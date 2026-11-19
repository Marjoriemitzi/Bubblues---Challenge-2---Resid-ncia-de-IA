"""Tracing no Langfuse (com um cliente falso) e escolha do Retrieval por configuracao."""

import pytest

from orchestrator import observabilidade as obs
from orchestrator.evidence_store import MemoryEvidenceStore
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, run
from orchestrator.llm_client import LLMClient, LLMError
from orchestrator.llm_fake import LLMFalso, chamar, texto
from orchestrator.retrieval_agent import RetrievalAgent
from orchestrator.retrieval_factory import criar_retrieval, modo_atual, montar_grafo
from orchestrator.retrieval_pipeline import RetrievalPipeline
from orchestrator.stubs import _request, stub_communication, stub_nlu
from orchestrator.tests.test_retrieval_agent import ASA_SUL, BUSCA, FINAL_B1
from orchestrator.tests.test_retrieval_pipeline import CAFE_OK, FakeBusca, _conexao, _linha, _registro
from orchestrator.tests.test_llm_client import FakeOpenAI, _resp, _usage
from orchestrator.validation_tool import EvidenceValidator


class FakeObs:
    def __init__(self, ev):
        self.ev, self.updates = ev, []

    def update(self, **kw):
        self.updates.append(kw)
        self.ev["update"] = {**self.ev.get("update", {}), **kw}


class FakeLangfuse:
    """Registra cada observacao: nome, tipo, entrada, e quem e o pai (pela pilha de contextos)."""

    def __init__(self, falha_ao_abrir=False):
        self.eventos, self.pilha, self.falha = [], [], falha_ao_abrir

    def start_as_current_observation(self, *, name, as_type, input=None, metadata=None, **extra):
        if self.falha:
            raise RuntimeError("langfuse fora")
        ev = {"nome": name, "tipo": as_type, "input": input, "metadata": metadata, "extra": extra,
              "pai": self.pilha[-1]["nome"] if self.pilha else None}
        self.eventos.append(ev)
        fake = self

        class CM:
            def __enter__(s):
                fake.pilha.append(ev)
                return FakeObs(ev)

            def __exit__(s, *a):
                fake.pilha.pop()
                ev["saiu_com_erro"] = a[0] is not None
                return False

        return CM()

    def flush(self):
        self.flushed = True


@pytest.fixture
def lf():
    f = FakeLangfuse()
    obs.configurar(f)
    yield f
    obs.configurar(None)


def _por_nome(lf, prefixo):
    return [e for e in lf.eventos if e["nome"].startswith(prefixo)]


# ------------------------------------------------------------------ liga/desliga e robustez
def test_desligado_por_padrao_sob_pytest_mesmo_com_chaves_no_ambiente(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-x")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-x")
    obs._inicializado, obs._cliente = False, None
    assert obs.cliente() is None
    with obs.observar("x") as o:
        o.update(output=1)  # no-op, nao levanta
    obs.configurar(None)


def test_falha_do_langfuse_nao_derruba_o_sistema():
    obs.configurar(FakeLangfuse(falha_ao_abrir=True))
    fake = FakeBusca(_registro([_linha(1, "A", 111, CAFE_OK)]))
    ag = RetrievalAgent(llm=LLMFalso(chamar(("buscar_lugares", BUSCA)), FINAL_B1), conexao_factory=_conexao, embedder=lambda t: [0.1] * 768,
                        buscar_fn=fake, regioes_fn=lambda c, n, l: ASA_SUL, validator=EvidenceValidator(store=MemoryEvidenceStore()), fallback=None)
    out = ag({"request_id": "r1", "structured_request": __import__("orchestrator.contracts", fromlist=["x"]).StructuredRequest.model_validate(_request("r1"))})
    assert out["validation_feedback"].approved
    obs.configurar(None)


def test_excecao_do_codigo_observado_segue_e_o_trace_marca_erro_sem_a_mensagem(lf):
    with pytest.raises(ValueError, match="segredo do usuario"):
        with obs.observar("passo"):
            raise ValueError("segredo do usuario")
    ev = lf.eventos[0]
    assert ev["saiu_com_erro"] and ev["update"]["level"] == "ERROR" and ev["update"]["status_message"] == "ValueError"
    assert "segredo" not in repr(lf.eventos)


def test_cortar_payload_grande():
    assert obs.cortar("x" * 5000).endswith("(+3500 caracteres)") and obs.cortar({"a": 1}) == {"a": 1} and obs.cortar(None) is None


# ------------------------------------------------------------------ a arvore de observacoes do grafo
def _agente_llm(fake, llm):
    return RetrievalAgent(llm=llm, conexao_factory=_conexao, embedder=lambda t: [0.1] * 768, buscar_fn=fake, regioes_fn=lambda c, n, l: ASA_SUL,
                          validator=EvidenceValidator(store=MemoryEvidenceStore()), fallback=None)


def test_pedido_completo_gera_pedido_nos_tools_gate_e_nao_vaza_o_texto_livre(lf):
    from orchestrator.graph import build_graph

    fake = FakeBusca(_registro([_linha(1, "A", 111, CAFE_OK)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), chamar(("validar_candidatos", {"busca_id": "B1"})), FINAL_B1)
    g = build_graph(stub_nlu(), _agente_llm(fake, llm), stub_communication)
    run(g, "TEXTO LIVRE SECRETO DO USUARIO", "r-trace")

    nomes = [e["nome"] for e in lf.eventos]
    assert nomes[0] == "pedido" and lf.eventos[0]["pai"] is None
    assert [f"no.{n}" for n in (NLU, RETRIEVAL, COMMUNICATION)] == [n for n in nomes if n.startswith("no.")]
    assert all(e["pai"] == "pedido" for e in _por_nome(lf, "no."))
    # as tools e o gate ficam DENTRO do no de retrieval
    assert {e["pai"] for e in _por_nome(lf, "tool.")} == {f"no.{RETRIEVAL}"}
    assert [e["tipo"] for e in _por_nome(lf, "tool.")] == ["tool", "tool"]
    gate = _por_nome(lf, "gate.")[0]
    assert gate["tipo"] == "guardrail" and gate["pai"] == f"no.{RETRIEVAL}" and gate["update"]["output"]["aprovado"] is True
    assert lf.eventos[0]["update"]["output"]["caminho"] == [NLU, RETRIEVAL, COMMUNICATION]
    assert "SECRETO" not in repr(lf.eventos)  # RNF02: o texto livre nunca chega ao trace


def test_tool_registra_resumo_e_marca_aviso_quando_o_modelo_erra(lf):
    from orchestrator.contracts import StructuredRequest
    from orchestrator.retrieval_tools import ContextoBusca, RetrievalTools

    req = StructuredRequest.model_validate(_request("r1"))
    t = RetrievalTools(ContextoBusca.de_pedido(req), "r1", conexao_factory=_conexao, embedder=lambda x: [0.1] * 768,
                       buscar_fn=FakeBusca(_registro([_linha(1, "Cafe A", 111, CAFE_OK)])), regioes_fn=lambda c, n, l: ASA_SUL)
    t.executar("buscar_lugares", {**BUSCA, "wheelchair": "no"})  # argumento proibido
    t.executar("buscar_lugares", BUSCA)
    ruim, bom = _por_nome(lf, "tool.buscar_lugares")
    assert ruim["update"]["level"] == "WARNING" and "argumentos nao permitidos" in ruim["update"]["output"]["erro"]
    assert bom["update"]["output"]["lugares"] == ["Cafe A"] and bom["update"]["output"]["busca_id"] == "B1"


# ------------------------------------------------------------------ chamadas ao LLM
def test_generation_leva_tokens_e_so_metadados_das_mensagens(lf):
    fake = FakeOpenAI(_resp("ok", usage=_usage(100, 20, hit=60, miss=40, raz=7)))
    llm = LLMClient(client=fake, model="deepseek-flash", reasoning_effort="none")
    llm.chat([{"role": "system", "content": "SEGREDO DO SISTEMA"}, {"role": "user", "content": "TEXTO LIVRE DO USUARIO"}], json_mode=True)
    g = lf.eventos[0]
    assert g["tipo"] == "generation" and g["extra"]["model"] == "deepseek-flash"
    assert g["input"] == {"n_mensagens": 2, "papeis": ["system", "user"]}
    assert g["update"]["usage_details"] == {"input": 100, "output": 20, "cache_hit_input": 60, "reasoning": 7}
    assert g["update"]["output"] == {"texto_chars": 2} and g["metadata"]["json_mode"] is True
    assert "USUARIO" not in repr(lf.eventos) and "SEGREDO" not in repr(lf.eventos)


def test_conteudo_so_com_a_variavel_de_depuracao(lf, monkeypatch):
    monkeypatch.setenv("LANGFUSE_LOG_CONTENT", "1")
    LLMClient(client=FakeOpenAI(_resp("resposta")), model="m").chat([{"role": "user", "content": "oi"}])
    assert lf.eventos[0]["input"] == [{"role": "user", "content": "oi"}] and lf.eventos[0]["update"]["output"]["content"] == "resposta"


def test_generation_com_retry_conta_as_requisicoes_e_erro_marca_o_span(lf):
    llm = LLMClient(client=FakeOpenAI(*[__import__("orchestrator.tests.test_llm_client", fromlist=["x"]).ErroHTTP(401)]), model="m")
    with pytest.raises(LLMError):
        llm.chat([])
    assert lf.eventos[0]["update"]["level"] == "ERROR" and lf.eventos[0]["update"]["status_message"] == "LLMError"


# ------------------------------------------------------------------ configuracao RETRIEVAL_MODE
def test_modo_padrao_e_llm_e_o_ambiente_vence(monkeypatch):
    monkeypatch.delenv("RETRIEVAL_MODE", raising=False)
    assert modo_atual() == "llm" and isinstance(criar_retrieval(llm=LLMFalso()), RetrievalAgent)
    monkeypatch.setenv("RETRIEVAL_MODE", "deterministic")
    assert modo_atual() == "deterministic" and isinstance(criar_retrieval(), RetrievalPipeline)
    assert modo_atual("llm") == "llm"  # argumento explicito vence o ambiente
    monkeypatch.setenv("RETRIEVAL_MODE", " LLM ")
    assert modo_atual() == "llm"


def test_padrao_sem_chave_degrada_para_o_pipeline_mas_llm_explicito_falha(monkeypatch):
    from orchestrator.llm_client import LLMError

    def sem_chave(*a, **k):
        raise LLMError("sem chave")

    monkeypatch.setattr("orchestrator.llm_client.LLMClient", sem_chave)
    monkeypatch.delenv("RETRIEVAL_MODE", raising=False)
    assert isinstance(criar_retrieval(), RetrievalPipeline)
    with pytest.raises(LLMError):
        criar_retrieval("llm")
    monkeypatch.setenv("RETRIEVAL_MODE", "llm")
    with pytest.raises(LLMError):
        criar_retrieval()


def test_modo_invalido_falha_claro(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_MODE", "turbo")
    with pytest.raises(ValueError, match="RETRIEVAL_MODE invalido"):
        criar_retrieval()


def test_agente_via_fabrica_tem_fallback_por_padrao_e_aceita_prompt_v2():
    ag = criar_retrieval("llm", llm=LLMFalso(), prompt="v2")
    assert ag.prompt == "v2" and isinstance(ag.fallback, RetrievalPipeline)
    assert criar_retrieval("llm", llm=LLMFalso(), fallback=None).fallback is None


def test_montar_grafo_usa_o_modo_escolhido():
    fake = FakeBusca(_registro([_linha(1, "A", 111, CAFE_OK)]))
    colab = dict(conexao_factory=_conexao, embedder=lambda t: [0.1] * 768, buscar_fn=fake, regioes_fn=lambda c, n, l: ASA_SUL,
                 validator=EvidenceValidator(store=MemoryEvidenceStore()))
    g = montar_grafo(stub_nlu(spatial_constraints={"target_region": None, "max_radius_km": 3.0}), stub_communication, "deterministic", **colab)
    s = run(g, "q", "r-fabrica")
    assert s["final_response"] == "top-3 auditado" and "agente llm" not in s["agent_trace"][1].note
