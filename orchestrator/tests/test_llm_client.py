"""LLMClient: retry, erros definitivos e resposta vazia, com um cliente OpenAI falso."""

import json
from types import SimpleNamespace

import pytest

from orchestrator.llm_client import LLMClient, LLMError


class ErroHTTP(Exception):
    def __init__(self, status):
        super().__init__(f"http {status} segredo-no-corpo")
        self.status_code = status


class APIConnectionError(Exception):  # mesmo nome da classe do SDK
    pass


def _resp(conteudo):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=conteudo, tool_calls=None))])


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
