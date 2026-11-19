"""Agentes de mentira (stubs) para exercitar o orquestrador antes das issues #7-#10.

Cada stub segue o mesmo formato que o agente real tera: recebe o estado e
devolve um dict parcial. Quando o agente real ficar pronto, basta passa-lo
para `build_graph` no lugar do stub.
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


def stub_retrieval(state):
    rid = state["request_id"]
    fb = state.get("validation_feedback")
    rejected = set(fb.rejected_place_ids) if fb else set()
    pid = "POI-02" if "POI-01" in rejected else "POI-01"
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
        # Metadados de OSM como o Retrieval real os devolveria (ids ficticios de teste).
        "osm_id": 1 if pid == "POI-01" else 2,
        "osm_type": "node",
        "osm_tags": {"wheelchair": "yes", "noise_level": "baixo"},
        "is_public_verified": True,
    }
    return {
        "search_response": {
            "query_id": rid,
            "status": "SUCCESS",
            "applied_filters": {"radius_km": 5.0, "expanded_once": False, "amenities": ["cafe"]},
            "results_count": 1,
            "items": [item],
        },
        "note": f"stub retrieval -> {pid}",
    }


def stub_validation(approve_on_attempt: int | None = 1):
    """Aprova na N-esima chamada; None = reprova sempre (testa a trava de retries)."""
    calls = {"n": 0}

    def agent(state):
        calls["n"] += 1
        ok = approve_on_attempt is not None and calls["n"] >= approve_on_attempt
        if ok:
            fb = ValidationFeedback(approved=True)
            records = [
                {
                    "evidence_id": f"EV-{uuid.uuid4().hex[:8]}",
                    "query_id": state["request_id"],
                    "place_id": "POI-02" if calls["n"] > 1 else "POI-01",
                    "place_name": "Local",
                    "osm_reference": {"osm_id": 1, "osm_type": "node", "osm_link": "https://www.openstreetmap.org/node/1"},
                    "matched_tags": ["cafe"],
                    "factors": [],
                    "total_score": 0.8,
                    "integrity_test": {"sum_equals_total": True, "all_factors_in_range_0_1": True, "passed": True},
                    "grounding_notes": ["wheelchair=yes"],
                }
            ]
            return {"validation_feedback": fb, "evidence_records": records, "note": "stub aprovou"}
        fb = ValidationFeedback(
            approved=False,
            rejected_place_ids=["POI-01"],
            hard_filters={"wheelchair": "yes"},
            diagnostics=["wheelchair=no viola wheelchair_required"],
        )
        return {"validation_feedback": fb, "note": "stub reprovou"}

    return agent


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
