"""Retrieval_Agent do Bubbles: adapta a busca hibrida (PostGIS + pgvector) ao grafo.

Papel: traduzir o `structured_request` (Contrato 2) em parametros de `busca.buscar`
e devolver o resultado como `search_response` (Contrato 3).

    structured_request ──► [montar_parametros] ──► busca.buscar (PostgreSQL) ──► [registro_para_search_response]
    validation_feedback ──┘                                                       └──► search_response

Pontos de atencao:
  - A busca e feita no PostgreSQL com PostGIS + pgvector (OSM do DF). Nao ha catalogo em codigo.
  - Reconsulta: `hard_filters` do Validation_Agent viram filtros rigidos da proxima busca e
    `rejected_place_ids` sao excluidos do resultado.
  - RNF02: o texto livre do usuario nunca chega aqui (o orquestrador zera `raw_query`). O embedding
    vem so de campos estruturados (activity, vibe, search_vector_focus).
  - Localizacao: `target_region` -> (lat, lon) usa a tabela `regioes` (OSM do DF) via `resolver_local`.
    Regiao nao encontrada NAO e chutada: o agente devolve NO_RESULTS e preenche
    `structured_request.clarification_needed`, e o Communication_Agent pergunta ao usuario.

Dependencias pesadas (psycopg, sentence-transformers) sao carregadas so quando necessarias, e todas
podem ser injetadas, entao os testes rodam sem banco.
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
        "status": status,
        "applied_filters": {
            "radius_km": registro["raio"]["final_m"] / 1000,
            "expanded_once": bool(ampliado),
            "amenities": list(tipos or []),
        },
        "results_count": len(items),
        "items": items,
    }


# --------------------------------------------------------------------------
# O agente
# --------------------------------------------------------------------------
class RetrievalAgent:
    """Callable `AgentState -> dict`, injetavel em `build_graph`.

    Todos os colaboradores sao injetaveis (teste sem banco):
      conexao_factory: () -> context manager de conexao (padrao: busca.conectar)
      embedder:        (texto) -> list[float] de 768 dims (padrao: gerar_embedding_consulta)
      resolver_local:  (target_region, conexao) -> (lat, lon) ou None se a regiao nao existe
      buscar_fn:       (conexao, lat, lon, embedding, **kw) -> registro (padrao: busca.buscar)
    """

    def __init__(
        self,
        conexao_factory: Optional[Callable[[], Any]] = None,
        embedder: Optional[Callable[[str], List[float]]] = None,
        resolver_local: Callable[[Optional[str], Any], Optional[Tuple[float, float]]] = resolver_local_padrao,
        buscar_fn: Optional[Callable[..., dict]] = None,
        k: int = K_PADRAO,
    ):
        self._conexao_factory = conexao_factory
        self._embedder = embedder
        self._resolver_local = resolver_local
        self._buscar_fn = buscar_fn
        self._modelo = None
        self.k = k

    def _padroes(self):
        busca, emb, _ = _pipeline()
        self._conexao_factory = self._conexao_factory or busca.conectar
        self._buscar_fn = self._buscar_fn or busca.buscar
        if self._embedder is None:
            def embedder(texto: str) -> List[float]:
                if self._modelo is None:
                    self._modelo = emb.carregar_modelo()
                return emb.gerar_embedding_consulta(texto, self._modelo)

            self._embedder = embedder

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        req = state.get("structured_request")
        if req is None:
            raise ValueError("retrieval_agent: structured_request ausente no estado")

        if None in (self._conexao_factory, self._buscar_fn, self._embedder):
            self._padroes()

        params = montar_parametros(req, state.get("validation_feedback"), self.k)
        embedding = self._embedder(texto_do_embedding(req))
        rejeitados = params.pop("rejeitados")
        regiao = req.spatial_constraints.target_region

        with self._conexao_factory() as conexao:
            local = self._resolver_local(regiao, conexao)
            if local is None:
                return self._pedir_esclarecimento(state, req, regiao, params["tipos"])
            lat, lon = local
            registro = self._buscar_fn(
                conexao,
                lat,
                lon,
                embedding,
                # Pede k extra para repor os candidatos que o validador ja reprovou.
                **{**params, "k": params["k"] + len(rejeitados)},
            )

        resposta = registro_para_search_response(
            registro, state["request_id"], params["tipos"], rejeitados, self.k
        )
        # Valida o contrato aqui tambem, para o erro apontar o Retrieval e nao o orquestrador.
        n = SearchResponse.model_validate(resposta).results_count
        return {
            "search_response": resposta,
            "note": f"{n} candidato(s); status={resposta['status']}; consulta_id={registro['consulta_id']}",
        }


    @staticmethod
    def _pedir_esclarecimento(state, req, regiao, tipos) -> Dict[str, Any]:
        """Regiao fora da base: nao busca em lugar nenhum e devolve a pergunta ao usuario."""
        pergunta = (
            f"Nao encontrei a regiao '{regiao}' no Distrito Federal. "
            "Pode indicar outra regiao administrativa ou bairro (ex.: Asa Sul, Aguas Claras)?"
        )
        return {
            "structured_request": req.model_copy(update={"clarification_needed": pergunta}),
            "search_response": {
                "query_id": state["request_id"],
                "status": "NO_RESULTS",
                "applied_filters": {
                    "radius_km": req.spatial_constraints.max_radius_km,
                    "expanded_once": False,
                    "amenities": list(tipos or []),
                },
                "results_count": 0,
                "items": [],
            },
            "note": "regiao nao encontrada na tabela regioes: pedindo esclarecimento",
        }


_default_agent: Optional[RetrievalAgent] = None


def retrieval_agent(state: AgentState) -> Dict[str, Any]:
    """Funcao de agente pronta para `build_graph` (usa PostgreSQL do .env)."""
    global _default_agent
    if _default_agent is None:
        _default_agent = RetrievalAgent()
    return _default_agent(state)
