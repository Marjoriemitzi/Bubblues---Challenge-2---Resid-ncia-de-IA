"""RetrievalAgent (LLM) com LLM falso roteirizado: o que o modelo decide, o que o codigo garante e o fallback."""

import json

import pytest

from orchestrator.contracts import StructuredRequest
from orchestrator.evidence_store import MemoryEvidenceStore
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, build_graph, run
from orchestrator.llm_client import LLMError
from orchestrator.llm_fake import LLMFalso, chamar, texto
from orchestrator.retrieval_agent import AgenteSemDecisao, RetrievalAgent, _ler_decisao
from orchestrator.retrieval_pipeline import RetrievalPipeline
from orchestrator.stubs import _request, stub_communication, stub_nlu
from orchestrator.tests.test_retrieval_pipeline import CAFE_OK, FakeBusca, _conexao, _linha, _registro
from orchestrator.validation_tool import EvidenceValidator

ASA_SUL = [{"nome": "Asa Sul", "tipo": "place=suburb", "latitude": -15.8169, "longitude": -47.9}]
BUSCA = dict(latitude=-15.8169, longitude=-47.9, raio_km=3.0, categorias=["cafe"], texto_consulta="cafe calmo para ler", k=3)
FINAL_B1 = texto('{"busca_escolhida": "B1", "motivo": "melhores opcoes"}')


def _bom(pid, nome, osm):
    return _linha(pid, nome, osm, CAFE_OK)


def _ruim(pid, nome, osm):
    return _linha(pid, nome, osm, {"amenity": "cafe", "wheelchair": "no"})


def _estado(**over):
    req = StructuredRequest.model_validate(_request("r1", **over))
    return {"request_id": "r1", "structured_request": req}


def _agente(llm, fake, regioes=None, **kw):
    store = MemoryEvidenceStore()
    kw.setdefault("fallback", None)
    ag = RetrievalAgent(
        llm=llm, conexao_factory=_conexao, embedder=lambda t: [0.1] * 768, buscar_fn=fake,
        regioes_fn=regioes or (lambda c, n, l: ASA_SUL), validator=EvidenceValidator(store=store), **kw,
    )
    return ag, store


# ------------------------------------------------------------------ leitura da decisao final
@pytest.mark.parametrize("txt,esperado", [
    ('{"busca_escolhida": "B1"}', "B1"),
    ('Segue a decisao:\n```json\n{"busca_escolhida": "B2", "place_ids": ["1"]}\n```', "B2"),
    ('{"busca_escolhida": null, "motivo": "nada bom"}', None),
])
def test_le_decisao_com_texto_em_volta(txt, esperado):
    assert _ler_decisao(txt)["busca_escolhida"] == esperado


@pytest.mark.parametrize("txt", [None, "", "sem json", "{quebrado", '{"outra": 1}', '{"busca_escolhida": 7}',
                                 '{"busca_escolhida": "B1", "place_ids": "1"}', "[1, 2]"])
def test_decisao_invalida_vira_none(txt):
    assert _ler_decisao(txt) is None


# ------------------------------------------------------------------ caminho feliz
def test_busca_simples_chega_ao_gate_e_entrega_evidencias():
    fake = FakeBusca(_registro([_bom(1, "A", 111), _bom(2, "B", 222)]))
    llm = LLMFalso(
        chamar(("resolver_regiao", {"nome": "Asa Sul"})),
        chamar(("buscar_lugares", BUSCA)),
        chamar(("validar_candidatos", {"busca_id": "B1"})),
        FINAL_B1,
    )
    ag, store = _agente(llm, fake)
    out = ag(_estado())
    assert [e.place_id for e in out["evidence_records"]] == ["1", "2"] and out["retry_count"] == 0
    assert out["validation_feedback"].approved and out["search_response"].consulta_id == "c-1"
    assert "agente llm" in out["note"] and "buscar_lugaresx1" in out["note"] and "passos=4" in out["note"]
    assert (fake.chamadas[0]["lat"], fake.chamadas[0]["lon"]) == (-15.8169, -47.9)
    assert [l["approved"] for l in store.linhas] == [True, True]


def test_o_modelo_ve_o_pedido_estruturado_sem_raw_query_e_as_quatro_tools():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), FINAL_B1)
    ag, _ = _agente(llm, fake)
    ag(_estado())
    sistema, usuario = llm.mensagens_recebidas[0][0], llm.mensagens_recebidas[0][1]
    assert "Voce e o Retrieval" in sistema["content"] and "Asa Sul" in usuario["content"] and "raw_query" not in usuario["content"]
    assert [t["function"]["name"] for t in llm.parametros[0]["tools"]] == [
        "resolver_regiao", "listar_categorias", "buscar_lugares", "validar_candidatos"]
    assert llm.parametros[0]["prazo"] is not None  # prazo total propagado ao cliente


def test_prompt_v2_acrescenta_a_conferencia_e_o_padrao_continua_v1():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    v1 = LLMFalso(chamar(("buscar_lugares", BUSCA)), FINAL_B1)
    v2 = LLMFalso(chamar(("buscar_lugares", BUSCA)), FINAL_B1)
    _agente(v1, fake)[0](_estado())
    _agente(v2, FakeBusca(_registro([_bom(1, "A", 111)])), prompt="v2")[0](_estado())
    s1, s2 = v1.mensagens_recebidas[0][0]["content"], v2.mensagens_recebidas[0][0]["content"]
    assert "CONFERENCIA ANTES DE ESCOLHER" not in s1 and "CONFERENCIA ANTES DE ESCOLHER" in s2 and s2.startswith(s1)
    with pytest.raises(ValueError, match="prompt desconhecido"):
        _agente(LLMFalso(), fake, prompt="v9")


def test_o_historico_devolve_o_reasoning_content_ao_modelo():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA), raciocinio="vou buscar cafes na Asa Sul"), FINAL_B1)
    _agente(llm, fake)[0](_estado())
    assistente = [m for m in llm.mensagens_recebidas[1] if m["role"] == "assistant"][0]
    assert assistente["reasoning_content"] == "vou buscar cafes na Asa Sul" and assistente["tool_calls"][0]["id"] == "call_1"


# ------------------------------------------------------------------ regiao
def test_regiao_ambigua_o_modelo_escolhe_o_candidato():
    regioes = lambda c, n, l: [  # noqa: E731
        {"nome": "Guara", "tipo": "place=quarter", "latitude": -15.83, "longitude": -47.98},
        {"nome": "Guara", "tipo": "admin_level=8", "latitude": -15.80, "longitude": -47.97}]
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(chamar(("resolver_regiao", {"nome": "Guara"})),
                   chamar(("buscar_lugares", {**BUSCA, "latitude": -15.80, "longitude": -47.97})), FINAL_B1)
    _agente(llm, fake, regioes=regioes)[0](_estado())
    assert (fake.chamadas[0]["lat"], fake.chamadas[0]["lon"]) == (-15.80, -47.97)


def test_regiao_sem_candidatos_vira_esclarecimento_decidido_pelo_codigo():
    llm = LLMFalso(chamar(("resolver_regiao", {"nome": "Narnia"})), texto('{"busca_escolhida": null, "motivo": "regiao desconhecida"}'))
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    ag, _ = _agente(llm, fake, regioes=lambda c, n, l: [])
    out = ag(_estado(spatial_constraints={"target_region": "Narnia", "max_radius_km": 3.0}))
    assert fake.chamadas == [] and "Narnia" in out["structured_request"].clarification_needed
    assert out["search_response"]["status"] == "NO_RESULTS"


def test_modelo_sem_escolha_e_regiao_conhecida_e_sem_resultado():
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), texto('{"busca_escolhida": null, "motivo": "nada adequado"}'))
    out = _agente(llm, FakeBusca(_registro([])))[0](_estado())
    assert out["search_response"]["status"] == "NO_RESULTS" and "structured_request" not in out
    assert "evidence_records" not in out


# ------------------------------------------------------------------ guardrails: o modelo nao consegue burlar
def test_modelo_tentando_desligar_o_filtro_e_barrado_e_a_busca_continua_filtrada():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(chamar(("buscar_lugares", {**BUSCA, "wheelchair": "no"})), chamar(("buscar_lugares", BUSCA)), FINAL_B1)
    out = _agente(llm, fake)[0](_estado())
    assert len(fake.chamadas) == 1 and fake.chamadas[0]["etiquetas_desejadas"] == {"wheelchair": "yes"}
    assert "argumentos nao permitidos" in llm.mensagens_recebidas[1][-1]["content"]
    assert out["validation_feedback"].approved


def test_coordenadas_alucinadas_fora_do_df_sao_recusadas():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(chamar(("buscar_lugares", {**BUSCA, "latitude": -23.55, "longitude": -46.63})), chamar(("buscar_lugares", BUSCA)), FINAL_B1)
    _agente(llm, fake)[0](_estado())
    assert len(fake.chamadas) == 1 and "fora do Distrito Federal" in llm.mensagens_recebidas[1][-1]["content"]


def test_place_id_inventado_na_decisao_e_recusado_e_o_modelo_corrige():
    fake = FakeBusca(_registro([_bom(1, "A", 111), _bom(2, "B", 222)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)),
                   texto('{"busca_escolhida": "B1", "place_ids": ["1", "999"]}'),
                   texto('{"busca_escolhida": "B1", "place_ids": ["2", "1"]}'))
    out = _agente(llm, fake)[0](_estado())
    assert [e.place_id for e in out["evidence_records"]] == ["2", "1"]  # subconjunto ordenado pelo modelo
    assert "SelecaoInvalida" in llm.mensagens_recebidas[2][-1]["content"]


def test_busca_inexistente_na_decisao_e_recusada():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), texto('{"busca_escolhida": "B9"}'), FINAL_B1)
    assert _agente(llm, fake)[0](_estado())["validation_feedback"].approved
    assert "BuscaDesconhecida" in llm.mensagens_recebidas[2][-1]["content"]


def test_o_gate_audita_mesmo_que_o_modelo_nunca_tenha_chamado_validar_candidatos():
    """Escolha ruim sem validar antes: o gate reprova, devolve o feedback e o modelo refaz a busca."""
    fake = FakeBusca(_registro([_ruim(1, "Sem rampa", 111), _bom(2, "Com rampa", 222)]), _registro([_bom(2, "Com rampa", 222)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), FINAL_B1,  # escolhe B1 inteira, sem validar
                   chamar(("buscar_lugares", BUSCA)), texto('{"busca_escolhida": "B2"}'))
    ag, store = _agente(llm, fake)
    out = ag(_estado())
    assert out["retry_count"] == 1 and [e.place_id for e in out["evidence_records"]] == ["2"]
    assert "GATE REPROVOU" in llm.mensagens_recebidas[2][-1]["content"]
    assert fake.chamadas[1]["k"] == 4 and fake.chamadas[1]["etiquetas_desejadas"] == {"wheelchair": "yes"}  # rejeitado excluido
    assert [(l["place_id"], l["approved"]) for l in store.linhas] == [("1", False), ("2", True)]


def test_validar_candidatos_do_modelo_ja_exclui_o_reprovado_da_proxima_busca():
    fake = FakeBusca(_registro([_ruim(1, "Sem rampa", 111), _bom(2, "Com rampa", 222)]), _registro([_bom(2, "Com rampa", 222)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), chamar(("validar_candidatos", {"busca_id": "B1"})),
                   chamar(("buscar_lugares", BUSCA)), texto('{"busca_escolhida": "B2"}'))
    out = _agente(llm, fake)[0](_estado())
    assert out["retry_count"] == 0 and fake.chamadas[1]["k"] == 4  # ja filtrado pela tool, o gate nem reprovou


# ------------------------------------------------------------------ limites e fallback
def _fallback_pipeline(fake):
    return RetrievalPipeline(conexao_factory=_conexao, embedder=lambda t: [0.1] * 768, buscar_fn=fake,
                             regioes_fn=lambda c, n, l: ASA_SUL, validator=EvidenceValidator(store=MemoryEvidenceStore()))


def test_passos_esgotados_caem_no_pipeline():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(*[chamar(("listar_categorias", {}))] * 3)
    ag, _ = _agente(llm, fake, max_passos=3, fallback=_fallback_pipeline(fake))
    out = ag(_estado())
    assert out["note"].startswith("FALLBACK para o pipeline (AgenteSemDecisao)") and out["validation_feedback"].approved
    assert llm.chamadas == 3


def test_sem_fallback_o_erro_sobe():
    llm = LLMFalso(*[chamar(("listar_categorias", {}))] * 2)
    with pytest.raises(AgenteSemDecisao):
        _agente(llm, FakeBusca(_registro([])), max_passos=2, fallback=None)[0](_estado())


def test_llm_fora_do_ar_cai_no_pipeline():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    ag, _ = _agente(LLMFalso(LLMError("503")), fake, fallback=_fallback_pipeline(fake))
    out = ag(_estado())
    assert "FALLBACK" in out["note"] and "LLMError" in out["note"] and [e.place_id for e in out["evidence_records"]] == ["1"]


def test_resposta_final_sem_json_pede_uma_correcao_e_depois_cai_no_pipeline():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(texto("acho que o primeiro"), texto("{ainda quebrado"))
    ag, _ = _agente(llm, fake, fallback=_fallback_pipeline(fake))
    out = ag(_estado())
    assert "FALLBACK" in out["note"] and "AgenteSemDecisao" in out["note"]
    assert "JSON final" in llm.mensagens_recebidas[1][-1]["content"]


def test_gate_reprovando_ate_o_fim_devolve_a_reprovacao_sem_fallback():
    fake = FakeBusca(_registro([_ruim(1, "R1", 111)]), _registro([_ruim(2, "R2", 222)]), _registro([_ruim(3, "R3", 333)]))
    escolha = lambda b: texto(json.dumps({"busca_escolhida": b}))  # noqa: E731
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), escolha("B1"), chamar(("buscar_lugares", BUSCA)), escolha("B2"),
                   chamar(("buscar_lugares", BUSCA)), escolha("B3"))
    out = _agente(llm, fake, fallback=None)[0](_estado())
    assert out["retry_count"] == 2 and "evidence_records" not in out and out["validation_feedback"].approved is False
    assert "reconsultas esgotadas" in out["note"]


def test_gate_reprovando_ate_o_fim_com_fallback_chama_o_pipeline():
    fake = FakeBusca(_registro([_ruim(1, "R1", 111)]), _registro([_ruim(2, "R2", 222)]), _registro([_ruim(3, "R3", 333)]),
                     _registro([_bom(4, "Bom", 444)]))
    escolha = lambda b: texto(json.dumps({"busca_escolhida": b}))  # noqa: E731
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), escolha("B1"), chamar(("buscar_lugares", BUSCA)), escolha("B2"),
                   chamar(("buscar_lugares", BUSCA)), escolha("B3"))
    out = _agente(llm, fake, fallback=_fallback_pipeline(fake))[0](_estado())
    assert "FALLBACK para o pipeline (gate reprovou" in out["note"] and [e.place_id for e in out["evidence_records"]] == ["4"]


def test_estado_sem_request_falha_alto():
    with pytest.raises(ValueError):
        _agente(LLMFalso(), FakeBusca(_registro([])))[0]({"request_id": "r1"})


# ------------------------------------------------------------------ no grafo
def test_no_grafo_o_agente_ocupa_o_no_retrieval():
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    llm = LLMFalso(chamar(("buscar_lugares", BUSCA)), FINAL_B1)
    ag, _ = _agente(llm, fake)
    g = build_graph(stub_nlu(), ag, stub_communication)
    s = run(g, "q", "r-grafo")
    assert [t.agent for t in s["agent_trace"]] == [NLU, RETRIEVAL, COMMUNICATION]
    assert s["final_response"] == "top-3 auditado" and "agente llm" in s["agent_trace"][1].note
