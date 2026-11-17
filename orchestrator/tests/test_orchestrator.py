import pytest
from pydantic import ValidationError

from orchestrator import build_graph, run
from orchestrator.contracts import EvidenceRecord, SearchResponse, StructuredRequest
from orchestrator.graph import COMMUNICATION, FALLBACK_MESSAGE, NLU, RETRIEVAL, VALIDATION
from orchestrator.stubs import (
    _request,
    stub_communication,
    stub_nlu,
    stub_retrieval,
    stub_validation,
)

QUERY = "Quero um cafe tranquilo na Asa Sul com acesso para cadeirantes"


def make(nlu=None, validation=None, **kw):
    return build_graph(
        nlu or stub_nlu(),
        stub_retrieval,
        validation or stub_validation(1),
        stub_communication,
        **kw,
    )


def path(state):
    return [t.agent for t in state["agent_trace"]]


# ---- 3 caminhos de roteamento --------------------------------------------
def test_fluxo_normal():
    s = run(make(), QUERY, "req-1")
    assert path(s) == [NLU, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert s["final_response"] == "top-3 auditado"
    assert s["retry_count"] == 0


@pytest.mark.parametrize(
    "over",
    [
        {"intent_valid": False, "out_of_scope": True, "out_of_scope_reason": "frete"},
        {"intent_valid": False, "impossible_criteria": True, "impossible_criteria_reason": "03h30"},
    ],
)
def test_abstencao_precoce_pula_busca(over):
    s = run(make(nlu=stub_nlu(**over)), QUERY, "req-2")
    assert path(s) == [NLU, COMMUNICATION]
    assert s["final_response"] == "abstencao"
    assert "search_response" not in s


def test_reconsulta_e_aprova_na_segunda():
    s = run(make(validation=stub_validation(approve_on_attempt=2)), QUERY, "req-3")
    assert path(s) == [NLU, RETRIEVAL, VALIDATION, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert s["retry_count"] == 1
    # o Retrieval recebeu o feedback e excluiu o POI reprovado
    assert s["search_response"].items[0].place_id == "POI-02"


def test_trava_de_2_reconsultas():
    s = run(make(validation=stub_validation(approve_on_attempt=None)), QUERY, "req-4")
    # 1 busca inicial + 2 reconsultas = 3 passagens por retrieval/validation
    assert path(s).count(RETRIEVAL) == 3
    assert path(s).count(VALIDATION) == 3
    assert path(s)[-1] == COMMUNICATION
    assert s["retry_count"] == 3  # 3 reprovacoes; a ultima nao gerou reconsulta
    assert s["final_response"] == "abstencao"


# ---- trace ----------------------------------------------------------------
def test_trace_tem_justificativa_de_cada_transicao():
    s = run(make(), QUERY, "req-5")
    for t in s["agent_trace"]:
        assert t.justification and t.next_agent and t.output_keys
    assert s["agent_trace"][0].next_agent == RETRIEVAL
    assert s["agent_trace"][-1].next_agent == "__end__"


# ---- RNF02 ----------------------------------------------------------------
def test_raw_query_descartado_apos_nlu():
    s = run(make(), QUERY, "req-6")
    assert s["raw_query"] is None
    assert s["structured_request"].raw_query is None
    assert "cadeirantes" not in repr(s)  # nenhum rastro do texto livre


# ---- contratos ------------------------------------------------------------
def test_contrato_rejeita_campo_obrigatorio_ausente():
    bad = _request("x")
    del bad["activity"]
    with pytest.raises(ValidationError):
        StructuredRequest.model_validate(bad)


def test_contrato_rejeita_campo_desconhecido_e_enum_invalido():
    with pytest.raises(ValidationError):
        StructuredRequest.model_validate(_request("x", campo_inventado=1))
    with pytest.raises(ValidationError):
        StructuredRequest.model_validate(_request("x", noise_tolerance="ensurdecedor"))


def test_orquestrador_barra_payload_invalido_do_agente():
    def nlu_ruim(state):
        bad = _request(state["request_id"])
        del bad["vibe"]
        return {"structured_request": bad}

    with pytest.raises(ValidationError):
        run(make(nlu=nlu_ruim), QUERY, "req-7")


def test_contratos_3_e_4_exigem_campos():
    with pytest.raises(ValidationError):
        SearchResponse.model_validate({"query_id": "q"})
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate({"evidence_id": "e"})


# ---- consistencia do Contrato 2 e esclarecimento ---------------------------
@pytest.mark.parametrize(
    "over",
    [
        {"out_of_scope": True, "out_of_scope_reason": "frete"},  # intent_valid segue true
        {"impossible_criteria": True, "impossible_criteria_reason": "x"},
        {"intent_valid": False},  # sem nenhuma flag
        {"intent_valid": False, "out_of_scope": True},  # sem motivo
        {"intent_valid": False, "impossible_criteria": True},  # sem motivo
    ],
)
def test_contrato_2_rejeita_flags_contraditorias(over):
    with pytest.raises(ValidationError):
        StructuredRequest.model_validate(_request("x", **over))


def test_clarification_needed_desvia_para_communication():
    s = run(make(nlu=stub_nlu(clarification_needed="Qual bairro voce prefere?")), QUERY, "req-8")
    assert path(s) == [NLU, COMMUNICATION]
    assert "search_response" not in s
    assert s["final_response"] == "Qual bairro voce prefere?"
    assert "clarification_needed" in s["agent_trace"][0].justification


# ---- busca vazia e falhas de agente ----------------------------------------
def retrieval_vazio(state):
    return {
        "search_response": {
            "query_id": state["request_id"],
            "status": "NO_RESULTS",
            "applied_filters": {"radius_km": 10.0, "expanded_once": True, "amenities": ["cafe"]},
            "results_count": 0,
            "items": [],
        }
    }


def test_busca_sem_resultados_pula_validacao():
    g = build_graph(stub_nlu(), retrieval_vazio, stub_validation(1), stub_communication)
    s = run(g, QUERY, "req-9")
    assert path(s) == [NLU, RETRIEVAL, COMMUNICATION]
    assert s["retry_count"] == 0
    assert s["final_response"] == "abstencao"


@pytest.mark.parametrize("quem", [NLU, RETRIEVAL, VALIDATION])
def test_falha_de_agente_vira_abstencao_segura(quem):
    def quebrado(state):
        raise ConnectionError(f"banco caiu: {state.get('raw_query')}")

    agents = {
        NLU: stub_nlu(),
        RETRIEVAL: stub_retrieval,
        VALIDATION: stub_validation(1),
    }
    agents[quem] = quebrado
    g = build_graph(agents[NLU], agents[RETRIEVAL], agents[VALIDATION], stub_communication)
    s = run(g, QUERY, "req-10")
    assert path(s)[-1] == COMMUNICATION
    assert s["error"] == f"{quem}: ConnectionError"
    assert s["final_response"] == "abstencao"
    assert s["raw_query"] is None
    assert "cadeirantes" not in repr(s)  # a mensagem da excecao nao vaza para o estado/trace


def test_falha_da_propria_communication_usa_mensagem_fixa():
    def comm_quebrada(state):
        raise RuntimeError("llm timeout")

    s = run(build_graph(stub_nlu(), stub_retrieval, stub_validation(1), comm_quebrada), QUERY, "req-11")
    assert s["final_response"] == FALLBACK_MESSAGE
    assert s["agent_trace"][-1].next_agent == "__end__"
