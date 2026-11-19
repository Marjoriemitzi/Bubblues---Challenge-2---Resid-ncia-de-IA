
def _get(obj, key, default=None):
    """Acessa campos de dicionários ou modelos Pydantic."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _format_metadata(value):
    """Formata metadados existentes, sem criar características."""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value) if value is not None else ""


def _get_profile(state):
    profile = str(state.get("user_profile", "")).lower()

    if "helena" in profile:
        return "helena"
    if "carla" in profile:
        return "carla"
    return "neutro"


def _build_justification(evidence, profile):
    notes = _get(evidence, "grounding_notes", []) or []
    tags = _get(evidence, "matched_tags", []) or []

    parts = [str(note) for note in notes if note]

    if tags:
        parts.append(
            "Características registradas no OpenStreetMap: "
            + _format_metadata(tags)
        )

    if not parts:
        return "Não há detalhes adicionais registrados nas evidências."

    return " ".join(parts)


def communication_agent(state):
    """Apresenta recomendações auditadas e justificadas por evidências."""

    request = state.get("structured_request") or {}

    if _get(request, "out_of_scope", False):
        reason = _get(request, "out_of_scope_reason")
        return {
            "final_response": (
                f"Não consigo atender a esse pedido porque ele está fora "
                f"do escopo da busca. Motivo: {reason}. "
                "Tente buscar locais públicos ou estabelecimentos da região."
            )
        }

    if _get(request, "impossible_criteria", False):
        reason = _get(request, "impossible_criteria_reason")
        return {
            "final_response": (
                f"Não foi possível encontrar uma combinação viável dos "
                f"critérios solicitados. Motivo: {reason}. "
                "Você pode flexibilizar algum requisito ou ampliar a região."
            )
        }

    clarification = _get(request, "clarification_needed")
    if clarification:
        return {"final_response": str(clarification)}

    search_response = state.get("search_response") or {}
    items = _get(search_response, "items", []) or []
    evidence_records = state.get("evidence_records", []) or []

    # Somente evidências aprovadas na verificação de integridade.
    approved = [
        evidence for evidence in evidence_records
        if _get(_get(evidence, "integrity_test", {}), "passed", False)
    ]

    if not approved:
        return {
            "final_response": (
                "Não encontrei locais com evidências suficientes para "
                "recomendar com segurança. Você pode ampliar o raio da "
                "busca ou flexibilizar algum critério?"
            )
        }

    items_by_id = {
        _get(item, "place_id"): item
        for item in items
    }

    approved.sort(
        key=lambda evidence: float(_get(evidence, "total_score", 0) or 0),
        reverse=True
    )

    profile = _get_profile(state)

    if profile == "helena":
        introduction = (
            "Encontrei estas opções para você. "
            "Veja as informações com calma:"
        )
    elif profile == "carla":
        introduction = (
            "Separei os locais mais compatíveis com sua busca. "
            "Confira os destaques:"
        )
    else:
        introduction = "Confira os locais aprovados na validação:"

    response = [introduction]

    for position, evidence in enumerate(approved[:3], start=1):
        place_id = _get(evidence, "place_id")
        item = items_by_id.get(place_id)

        if item is None:
            continue

        name = _get(evidence, "place_name")
        address = _get(item, "address") or "Endereço não informado"
        distance = _get(item, "distance_km")

        if not name:
            continue

        distance_text = (
            f"{distance:.2f} km"
            if distance is not None
            else "Distância não informada"
        )

        justification = _build_justification(evidence, profile)
        osm_reference = _get(evidence, "osm_reference", {})
        osm_link = _get(osm_reference, "osm_link")

        if profile == "helena":
            place_text = (
                f"{position}. {name}\n"
                f"Endereço: {address}\n"
                f"Distância: {distance_text}\n"
                f"Por que foi recomendado: {justification}"
            )
        else:
            place_text = (
                f"{position}. {name}\n"
                f"Localização: {address}\n"
                f"Distância: {distance_text}\n"
                f"Destaques: {justification}"
            )

        if osm_link:
            place_text += f"\nFonte OSM: {osm_link}"

        response.append(place_text)

    if len(response) == 1:
        return {
            "final_response": (
                "Não foi possível relacionar as evidências aprovadas aos "
                "locais encontrados. Tente realizar uma nova busca."
            )
        }

    return {"final_response": "\n\n".join(response)}


