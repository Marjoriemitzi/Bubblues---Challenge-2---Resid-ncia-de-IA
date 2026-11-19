"""NLUAgent com LLM falso: contrato, categorias da base, retry com feedback e RNF02."""

import json
from types import SimpleNamespace

import pytest

from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, build_graph, run
from orchestrator.nlu_agent import EXEMPLO, NLUAgent, NLUFalhou, montar_prompt
from orchestrator.stubs import stub_communication, stub_retrieval, stub_validation

CATS = ["cafe", "park", "restaurant"]


class FakeLLM:
    model = "fake-model"

    def __init__(self, *respostas):
        self.respostas, self.chamadas = list(respostas), []

    def chat(self, messages, **kw):
        self.chamadas.append([dict(m) for m in messages])
        r = self.respostas.pop(0)
        return SimpleNamespace(content=r if isinstance(r, str) else json.dumps(r), tool_calls=None)


def _json(**over):
    return {**EXEMPLO, **over}


def _estado(texto="quero um cafe calmo na asa sul", rid="r1"):
    return {"request_id": rid, "raw_query": texto}


def test_prompt_traz_categorias_exemplo_e_regras():
    p = montar_prompt(CATS)
    assert '["cafe", "park", "restaurant"]' in p and "json" in p.lower() and "madrugada" in p
    assert "request_id" in p and "NAO inclua" in p


def test_resposta_valida_vira_structured_request_sem_raw_query():
    out = NLUAgent(FakeLLM(_json()), CATS)(_estado())
    req = out["structured_request"]
    assert req["request_id"] == "r1" and req["raw_query"] is None
    assert req["target_amenities"] == ["cafe"] and "fake-model" in out["note"]
    assert "cafe calmo" not in out["note"]  # nada do texto do usuario na nota


def test_request_id_do_estado_vence_o_do_modelo():
    out = NLUAgent(FakeLLM(_json(request_id="inventado", raw_query="vazou")), CATS)(_estado(rid="REAL"))
    assert out["structured_request"]["request_id"] == "REAL" and out["structured_request"]["raw_query"] is None


def test_json_invalido_volta_ao_modelo_com_o_motivo():
    llm = FakeLLM("{nao e json", _json())
    out = NLUAgent(llm, CATS)(_estado())
    assert "tentativas=2" in out["note"] and len(llm.chamadas) == 2
    ultima = llm.chamadas[1][-1]
    assert ultima["role"] == "user" and "Corrija" in ultima["content"]


def test_flags_contraditorias_sao_barradas_pelo_contrato():
    contraditoria = _json(intent_valid=True, out_of_scope=True, out_of_scope_reason="frete")
    llm = FakeLLM(contraditoria, _json(intent_valid=False, out_of_scope=True, out_of_scope_reason="servico de frete",
                                       target_amenities=[]))
    out = NLUAgent(llm, CATS)(_estado("preciso de um frete"))
    assert out["structured_request"]["intent_valid"] is False and len(llm.chamadas) == 2


def test_categoria_fora_da_base_e_recusada_e_corrigida():
    llm = FakeLLM(_json(target_amenities=["library_bookstore"]), _json(target_amenities=["cafe"]))
    out = NLUAgent(llm, CATS)(_estado())
    assert out["structured_request"]["target_amenities"] == ["cafe"]
    assert "fora da lista" in llm.chamadas[1][-1]["content"]


def test_desiste_depois_do_limite_sem_vazar_texto():
    with pytest.raises(NLUFalhou) as e:
        NLUAgent(FakeLLM("x", "y", "z"), CATS, max_tentativas=3)(_estado("texto secreto do usuario"))
    assert "secreto" not in str(e.value)


def test_sem_texto_falha():
    with pytest.raises(NLUFalhou):
        NLUAgent(FakeLLM(_json()), CATS)({"request_id": "r", "raw_query": "  "})


def test_pedido_ambiguo_mantem_intent_valida_e_pergunta():
    out = NLUAgent(FakeLLM(_json(clarification_needed="Que tipo de lugar voce prefere?", target_amenities=["cafe"])), CATS)(_estado())
    assert out["structured_request"]["clarification_needed"].startswith("Que tipo")


def test_no_no_grafo_zera_raw_query_e_roteia():
    nlu = NLUAgent(FakeLLM(_json()), CATS)
    g = build_graph(nlu, stub_retrieval, stub_validation(1), stub_communication)
    s = run(g, "quero um cafe calmo", "r-grafo")
    assert s["raw_query"] is None and s["agent_trace"][0].agent == NLU and s["agent_trace"][1].agent == RETRIEVAL


def test_fora_de_escopo_vai_direto_ao_communication():
    llm = FakeLLM(_json(intent_valid=False, out_of_scope=True, out_of_scope_reason="servico de frete", target_amenities=[]))
    g = build_graph(NLUAgent(llm, CATS), stub_retrieval, stub_validation(1), stub_communication)
    s = run(g, "preciso de um frete", "r-fora")
    assert [t.agent for t in s["agent_trace"]] == [NLU, COMMUNICATION]
