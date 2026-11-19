
from orchestrator.communication import communication_agent


def make_state(profile="carla_mendes"):
    return {
        "user_profile": profile,
        "structured_request": {
            "intent_valid": True,
            "out_of_scope": False,
            "impossible_criteria": False,
            "activity": "café",
            "clarification_needed": None,
        },
        "search_response": {
            "items": [
                {
                    "place_id": "1",
                    "name": "Café Central",
                    "address": "Asa Sul",
                    "distance_km": 1.2,
                },
                {
                    "place_id": "2",
                    "name": "Espaço Verde",
                    "address": "Asa Norte",
                    "distance_km": 2.5,
                },
                {
                    "place_id": "3",
                    "name": "Praça Cultural",
                    "address": "Plano Piloto",
                    "distance_km": 3.0,
                },
            ]
        },
        "evidence_records": [
            {
                "place_id": "1",
                "place_name": "Café Central",
                "total_score": 0.95,
                "matched_tags": ["amenity=cafe"],
                "grounding_notes": ["Possui área de convivência."],
                "integrity_test": {"passed": True},
            },
            {
                "place_id": "2",
                "place_name": "Espaço Verde",
                "total_score": 0.85,
                "matched_tags": ["leisure=park"],
                "grounding_notes": ["Possui área verde."],
                "integrity_test": {"passed": True},
            },
            {
                "place_id": "3",
                "place_name": "Praça Cultural",
                "total_score": 0.75,
                "matched_tags": ["leisure=common"],
                "grounding_notes": ["Possui espaço público."],
                "integrity_test": {"passed": True},
            },
        ],
    }


def test_communication_presents_top_three():
    result = communication_agent(make_state())

    assert "Café Central" in result["final_response"]
    assert "Espaço Verde" in result["final_response"]
    assert "Praça Cultural" in result["final_response"]
    assert "1.20 km" in result["final_response"]


def test_communication_adapts_to_dona_helena():
    result = communication_agent(make_state("dona_helena"))

    assert "com calma" in result["final_response"]
    assert "Por que foi recomendado" in result["final_response"]


def test_communication_abstains_without_evidence():
    state = make_state()
    state["evidence_records"] = []

    result = communication_agent(state)

    assert "Não encontrei locais" in result["final_response"]


def test_communication_ignores_evidence_without_approval():
    state = make_state()
    state["evidence_records"][0]["integrity_test"]["passed"] = False

    result = communication_agent(state)

    assert "Café Central" not in result["final_response"]

