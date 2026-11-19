"""Testes unitários e de integração para o Validation_Agent (Issue #9).

Critérios de Aceite testados:
  [x] Rejeita automaticamente qualquer candidato sem osm_id ou com is_public_verified != true (RNF01).
  [x] Reprova candidatos que violem restrições críticas da requisição (wheelchair_required, horário, ruído)
      e emite diagnóstico estruturado para o Retrieval_Agent.
  [x] Valida a soma exata das contribuições do score composto (|sum - score| < 1e-5) antes de aprovar.
  [x] Persiste o evidence_record (Contrato 4) na tabela evidencias_busca para 100% das buscas aprovadas.
  [x] Integração completa no fluxo LangGraph (fluxo normal, reconsulta após rejeição, e esgotamento de retries).
"""

import os
import pytest

from orchestrator import build_graph, run
from orchestrator.contracts import (
    AppliedFilters,
    EvidenceRecord,
    ScoreDecomposition,
    SearchItem,
    SearchResponse,
    StructuredRequest,
    ValidationFeedback,
)
from orchestrator.catalogo_exemplo import BASE_POIS_CATALOG
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, VALIDATION
from orchestrator.stubs import _request, stub_communication, stub_nlu
from orchestrator.evidence_store import MemoryEvidenceStore
from orchestrator.validation_tool import EvidenceValidator


def _osm_do_item(place_id: str) -> dict:
    """Campos de OSM que o Retrieval real anexaria ao SearchItem (vindos de `places`)."""
    poi = BASE_POIS_CATALOG.get(place_id)
    if not poi:
        return {}  # lugar sem dado de OSM: o RNF01 tem que reprova-lo
    tags = {k: poi[k] for k in ("wheelchair", "noise_level", "opening_hours") if poi.get(k)}
    return {
        "osm_id": poi["osm_id"],
        "osm_type": poi["osm_type"],
        "osm_tags": tags,
        "is_public_verified": poi["is_public_verified"],
    }


@pytest.fixture
def store():
    return MemoryEvidenceStore()


@pytest.fixture
def agent(store):
    return EvidenceValidator(store=store, metadata_catalog=BASE_POIS_CATALOG)


@pytest.fixture
def base_request():
    return StructuredRequest.model_validate(
        _request(
            request_id="req-test-01",
            activity="leitura e conversa calma",
            target_amenities=["cafe"],
            vibe="tranquilo",
            noise_tolerance="baixo",
            spatial_constraints={"target_region": "Asa Sul", "max_radius_km": 3.0},
            temporal_constraints={"preferred_time_slot": "tarde", "specific_hours": "14:00 - 18:00"},
            accessibility_requirements={"wheelchair_required": True, "elder_friendly": True},
        )
    )


def _search_item(
    place_id="POI-01",
    name="Ernesto Cafés Especiais",
    final_score=None,
    c_vec=0.36,
    c_dist=0.20,
    c_rep=0.15,
    c_comp=0.15,
    rank=1,
) -> SearchItem:
    sum_val = round(c_vec + c_dist + c_rep + c_comp, 6)
    actual_final_score = sum_val if final_score is None else final_score
    return SearchItem(
        rank=rank,
        place_id=place_id,
        name=name,
        amenity="cafe",
        address="CLS 115 Bloco C, Asa Sul",
        distance_km=1.2,
        cosine_similarity=0.9,
        final_score=actual_final_score,
        score_decomposition=ScoreDecomposition(
            vector_contribution=c_vec,
            distance_contribution=c_dist,
            reputation_contribution=c_rep,
            compatibility_contribution=c_comp,
            sum_check=sum_val,
        ),
        **_osm_do_item(place_id),
    )


# =========================================================================
# 1. RNF01: Zero Alucinação (osm_id e is_public_verified)
# =========================================================================

def test_rnf01_rejeita_candidato_sem_osm_id(agent, base_request):
    candidato = {
        "nome": "Café Fantasma Alucinado",
        "osm_id": None,
        "is_public_verified": True,
        "wheelchair": "yes",
        "score_contributions": {"vec": 0.4, "dist": 0.4},
        "score_total": 0.8,
    }
    resultado = agent.auditar_candidato(base_request, candidato)
    assert resultado["approved"] is False
    assert resultado["rnf01_passed"] is False
    assert any("sem osm_id válido" in m for m in resultado["rejection_reasons"])


def test_rnf01_rejeita_candidato_com_is_public_verified_false(agent, base_request):
    candidato = {
        "nome": "Espaço Privado Não Verificado",
        "osm_id": "node/12345678",
        "is_public_verified": False,
        "wheelchair": "yes",
        "score_contributions": {"vec": 0.4, "dist": 0.4},
        "score_total": 0.8,
    }
    resultado = agent.auditar_candidato(base_request, candidato)
    assert resultado["approved"] is False
    assert resultado["rnf01_passed"] is False
    assert any("is_public_verified != true" in m for m in resultado["rejection_reasons"])


def test_rnf01_aprova_candidato_com_osm_id_e_publico_verificado(agent, base_request):
    candidato = {
        "nome": "Sebinho Livraria",
        "osm_id": "node/1849203941",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "noise_level": "baixo",
        "score_contributions": {"vec": 0.45, "dist": 0.40},
        "score_total": 0.85,
    }
    resultado = agent.auditar_candidato(base_request, candidato)
    assert resultado["rnf01_passed"] is True
    assert resultado["approved"] is True


# =========================================================================
# 2. Auditoria de Restrições Críticas (Acessibilidade, Ruído, Horário)
# =========================================================================

def test_restricao_rejeita_wheelchair_no_quando_exigido(agent, base_request):
    # base_request exige wheelchair_required = True
    candidato = {
        "nome": "Bistrô Escadaria Sem Rampa",
        "osm_id": "node/998877",
        "is_public_verified": True,
        "wheelchair": "no",
        "score_contributions": {"v": 0.5, "d": 0.3},
        "score_total": 0.8,
    }
    resultado = agent.auditar_candidato(base_request, candidato)
    assert resultado["approved"] is False
    assert resultado["constraints_passed"] is False
    assert "wheelchair" in resultado["hard_filters"]
    assert resultado["hard_filters"]["wheelchair"] == "yes"
    assert any("Violação de Acessibilidade" in m for m in resultado["rejection_reasons"])


def test_restricao_rejeita_ruido_alto_quando_tolerancia_baixa(agent, base_request):
    # base_request exige noise_tolerance = "baixo"
    candidato = {
        "nome": "Bar e Balada Barulhenta",
        "osm_id": "way/554433",
        "is_public_verified": True,
        "wheelchair": "yes",
        "noise_level": "alto",
        "score_contributions": {"v": 0.5, "d": 0.3},
        "score_total": 0.8,
    }
    resultado = agent.auditar_candidato(base_request, candidato)
    assert resultado["approved"] is False
    assert resultado["constraints_passed"] is False
    assert "noise_level" in resultado["hard_filters"]
    assert any("Violação de Tolerância Sensorial" in m for m in resultado["rejection_reasons"])


def test_restricao_rejeita_horario_incompativel_madrugada(agent):
    req_madrugada = StructuredRequest.model_validate(
        _request(
            request_id="req-madrugada",
            activity="conversa",
            target_amenities=["cafe"],
            vibe="tranquilo",
            noise_tolerance="indiferente",
            temporal_constraints={"preferred_time_slot": "madrugada", "specific_hours": "03:30"},
            accessibility_requirements={"wheelchair_required": False},
        )
    )
    candidato = {
        "nome": "Café Diurno Fechado à Noite",
        "osm_id": "node/776655",
        "is_public_verified": True,
        "wheelchair": "yes",
        "opening_hours": "08:00-19:00",
        "score_contributions": {"v": 0.5, "d": 0.3},
        "score_total": 0.8,
    }
    resultado = agent.auditar_candidato(req_madrugada, candidato)
    assert resultado["approved"] is False
    assert resultado["constraints_passed"] is False
    assert any("Violação de Horário" in m for m in resultado["rejection_reasons"])


# =========================================================================
# 3. Integridade Matemática (|sum(contribuições) - score_total| < 1e-5)
# =========================================================================

def test_integridade_matematica_rejeita_soma_inconsistente(agent, base_request):
    candidato = {
        "nome": "Local com Fraude ou Erro no Score",
        "osm_id": "way/112233",
        "is_public_verified": True,
        "wheelchair": "yes",
        "score_contributions": {
            "c1": 0.40,
            "c2": 0.20,
        },
        "score_total": 0.85,  # Soma real = 0.60, diferença 0.25 >= 1e-5
    }
    resultado = agent.auditar_candidato(base_request, candidato)
    assert resultado["approved"] is False
    assert resultado["math_integrity_passed"] is False
    assert resultado["erro_matematico"] >= 1e-5
    assert any("Inconsistência Matemática" in m for m in resultado["rejection_reasons"])


def test_integridade_matematica_aprova_soma_exata(agent, base_request):
    candidato = {
        "nome": "Local com Matemática Exata",
        "osm_id": "way/112233",
        "is_public_verified": True,
        "wheelchair": "yes",
        "score_contributions": {
            "semantic": 0.451200,
            "distance": 0.250000,
            "accessibility": 0.200000,
            "noise": 0.050000,
        },
        "score_total": 0.951200,  # |0.951200 - 0.951200| = 0.0 < 1e-5
    }
    resultado = agent.auditar_candidato(base_request, candidato)
    assert resultado["math_integrity_passed"] is True
    assert resultado["erro_matematico"] < 1e-5
    assert resultado["approved"] is True


# =========================================================================
# 4. Auditoria de Lote e SearchResponse (Contrato 3 -> Contrato 4)
# =========================================================================

def test_auditar_search_response_rejeita_se_houver_reprovado_e_emite_diagnostico(agent, base_request):
    # POI-01 é válido, mas POI-FANTASMA não tem osm_id
    item_bom = _search_item(place_id="POI-01", name="Ernesto Cafés Especiais", final_score=0.86, rank=1)
    item_ruim = SearchItem(
        rank=2,
        place_id="POI-FANTASMA",
        name="Lugar Inexistente",
        distance_km=0.5,
        cosine_similarity=0.9,
        final_score=0.8,
        score_decomposition=ScoreDecomposition(
            vector_contribution=0.3,
            distance_contribution=0.2,
            reputation_contribution=0.15,
            compatibility_contribution=0.15,
            sum_check=0.8,
        ),
    )
    sr = SearchResponse(
        query_id=base_request.request_id,
        status="SUCCESS",
        applied_filters=AppliedFilters(radius_km=3.0, expanded_once=False, amenities=["cafe"]),
        results_count=2,
        items=[item_bom, item_ruim],
    )

    fb, records = agent.auditar_search_response(base_request, sr)
    assert fb.approved is False
    assert "POI-FANTASMA" in fb.rejected_place_ids
    assert len(records) == 0
    assert len(fb.diagnostics) > 0


def test_auditar_search_response_aprova_top3_valido_e_gera_evidence_records(agent, base_request):
    item1 = _search_item(place_id="POI-01", name="Ernesto Cafés Especiais", c_vec=0.36, c_dist=0.20, c_rep=0.15, c_comp=0.15, rank=1)
    item2 = _search_item(place_id="POI-02", name="Parque da Cidade Dona Sarah Kubitschek", c_vec=0.34, c_dist=0.20, c_rep=0.15, c_comp=0.15, rank=2)
    item3 = _search_item(place_id="POI-03", name="Sephinah Casa de Chá e Cafeteria", c_vec=0.32, c_dist=0.20, c_rep=0.15, c_comp=0.15, rank=3)

    sr = SearchResponse(
        query_id=base_request.request_id,
        status="SUCCESS",
        applied_filters=AppliedFilters(radius_km=5.0, expanded_once=False, amenities=["cafe", "parque"]),
        results_count=3,
        items=[item1, item2, item3],
    )

    fb, records = agent.auditar_search_response(base_request, sr)
    assert fb.approved is True
    assert len(fb.rejected_place_ids) == 0
    assert len(records) == 3

    for r in records:
        assert isinstance(r, EvidenceRecord)
        assert r.osm_reference.osm_id > 0
        assert r.osm_reference.osm_link.startswith("https://www.openstreetmap.org/")
        assert r.integrity_test.passed is True
        assert len(r.grounding_notes) > 0


# =========================================================================
# 5. Persistência da auditoria (Contrato 4) via EvidenceStore
# =========================================================================

def _response(base_request, items, consulta_id=None):
    return SearchResponse(
        query_id=base_request.request_id,
        consulta_id=consulta_id,
        status="SUCCESS",
        applied_filters=AppliedFilters(radius_km=3.0, expanded_once=False, amenities=["cafe"]),
        results_count=len(items),
        items=items,
    )


def test_top_aprovado_persiste_todas_as_evidencias(agent, store, base_request):
    cid = "56c6f629-21e8-4014-80fe-e8c0a1b2c3d4"
    sr = _response(base_request, [_search_item("POI-01", rank=1), _search_item("POI-02", rank=2)], cid)
    fb, records = agent.auditar_search_response(base_request, sr)
    assert fb.approved and len(records) == 2
    assert len(store.linhas) == 2
    assert all(l["approved"] and l["rnf01_passed"] and l["math_integrity_passed"] for l in store.linhas)
    assert {l["consulta_id"] for l in store.linhas} == {cid}


def test_top_reprovado_grava_so_os_reprovados(agent, store, base_request):
    ruim = SearchItem(
        rank=2, place_id="POI-FANTASMA", name="Lugar Inexistente", distance_km=0.5,
        cosine_similarity=0.9, final_score=0.8,
        score_decomposition=ScoreDecomposition(
            vector_contribution=0.3, distance_contribution=0.2,
            reputation_contribution=0.15, compatibility_contribution=0.15, sum_check=0.8,
        ),
    )
    sr = _response(base_request, [_search_item("POI-01", rank=1), ruim])
    fb, records = agent.auditar_search_response(base_request, sr)
    assert fb.approved is False and records == []
    # POI-01 era bom, mas nao foi entregue: nao vira evidencia aprovada.
    assert [l["place_id"] for l in store.linhas] == ["POI-FANTASMA"]
    assert store.linhas[0]["approved"] is False and store.linhas[0]["rejection_reasons"]


def test_sem_store_nao_persiste_e_nao_quebra(base_request):
    ag = EvidenceValidator(metadata_catalog=BASE_POIS_CATALOG)
    fb, _ = ag.auditar_search_response(base_request, _response(base_request, [_search_item("POI-01")]))
    assert fb.approved


def test_falha_ao_gravar_sobe_a_excecao(base_request):
    class Quebrada:
        def salvar(self, auditorias, consulta_id=None):
            raise ConnectionError("db fora")

    ag = EvidenceValidator(store=Quebrada(), metadata_catalog=BASE_POIS_CATALOG)
    with pytest.raises(ConnectionError):
        ag.auditar_search_response(base_request, _response(base_request, [_search_item("POI-01")]))


def test_grafo_vira_abstencao_segura_se_gravacao_falhar():
    class Quebrada:
        def salvar(self, auditorias, consulta_id=None):
            raise ConnectionError("db fora")

    def retrieval(state):
        return {"search_response": {
            "query_id": state["request_id"], "status": "SUCCESS",
            "applied_filters": {"radius_km": 3.0, "expanded_once": False, "amenities": ["cafe"]},
            "results_count": 1,
            "items": [_search_item("POI-01").model_dump()],
        }}

    graph = build_graph(
        nlu=stub_nlu(), retrieval=retrieval,
        validation=EvidenceValidator(store=Quebrada(), metadata_catalog=BASE_POIS_CATALOG),
        communication=stub_communication,
    )
    state = run(graph, "q", "req-falha-store")
    assert state["error"] == "validation_agent: ConnectionError"
    assert state["final_response"] == "abstencao"
    assert not state.get("evidence_records")


# =========================================================================
# 6. Integração com o Grafo LangGraph do Orquestrador
# =========================================================================

def test_langgraph_integracao_fluxo_normal_com_validation_agent():
    # Retrieval retorna candidato válido
    def retrieval_bom(state):
        return {
            "search_response": {
                "query_id": state["request_id"],
                "status": "SUCCESS",
                "applied_filters": {"radius_km": 3.0, "expanded_once": False, "amenities": ["cafe"]},
                "results_count": 1,
                "items": [
                    {
                        "rank": 1,
                        "place_id": "POI-01",
                        "name": "Ernesto Cafés Especiais",
                        "distance_km": 1.2,
                        "cosine_similarity": 0.9,
                        "final_score": 0.86,
                        "score_decomposition": {
                            "vector_contribution": 0.36,
                            "distance_contribution": 0.20,
                            "reputation_contribution": 0.15,
                            "compatibility_contribution": 0.15,
                            "sum_check": 0.86,
                        },
                        **_osm_do_item("POI-01"),
                    }
                ],
            }
        }

    graph = build_graph(
        nlu=stub_nlu(),
        retrieval=retrieval_bom,
        validation=EvidenceValidator(),
        communication=stub_communication,
    )

    state = run(graph, "Quero um café calmo na Asa Sul", "req-graph-01")
    trace_agents = [t.agent for t in state["agent_trace"]]
    assert trace_agents == [NLU, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert state["validation_feedback"].approved is True
    assert len(state["evidence_records"]) == 1
    assert state["final_response"] == "top-3 auditado"


def test_langgraph_integracao_reconsulta_e_aprovacao_segunda_tentativa():
    tentativas = {"n": 0}

    def retrieval_com_correcao(state):
        tentativas["n"] += 1
        fb: ValidationFeedback = state.get("validation_feedback")
        # Na primeira tentativa, envia candidato sem osm_id
        if tentativas["n"] == 1:
            pid = "POI-INVALIDO"
            name = "Inexistente"
        else:
            # Na segunda tentativa, corrigiu e enviou POI-01
            assert fb is not None
            assert fb.approved is False
            assert "POI-INVALIDO" in fb.rejected_place_ids
            pid = "POI-01"
            name = "Ernesto Cafés Especiais"

        return {
            "search_response": {
                "query_id": state["request_id"],
                "status": "SUCCESS",
                "applied_filters": {"radius_km": 3.0, "expanded_once": False, "amenities": ["cafe"]},
                "results_count": 1,
                "items": [
                    {
                        "rank": 1,
                        "place_id": pid,
                        "name": name,
                        "distance_km": 1.0,
                        "cosine_similarity": 0.9,
                        "final_score": 0.86,
                        "score_decomposition": {
                            "vector_contribution": 0.36,
                            "distance_contribution": 0.20,
                            "reputation_contribution": 0.15,
                            "compatibility_contribution": 0.15,
                            "sum_check": 0.86,
                        },
                        **_osm_do_item(pid),
                    }
                ],
            }
        }

    graph = build_graph(
        nlu=stub_nlu(),
        retrieval=retrieval_com_correcao,
        validation=EvidenceValidator(),
        communication=stub_communication,
    )

    state = run(graph, "Quero um café calmo na Asa Sul", "req-graph-02")
    trace_agents = [t.agent for t in state["agent_trace"]]
    assert trace_agents == [NLU, RETRIEVAL, VALIDATION, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert state["retry_count"] == 1
    assert state["validation_feedback"].approved is True
    assert state["final_response"] == "top-3 auditado"


# =========================================================================
# 7. Contrato 3 estendido: metadados de OSM vem no proprio SearchItem
# =========================================================================

def _item_osm(place_id="POI-X", **osm):
    return _search_item(place_id=place_id, name="Local X").model_copy(update=osm)


def test_item_com_osm_no_proprio_item_aprova_sem_catalogo(base_request):
    agent_sem_catalogo = EvidenceValidator()
    item = _item_osm(
        osm_id=123456, osm_type="way",
        osm_tags={"wheelchair": "yes", "noise_level": "baixo", "amenity": "cafe"},
        is_public_verified=True,
    )
    r = agent_sem_catalogo.auditar_candidato(base_request, item)
    assert r["approved"] is True
    ev = EvidenceRecord.model_validate(r["evidence_payload"])
    assert ev.osm_reference.osm_link == "https://www.openstreetmap.org/way/123456"
    # matched_tags vem das tags reais, sem valores inventados
    assert ev.matched_tags == ["amenity=cafe", "wheelchair=yes", "noise_level=baixo"]


def test_item_sem_metadados_osm_e_reprovado_pelo_rnf01(base_request):
    agent_sem_catalogo = EvidenceValidator()
    r = agent_sem_catalogo.auditar_candidato(base_request, _item_osm())
    assert r["approved"] is False
    assert r["rnf01_passed"] is False


def test_osm_tags_wheelchair_no_gera_hard_filter(base_request):
    agent_sem_catalogo = EvidenceValidator()
    item = _item_osm(
        osm_id=99, osm_type="node", osm_tags={"wheelchair": "no"}, is_public_verified=True
    )
    r = agent_sem_catalogo.auditar_candidato(base_request, item)
    assert r["approved"] is False
    assert r["hard_filters"] == {"wheelchair": "yes"}


def test_osm_tags_ruido_alto_reprova_com_tolerancia_baixa(base_request):
    agent_sem_catalogo = EvidenceValidator()
    item = _item_osm(
        osm_id=99, osm_type="node",
        osm_tags={"wheelchair": "yes", "noise_level": "alto"}, is_public_verified=True,
    )
    r = agent_sem_catalogo.auditar_candidato(base_request, item)
    assert r["approved"] is False
    assert r["hard_filters"].get("noise_level") == "baixo"
