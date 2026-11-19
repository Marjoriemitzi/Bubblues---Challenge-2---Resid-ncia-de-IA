"""RetrievalPipeline: busca determinística (sem LLM) com auditoria obrigatória e reconsulta.

Faz TUDO o que o nó `retrieval` do grafo precisa, usando as mesmas tools que o agente LLM usará:

    regiao -> buscar_lugares -> GATE (EvidenceValidator) -> aprovado? entrega
                   ^                     |
                   +--- reconsulta com os filtros do feedback (ate MAX_RETRIES) --+

Saída (estado): search_response, evidence_records, validation_feedback, retry_count e note.
`retry_count` = reconsultas realizadas (0 = aprovado na primeira busca).

Antes chamava-se RetrievalAgent; "agente" agora é só o que usa LLM. O nome `retrieval_agent` fica
reservado para o agente LLM (Fase D do plano).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .contracts import SearchResponse, StructuredRequest
from .graph import MAX_RETRIES
from .retrieval_common import CENTRO_BRASILIA, K_PADRAO, texto_do_embedding
from .retrieval_gate import RetrievalGate
from .retrieval_tools import ContextoBusca, RetrievalTools
from .state import AgentState
from .validation_tool import EvidenceValidator

MAX_TEXTO_CONSULTA = 290


def _resposta_vazia(req: StructuredRequest, request_id: str, tipos: List[str]) -> Dict[str, Any]:
    return {
        "query_id": request_id,
        "status": "NO_RESULTS",
        "applied_filters": {
            "radius_km": req.spatial_constraints.max_radius_km,
            "expanded_once": False,
            "amenities": list(tipos or []),
        },
        "results_count": 0,
        "items": [],
    }


class RetrievalPipeline:
    """Callable `AgentState -> dict`, injetável em `build_graph`.

    Colaboradores injetáveis (testes sem banco): conexao_factory, embedder, buscar_fn, regioes_fn
    (as mesmas das tools) e `validator` (padrão: EvidenceValidator gravando no PostgreSQL).
    """

    def __init__(
        self,
        conexao_factory: Optional[Callable[[], Any]] = None,
        embedder: Optional[Callable[[str], List[float]]] = None,
        buscar_fn: Optional[Callable[..., dict]] = None,
        regioes_fn: Optional[Callable[..., list]] = None,
        validator: Optional[EvidenceValidator] = None,
        k: int = K_PADRAO,
        max_retries: int = MAX_RETRIES,
    ):
        self._conexao_factory = conexao_factory
        self._embedder = embedder
        self._buscar_fn = buscar_fn
        self._regioes_fn = regioes_fn
        self._validator = validator
        self.k = k
        self.max_retries = max_retries

    def _validador(self) -> EvidenceValidator:
        if self._validator is None:
            from .evidence_store import PostgresEvidenceStore  # noqa: PLC0415

            self._validator = EvidenceValidator(store=PostgresEvidenceStore(conexao_factory=self._conexao_factory))
        return self._validator

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        req = state.get("structured_request")
        if req is None:
            raise ValueError("retrieval: structured_request ausente no estado")

        validator = self._validador()
        contexto = ContextoBusca.de_pedido(req, state.get("validation_feedback"), self.k)
        tools = RetrievalTools(
            contexto, state["request_id"], conexao_factory=self._conexao_factory, embedder=self._embedder,
            buscar_fn=self._buscar_fn, regioes_fn=self._regioes_fn, req=req, validator=validator,
            max_buscas=self.max_retries + 1,
        )
        gate = RetrievalGate(validator)

        # 1. localizacao
        regiao = req.spatial_constraints.target_region
        if regiao:
            candidatas = tools.executar("resolver_regiao", {"nome": regiao}).get("regioes") or []
            if not candidatas:
                return self._pedir_esclarecimento(state, req, regiao)
            lat, lon = candidatas[0]["latitude"], candidatas[0]["longitude"]
        else:
            lat, lon = CENTRO_BRASILIA

        # 2. busca -> gate -> reconsulta
        reconsultas, ultima, resultado = 0, None, None
        for _ in range(self.max_retries + 1):
            r = tools.executar("buscar_lugares", {
                "latitude": lat, "longitude": lon, "raio_km": req.spatial_constraints.max_radius_km,
                "categorias": list(req.target_amenities), "k": self.k,
                "texto_consulta": texto_do_embedding(req)[:MAX_TEXTO_CONSULTA],
            })
            if "erro" in r:  # pedido que a base nao atende (ex.: nenhuma categoria existente)
                return self._sem_resultado(req, state, contexto, f"pedido nao atendivel pela base: {r['erro']}")
            ultima = tools.runlog.obter(r["busca_id"])
            if r["total"] == 0:
                if resultado is not None:  # ja houve reprovacao: nao sobrou candidato novo para repor
                    return {
                        "search_response": ultima.search_response,
                        "validation_feedback": resultado.feedback,
                        "retry_count": reconsultas,
                        "note": f"reprovado pelo gate e sem novos candidatos apos {reconsultas} reconsulta(s)",
                    }
                return self._sem_resultado(req, state, contexto, "busca sem candidatos", ultima.search_response)
            resultado = gate.auditar(req, ultima)
            if resultado.aprovado:
                break
            contexto.aplicar_feedback(resultado.feedback)  # rejeitados + hard_filters valem na proxima busca
            reconsultas += 1
        else:
            reconsultas = self.max_retries  # esgotou: a ultima reprovacao nao gerou nova busca
            return {
                "search_response": ultima.search_response,
                "validation_feedback": resultado.feedback,
                "retry_count": reconsultas,
                "note": f"reprovado pelo gate; reconsultas esgotadas ({reconsultas}); consulta_id={ultima.consulta_id}",
            }

        return {
            "search_response": resultado.search_response,
            "validation_feedback": resultado.feedback,
            "evidence_records": resultado.evidence_records,
            "retry_count": reconsultas,
            "note": f"{len(resultado.evidence_records)} aprovado(s); reconsultas={reconsultas}; consulta_id={ultima.consulta_id}",
        }

    # ------------------------------------------------------------------ desfechos sem entrega
    @staticmethod
    def _sem_resultado(req, state, contexto, motivo, resposta: Optional[dict] = None) -> Dict[str, Any]:
        resposta = resposta or _resposta_vazia(req, state["request_id"], list(req.target_amenities))
        SearchResponse.model_validate(resposta)
        return {"search_response": resposta, "retry_count": 0, "note": motivo}

    @staticmethod
    def _pedir_esclarecimento(state, req: StructuredRequest, regiao: str) -> Dict[str, Any]:
        """Regiao fora da base: nao busca em lugar nenhum e devolve a pergunta ao usuario."""
        pergunta = (
            f"Nao encontrei a regiao '{regiao}' no Distrito Federal. "
            "Pode indicar outra regiao administrativa ou bairro (ex.: Asa Sul, Aguas Claras)?"
        )
        return {
            "structured_request": req.model_copy(update={"clarification_needed": pergunta}),
            "search_response": _resposta_vazia(req, state["request_id"], list(req.target_amenities)),
            "retry_count": 0,
            "note": "regiao nao encontrada na tabela regioes: pedindo esclarecimento",
        }


_default_pipeline: Optional[RetrievalPipeline] = None


def retrieval_pipeline(state: AgentState) -> Dict[str, Any]:
    """Funcao pronta para `build_graph` (PostgreSQL do .env, auditoria gravada no banco)."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = RetrievalPipeline()
    return _default_pipeline(state)
