"""Funcoes compartilhadas do Retrieval (determinístico e, depois, o agente LLM).

Contrato 2 (+ feedback) -> parametros de busca; resultado de busca.buscar -> Contrato 3; acesso ao
data-pipeline/. Nada aqui usa LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .contracts import SearchResponse, StructuredRequest, ValidationFeedback
from .state import AgentState

K_PADRAO = 3
CENTRO_BRASILIA = (-15.7939, -47.8828)
_PIPELINE_DIR = Path(__file__).resolve().parent.parent / "data-pipeline"


def resolver_local_padrao(regiao: Optional[str], conexao) -> Optional[Tuple[float, float]]:
    """(lat, lon) da regiao pedida, ou None se nao existir. Sem regiao: centro de Brasilia."""
    if not regiao:
        return CENTRO_BRASILIA
    _, _, regioes = _pipeline()
    achado = regioes.resolver_regiao(conexao, regiao)
    return (achado[0], achado[1]) if achado else None


def _pipeline():
    """Importa busca.py/gerar_embeddings.py (modulos 'planos' de data-pipeline/) sob demanda."""
    if str(_PIPELINE_DIR) not in sys.path:
        sys.path.insert(0, str(_PIPELINE_DIR))
    import busca  # noqa: PLC0415
    import gerar_embeddings  # noqa: PLC0415
    import regioes  # noqa: PLC0415

    return busca, gerar_embeddings, regioes


# --------------------------------------------------------------------------
# Contrato 2 (+ feedback) -> parametros de busca.buscar
# --------------------------------------------------------------------------
def texto_do_embedding(req: StructuredRequest) -> str:
    """Texto semantico da consulta, montado so com campos estruturados (RNF02)."""
    partes = [req.activity, f"vibe: {req.vibe}", *req.search_vector_focus, *req.target_amenities]
    return ". ".join(p for p in partes if p)


def montar_parametros(
    req: StructuredRequest,
    feedback: Optional[ValidationFeedback],
    k: int = K_PADRAO,
) -> Dict[str, Any]:
    """Converte o pedido (e o feedback do validador) nos argumentos de `buscar`."""
    etiquetas: Dict[str, str] = {}
    tolerancia = req.noise_tolerance

    if req.accessibility_requirements.wheelchair_required:
        etiquetas["wheelchair"] = "yes"

    rejeitados: List[str] = []
    if feedback is not None and not feedback.approved:
        rejeitados = list(feedback.rejected_place_ids)
        hf = feedback.hard_filters
        if hf.get("wheelchair") == "yes":
            etiquetas["wheelchair"] = "yes"
        if hf.get("noise_level") in ("baixo", "moderado"):
            # So endurece: nunca afrouxa a tolerancia pedida pelo usuario.
            if tolerancia == "indiferente" or hf["noise_level"] == "baixo":
                tolerancia = hf["noise_level"]
        # preferred_time_slot / specific_hours / elder_friendly: a busca nao filtra por
        # horario nem por idoso; a auditoria continua barrando esses casos.

    return {
        "raio_m": req.spatial_constraints.max_radius_km * 1000,
        "tipos": list(req.target_amenities) or None,
        "k": k,
        "etiquetas_desejadas": etiquetas,
        "tolerancia_sensorial": tolerancia,
        "rejeitados": rejeitados,
    }


# --------------------------------------------------------------------------
# Resultado de busca.buscar (dict em portugues) -> Contrato 3
# --------------------------------------------------------------------------
def _fator(resultado: dict, nome: str) -> dict:
    return next(f for f in resultado["fatores"] if f["nome"] == nome)


def registro_para_search_response(
    registro: dict,
    request_id: str,
    tipos: Optional[List[str]],
    rejeitados: Optional[List[str]] = None,
    k: int = K_PADRAO,
) -> dict:
    """Traduz o registro da busca para o dict do Contrato 3 (validado depois pelo orquestrador)."""
    rejeitados_set = {str(r) for r in rejeitados or []}
    resultados = [r for r in registro["resultados"] if str(r["local"]["place_id"]) not in rejeitados_set][:k]

    items = []
    for posicao, r in enumerate(resultados, start=1):
        contrib = {f["nome"]: f["contribuicao"] for f in r["fatores"]}
        osm = r.get("osm") or {}
        items.append(
            {
                "rank": posicao,
                "place_id": str(r["local"]["place_id"]),
                "name": r["local"]["nome"],
                "amenity": r["local"].get("categoria"),
                "distance_km": r["local"]["distancia_m"] / 1000,
                "cosine_similarity": _fator(r, "similaridade")["valor"],
                "final_score": r["score_total"],
                "score_decomposition": {
                    "vector_contribution": contrib["similaridade"],
                    "distance_contribution": contrib["distancia"],
                    "reputation_contribution": contrib["reputacao"],
                    "compatibility_contribution": contrib["compatibilidade"],
                    "sum_check": sum(contrib.values()),
                },
                "osm_id": osm.get("osm_id"),
                "osm_type": osm.get("osm_type"),
                "osm_tags": {str(c): str(v) for c, v in (osm.get("tags") or {}).items()},
                # `places` so contem estabelecimentos publicos extraidos do OSM, e a busca ja
                # exige osm_id/osm_type. Sem osm_id nao ha verificacao possivel.
                "is_public_verified": bool(osm.get("osm_id") and osm.get("osm_type")),
            }
        )

    ampliado = registro["raio"]["ampliado"]
    if not items:
        status = "NO_RESULTS"
    elif ampliado:
        status = "EXPANDED_RADIUS"
    else:
        status = "SUCCESS"

    return {
        "query_id": request_id,
        "consulta_id": registro.get("consulta_id"),
        "status": status,
        "applied_filters": {
            "radius_km": registro["raio"]["final_m"] / 1000,
            "expanded_once": bool(ampliado),
            "amenities": list(tipos or []),
        },
        "results_count": len(items),
        "items": items,
    }
