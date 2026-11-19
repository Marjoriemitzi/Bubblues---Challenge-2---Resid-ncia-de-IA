"""Agentes de mentira (stubs) para exercitar o orquestrador sem banco nem LLM.

Cada stub segue o formato do componente real: recebe o estado e devolve um dict parcial. O Retrieval
devolve ja a busca, a auditoria (gate) e as evidencias; o laco de reconsulta e interno a ele.
"""

from __future__ import annotations

import uuid

from .contracts import ValidationFeedback


def _request(request_id: str, **over) -> dict:
    base = {
        "request_id": request_id,
        "intent_valid": True,
        "out_of_scope": False,
        "impossible_criteria": False,
        "activity": "conversa",
        "target_amenities": ["cafe"],
        "vibe": "tranquilo",
        "noise_tolerance": "baixo",
        "spatial_constraints": {"target_region": "Asa Sul", "max_radius_km": 3.0},
        "temporal_constraints": {"preferred_time_slot": "tarde"},
        "accessibility_requirements": {"wheelchair_required": True},
    }
    base.update(over)
    return base


def stub_nlu(**overrides):
    """Aceita o pedido por padrao; passe out_of_scope=True etc. para bloquear."""

    def agent(state):
        # O stub "le" o raw_query como o NLU real faria (e o orquestrador o descarta depois).
        _ = state["raw_query"]
        return {"structured_request": _request(state["request_id"], **overrides), "note": "stub nlu"}

    return agent


def _search_response(rid: str, pid: str = "POI-01") -> dict:
    item = {
        "rank": 1,
        "place_id": pid,
        "name": f"Local {pid}",
        "distance_km": 1.2,
        "cosine_similarity": 0.9,
        "final_score": 0.8,
        "score_decomposition": {
            "vector_contribution": 0.36,
            "distance_contribution": 0.19,
            "reputation_contribution": 0.12,
            "compatibility_contribution": 0.13,
            "sum_check": 0.8,
        },
        "osm_id": 1,
        "osm_type": "node",
        "osm_tags": {"wheelchair": "yes", "noise_level": "baixo"},
        "is_public_verified": True,
    }
    return {
        "query_id": rid,
        "status": "SUCCESS",
        "applied_filters": {"radius_km": 5.0, "expanded_once": False, "amenities": ["cafe"]},
        "results_count": 1,
        "items": [item],
    }


def stub_retrieval(state):
    """Retrieval de mentira com o contrato novo: ja devolve a busca, a auditoria e as evidencias."""
    rid = state["request_id"]
    evidencia = {
        "evidence_id": f"EV-{uuid.uuid4().hex[:8]}",
        "query_id": rid,
        "place_id": "POI-01",
        "place_name": "Local POI-01",
        "osm_reference": {"osm_id": 1, "osm_type": "node", "osm_link": "https://www.openstreetmap.org/node/1"},
        "matched_tags": ["wheelchair=yes"],
        "factors": [],
        "total_score": 0.8,
        "integrity_test": {"sum_equals_total": True, "all_factors_in_range_0_1": True, "passed": True},
        "grounding_notes": ["wheelchair=yes"],
    }
    return {
        "search_response": _search_response(rid),
        "validation_feedback": ValidationFeedback(approved=True),
        "evidence_records": [evidencia],
        "retry_count": 0,
        "note": "stub retrieval: aprovado",
    }


def stub_retrieval_reprovado(state):
    """Retrieval cujo gate reprova ate esgotar as reconsultas: sem evidencias, vai para a abstencao."""
    return {
        "search_response": _search_response(state["request_id"]),
        "validation_feedback": ValidationFeedback(
            approved=False,
            rejected_place_ids=["POI-01"],
            hard_filters={"wheelchair": "yes"},
            diagnostics=["wheelchair=no viola wheelchair_required"],
        ),
        "retry_count": 2,
        "note": "stub retrieval: reprovado pelo gate",
    }


def stub_communication(state):
    req = state.get("structured_request")
    if req is None or state.get("error"):  # NLU falhou ou outro agente caiu
        return {"final_response": "abstencao", "note": "abstencao por falha"}
    if not req.intent_valid:
        return {"final_response": "abstencao", "note": "modo abstencao"}
    if req.clarification_needed:
        return {"final_response": req.clarification_needed, "note": "modo esclarecimento"}
    if state.get("evidence_records"):
        return {"final_response": "top-3 auditado", "note": "modo recomendacao"}
    return {"final_response": "abstencao", "note": "abstencao apos falhas de validacao"}
