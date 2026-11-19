"""LLMClient: retry, erros definitivos e resposta vazia, com um cliente OpenAI falso."""

import json
from types import SimpleNamespace

import pytest

from orchestrator.llm_client import (
    LLMClient,
    LLMError,
    Uso,
    _base_url,
    extrair_chamadas,
    mensagem_de_ferramenta,
    mensagem_para_dict,
)
from orchestrator.llm_fake import LLMFalso, chamar, texto


class ErroHTTP(Exception):
    def __init__(self, status):
        super().__init__(f"http {status} segredo-no-corpo")
        self.status_code = status


class APIConnectionError(Exception):  # mesmo nome da classe do SDK
    pass


def _resp(conteudo, finish="stop", usage=None, **msg):
    m = SimpleNamespace(content=conteudo, tool_calls=None, **msg)
    return SimpleNamespace(choices=[SimpleNamespace(message=m, finish_reason=finish)], usage=usage)


class FakeOpenAI:
    def __init__(self, *respostas):
        self.respostas, self.chamadas = list(respostas), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.chamadas.append(kw)
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _llm(fake, **kw):
    esperas = []
    return LLMClient(client=fake, model="m", sleep=esperas.append, **kw), esperas


def test_resposta_normal_e_parametros():
    fake = FakeOpenAI(_resp('{"a":1}'))
    llm, _ = _llm(fake)
    msg = llm.chat([{"role": "user", "content": "x"}], json_mode=True)
    assert msg.content == '{"a":1}'
    kw = fake.chamadas[0]
    assert kw["model"] == "m" and kw["response_format"] == {"type": "json_object"} and kw["temperature"] == 0.0


@pytest.mark.parametrize("status", [429, 500, 503])
def test_erro_transitorio_tenta_de_novo_com_espera_crescente(status):
    fake = FakeOpenAI(ErroHTTP(status), ErroHTTP(status), _resp("ok"))
    llm, esperas = _llm(fake)
    assert llm.chat([]).content == "ok" and llm.chamadas == 3
    assert esperas == [1.5, 3.0]


@pytest.mark.parametrize("status", [400, 401, 402, 422])
def test_erro_definitivo_nao_repete_e_nao_vaza_corpo(status):
    fake = FakeOpenAI(ErroHTTP(status))
    llm, esperas = _llm(fake)
    with pytest.raises(LLMError) as e:
        llm.chat([])
    assert "segredo-no-corpo" not in str(e.value) and str(status) in str(e.value)
    assert llm.chamadas == 1 and esperas == []


def test_erro_de_rede_e_transitorio():
    llm, _ = _llm(FakeOpenAI(APIConnectionError(), _resp("ok")))
    assert llm.chat([]).content == "ok"


def test_json_vazio_conta_como_falha_e_repete():
    llm, _ = _llm(FakeOpenAI(_resp("   "), _resp('{"x":1}')))
    assert json.loads(llm.chat([], json_mode=True).content) == {"x": 1}
    assert llm.chamadas == 2


def test_esgota_tentativas():
    llm, _ = _llm(FakeOpenAI(*[ErroHTTP(503)] * 3), max_tentativas=3)
    with pytest.raises(LLMError, match="3 tentativas"):
        llm.chat([])


def test_sem_chave_falha_claro(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    with pytest.raises(LLMError, match="DEEPSEEK_API_KEY"):
        LLMClient()


# ------------------------------------------------------------------ Fase C: tools, thinking, strict, uso
def _usage(p, c, hit=0, miss=0, raz=0):
    return SimpleNamespace(prompt_tokens=p, completion_tokens=c, prompt_cache_hit_tokens=hit,
                           prompt_cache_miss_tokens=miss, completion_tokens_details=SimpleNamespace(reasoning_tokens=raz))


def test_acumula_uso_de_tokens_incluindo_cache_e_raciocinio():
    fake = FakeOpenAI(_resp("a", usage=_usage(100, 20, hit=60, miss=40, raz=7)), _resp("b", usage=_usage(50, 10, hit=50, miss=0)))
    llm, _ = _llm(fake)
    llm.chat([]); llm.chat([])
    assert llm.uso.como_dict() == {"chamadas": 2, "prompt_tokens": 150, "completion_tokens": 30,
                                   "cache_hit_tokens": 110, "cache_miss_tokens": 40, "reasoning_tokens": 7}
    assert llm.chamadas == 2


def test_uso_tolera_resposta_sem_usage():
    llm, _ = _llm(FakeOpenAI(_resp("a")))
    llm.chat([])
    assert llm.uso.prompt_tokens == 0 and llm.uso.chamadas == 1
    Uso().somar(None)


def test_tools_tool_choice_e_reasoning_effort_vao_para_a_api():
    fake = FakeOpenAI(_resp("ok"))
    llm, _ = _llm(fake, reasoning_effort="none")
    tools = [{"type": "function", "function": {"name": "f"}}]
    llm.chat([], tools=tools, tool_choice="auto")
    kw = fake.chamadas[0]
    assert kw["tools"] == tools and kw["tool_choice"] == "auto" and kw["reasoning_effort"] == "none"


def test_tool_choice_sem_tools_nao_e_enviado():
    fake = FakeOpenAI(_resp("ok"))
    _llm(fake)[0].chat([], tool_choice="auto")
    assert "tool_choice" not in fake.chamadas[0]


def test_padrao_e_thinking_desligado_e_a_variavel_de_ambiente_vence(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_REASONING_EFFORT", raising=False)
    fake = FakeOpenAI(_resp("ok"))
    LLMClient(client=fake, model="m").chat([])
    assert fake.chamadas[0]["reasoning_effort"] == "none"
    monkeypatch.setenv("DEEPSEEK_REASONING_EFFORT", "high")
    assert LLMClient(client=FakeOpenAI(), model="m").reasoning_effort == "high"
    assert LLMClient(client=FakeOpenAI(), model="m", reasoning_effort="low").reasoning_effort == "low"  # argumento vence o ambiente


def test_modelo_padrao_e_o_flash(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    assert LLMClient(client=FakeOpenAI()).model == "deepseek-flash"


def test_reasoning_effort_por_chamada_vence_o_do_cliente_e_invalido_e_recusado():
    fake = FakeOpenAI(_resp("ok"))
    llm, _ = _llm(fake, reasoning_effort="high")
    llm.chat([], reasoning_effort="low")
    assert fake.chamadas[0]["reasoning_effort"] == "low"
    with pytest.raises(LLMError, match="reasoning_effort"):
        llm.chat([], reasoning_effort="turbo")
    with pytest.raises(LLMError, match="reasoning_effort"):
        _llm(FakeOpenAI(), reasoning_effort="turbo")


def test_resposta_truncada_e_filtro_de_conteudo_falham_sem_retry():
    for motivo, trecho in (("length", "truncada"), ("content_filter", "filtro")):
        llm, esperas = _llm(FakeOpenAI(_resp("x", finish=motivo)))
        with pytest.raises(LLMError, match=trecho):
            llm.chat([])
        assert llm.chamadas == 1 and esperas == []


def test_geracao_interrompida_pelo_provedor_e_transitoria():
    llm, _ = _llm(FakeOpenAI(_resp("", finish="insufficient_system_resource"), _resp("", finish="aborted"), _resp("ok")))
    assert llm.chat([]).content == "ok" and llm.chamadas == 3


def test_prazo_total_limita_as_tentativas_e_a_espera():
    t = {"agora": 0.0}
    esperas = []
    llm = LLMClient(client=FakeOpenAI(*[ErroHTTP(503)] * 5), model="m", sleep=lambda s: (esperas.append(s), t.__setitem__("agora", t["agora"] + s)),
                    relogio=lambda: t["agora"], max_tentativas=5)
    with pytest.raises(LLMError, match="tempo total excedido"):
        llm.chat([], prazo=2.0)
    assert esperas == [1.5, 0.5]  # a 2a espera foi cortada para caber no prazo
    assert llm.chamadas == 2


def test_cada_requisicao_recebe_o_timeout_do_tempo_restante_do_prazo():
    t = {"agora": 100.0}
    fake = FakeOpenAI(ErroHTTP(503), _resp("ok"))
    llm = LLMClient(client=fake, model="m", timeout=90.0, sleep=lambda s: t.__setitem__("agora", t["agora"] + s), relogio=lambda: t["agora"])
    llm.chat([], prazo=160.0)  # 60 s de prazo, bem abaixo do timeout de 90 s
    assert fake.chamadas[0]["timeout"] == 60.0
    assert fake.chamadas[1]["timeout"] == pytest.approx(58.5)  # depois da espera de 1,5 s


def test_sem_prazo_nao_define_timeout_por_requisicao():
    fake = FakeOpenAI(_resp("ok"))
    _llm(fake)[0].chat([])
    assert "timeout" not in fake.chamadas[0]


def test_prazo_ja_vencido_nem_chama_a_api():
    fake = FakeOpenAI(_resp("x"))
    llm = LLMClient(client=fake, model="m", relogio=lambda: 10.0)
    with pytest.raises(LLMError, match="tempo total"):
        llm.chat([], prazo=5.0)
    assert fake.chamadas == []


def test_strict_usa_o_endpoint_beta():
    assert _base_url("https://api.deepseek.com", True) == "https://api.deepseek.com/beta"
    assert _base_url("https://api.deepseek.com/", True) == "https://api.deepseek.com/beta"
    assert _base_url("https://api.deepseek.com/beta", True) == "https://api.deepseek.com/beta"
    assert _base_url("https://api.deepseek.com", False) == "https://api.deepseek.com"


def test_listar_modelos():
    fake = FakeOpenAI()
    fake.models = SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id="a"), SimpleNamespace(id="b")]))
    assert _llm(fake)[0].listar_modelos() == ["a", "b"]


# ------------------------------------------------------------------ historico com tool calling
def test_extrair_chamadas_e_historico_preservam_ids_e_argumentos_crus():
    msg = chamar(("buscar_lugares", {"k": 3}), ("validar_candidatos", "{nao e json"), conteudo=None)
    cs = extrair_chamadas(msg)
    assert [(c.id, c.nome) for c in cs] == [("call_1", "buscar_lugares"), ("call_2", "validar_candidatos")]
    assert json.loads(cs[0].argumentos) == {"k": 3} and cs[1].argumentos == "{nao e json"
    d = mensagem_para_dict(msg)
    assert d["role"] == "assistant" and d["content"] is None
    assert d["tool_calls"][1] == {"id": "call_2", "type": "function", "function": {"name": "validar_candidatos", "arguments": "{nao e json"}}


def test_historico_devolve_reasoning_content_obrigatorio_no_modo_thinking():
    d = mensagem_para_dict(chamar(("f", {}), raciocinio="vou buscar primeiro"))
    assert d["reasoning_content"] == "vou buscar primeiro"
    assert "reasoning_content" not in mensagem_para_dict(SimpleNamespace(content="oi", tool_calls=None))
    assert mensagem_para_dict(texto("fim", raciocinio="")).get("reasoning_content") == ""  # string vazia tambem volta


def test_mensagem_sem_tool_calls_nao_cria_a_chave():
    assert "tool_calls" not in mensagem_para_dict(texto("so texto"))


def test_resposta_de_ferramenta_vira_texto_json():
    m = mensagem_de_ferramenta("call_1", {"erro": "ação inválida"})
    assert m == {"role": "tool", "tool_call_id": "call_1", "content": '{"erro": "ação inválida"}'}
    assert mensagem_de_ferramenta("c", "ja e texto")["content"] == "ja e texto"


# ------------------------------------------------------------------ LLM falso com roteiro
def test_llm_falso_segue_o_roteiro_e_guarda_o_que_recebeu():
    llm = LLMFalso(chamar(("resolver_regiao", {"nome": "Asa Sul"})), texto("pronto"))
    a = llm.chat([{"role": "user", "content": "oi"}], tools=[{"x": 1}], prazo=9.0)
    assert extrair_chamadas(a)[0].nome == "resolver_regiao"
    b = llm.chat([{"role": "user", "content": "oi"}, mensagem_para_dict(a)])
    assert b.content == "pronto" and llm.chamadas == 2
    assert len(llm.mensagens_recebidas[1]) == 2 and llm.parametros[0]["prazo"] == 9.0


def test_llm_falso_levanta_excecao_do_roteiro_e_acusa_roteiro_curto():
    llm = LLMFalso(LLMError("fora do ar"))
    with pytest.raises(LLMError, match="fora do ar"):
        llm.chat([])
    with pytest.raises(AssertionError, match="roteiro acabou"):
        llm.chat([])
