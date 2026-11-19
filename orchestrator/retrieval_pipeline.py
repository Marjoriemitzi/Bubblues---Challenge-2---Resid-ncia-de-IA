"""RetrievalPipeline: busca determinística (sem LLM) que alimenta o grafo.

Antes chamava-se RetrievalAgent; "agente" agora e so o que usa LLM. O nome `retrieval_agent` fica
reservado para o agente LLM (Fase D do plano).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .contracts import SearchResponse
from .retrieval_common import (
    K_PADRAO,
    _pipeline,
    montar_parametros,
    registro_para_search_response,
    resolver_local_padrao,
    texto_do_embedding,
)
from .state import AgentState

# --------------------------------------------------------------------------
# O agente
# --------------------------------------------------------------------------
class RetrievalPipeline:
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
            raise ValueError("retrieval: structured_request ausente no estado")

        if None in (self._conexao_factory, self._buscar_fn, self._embedder):
            self._padroes()

        params = montar_parametros(req, state.get("validation_feedback"), self.k)
        rejeitados = params.pop("rejeitados")
        regiao = req.spatial_constraints.target_region

        with self._conexao_factory() as conexao:
            local = self._resolver_local(regiao, conexao)
            if local is None:
                return self._pedir_esclarecimento(state, req, regiao, params["tipos"])
            lat, lon = local
            # Depois da regiao: nao carrega o modelo de embeddings a toa quando vai pedir esclarecimento.
            embedding = self._embedder(texto_do_embedding(req))
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


_default_pipeline: Optional[RetrievalPipeline] = None


def retrieval_pipeline(state: AgentState) -> Dict[str, Any]:
    """Funcao de agente pronta para `build_graph` (usa PostgreSQL do .env)."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = RetrievalPipeline()
    return _default_pipeline(state)
