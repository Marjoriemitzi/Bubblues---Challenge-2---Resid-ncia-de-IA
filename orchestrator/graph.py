"""Orquestrador LangGraph do Bubbles.

Fluxo:

    START -> nlu --(intent_valid=false)------------------------> communication -> END
              |                                                        ^
              +--(ok)--> retrieval -> validation --(aprovado)----------+
                            ^             |
                            +--(reprovado e retry_count < max)
                                          |
                                          +--(reprovado, sem tentativas)-> communication (abstencao)

CONCEITOS LANGGRAPH usados aqui
  - Node: uma funcao `estado -> atualizacao parcial`. Cada agente e um no.
  - Edge: aresta fixa (`add_edge`): "depois de A, sempre B".
  - Conditional edge: `add_conditional_edges(no, funcao_roteadora)`. A funcao
    olha o estado e devolve o NOME do proximo no. E assim que se faz if/loop.
  - compile(): valida o grafo (nos soltos, destinos inexistentes) e devolve
    um objeto executavel com `.invoke(estado_inicial)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from langgraph.graph import END, START, StateGraph

from .contracts import EvidenceRecord, SearchResponse, StructuredRequest, ValidationFeedback
from .state import AgentState, TraceEntry

MAX_RETRIES = 2  # reconsultas ao Retrieval_Agent apos reprovacao do Validation_Agent

NLU = "nlu_guardrail_agent"
RETRIEVAL = "retrieval_agent"
VALIDATION = "validation_agent"
COMMUNICATION = "communication_agent"

# Resposta fixa (sem LLM) usada se ate o Communication_Agent falhar.
FALLBACK_MESSAGE = (
    "Nao consegui processar seu pedido agora. Tente novamente em instantes."
)

# Um agente e qualquer callable estado -> dict parcial. Ele pode devolver
# dicts "crus" (ex.: JSON do LLM); o orquestrador valida com os modelos Pydantic.
Agent = Callable[[AgentState], dict]


@dataclass(frozen=True)
class Decision:
    next: str
    reason: str


# --------------------------------------------------------------------------
# Roteamento: funcoes PURAS (so leem o estado). Ficam fora do grafo para
# serem testaveis sem executar nada.
# --------------------------------------------------------------------------
def route_after_nlu(state: AgentState) -> Decision:
    req = state["structured_request"]
    if not req.intent_valid:
        why = (
            "out_of_scope" if req.out_of_scope else "impossible_criteria"
        )
        return Decision(COMMUNICATION, f"intent_valid=false ({why}): abstencao precoce")
    if req.clarification_needed:
        return Decision(COMMUNICATION, "clarification_needed: pergunta ao usuario antes de buscar")
    return Decision(RETRIEVAL, "intent_valid=true: segue para busca")


def route_after_retrieval(state: AgentState) -> Decision:
    resp = state["search_response"]
    if resp.status in ("NO_RESULTS", "OUT_OF_SCOPE") or resp.results_count == 0:
        # O Retrieval ja expande o raio sozinho; auditar lista vazia so geraria reconsultas inuteis.
        return Decision(COMMUNICATION, f"busca sem candidatos ({resp.status}): abstencao")
    return Decision(VALIDATION, "candidatos prontos para auditoria")


def _guard(route: Callable[[AgentState], Decision]) -> Callable[[AgentState], Decision]:
    """Se qualquer agente falhou (state['error']), desvia para abstencao segura."""

    def guarded(state: AgentState) -> Decision:
        if state.get("error"):
            return Decision(COMMUNICATION, f"falha de agente ({state['error']}): abstencao segura")
        return route(state)

    return guarded


def make_route_after_validation(max_retries: int) -> Callable[[AgentState], Decision]:
    def route(state: AgentState) -> Decision:
        fb = state["validation_feedback"]
        if fb.approved:
            return Decision(COMMUNICATION, "Top-3 aprovado pela auditoria")
        # retry_count ja foi incrementado pelo no de validacao ao reprovar.
        if state.get("retry_count", 0) <= max_retries:
            return Decision(
                RETRIEVAL,
                f"reprovado; reconsulta {state['retry_count']}/{max_retries}",
            )
        return Decision(COMMUNICATION, f"reprovado e {max_retries} reconsultas esgotadas: abstencao")

    return route


# --------------------------------------------------------------------------
# Instrumentacao: embrulha cada agente com validacao + trace + regras de estado.
# --------------------------------------------------------------------------
def _coerce(update: dict) -> dict:
    """Converte dicts em modelos Pydantic. Payload invalido -> ValidationError."""
    models = {
        "structured_request": StructuredRequest,
        "search_response": SearchResponse,
        "validation_feedback": ValidationFeedback,
    }
    out = dict(update)
    for key, model in models.items():
        if out.get(key) is not None:
            out[key] = model.model_validate(out[key])
    if "evidence_records" in out:
        out["evidence_records"] = [EvidenceRecord.model_validate(e) for e in out["evidence_records"]]
    return out


def _node(
    name: str,
    agent: Agent,
    decide: Callable[[AgentState], Decision] | None,
    post: Callable[[AgentState, dict], dict] | None = None,
):
    def run(state: AgentState) -> dict:
        try:
            raw = agent(state)
        except Exception as exc:  # falha de runtime do agente (LLM fora do ar, banco, timeout...)
            # Guardamos so o NOME da excecao: a mensagem pode conter texto do usuario (RNF02).
            kind = type(exc).__name__
            update: dict = {"error": f"{name}: {kind}"}
            note = f"falha do agente ({kind})"
            if name == NLU:
                update["raw_query"] = None  # RNF02 vale mesmo quando o NLU falha
            if name == COMMUNICATION:
                update["final_response"] = FALLBACK_MESSAGE
        else:
            # Payload fora do contrato continua levantando ValidationError: e bug de
            # implementacao do agente, nao falha transitoria, e deve aparecer alto.
            update = _coerce(raw)
            note = update.pop("note", "")  # agentes podem anexar um resumo livre (sem PII)
            if post:
                update = post(state, update)

        merged = {**state, **update}
        decision = decide(merged) if decide else Decision(END, "fim do fluxo")
        update["agent_trace"] = [
            TraceEntry(
                timestamp=datetime.now(timezone.utc),
                agent=name,
                input_keys=sorted(k for k, v in state.items() if v not in (None, [], "") and k != "agent_trace"),
                output_keys=sorted(k for k in update if k != "agent_trace"),
                note=note,
                next_agent=decision.next,
                justification=decision.reason,
            )
        ]
        return update

    return run


def _scrub_raw_query(state: AgentState, update: dict) -> dict:
    """RNF02: descarta o texto livre assim que o NLU termina."""
    update["raw_query"] = None
    req = update.get("structured_request")
    if req is not None:
        update["structured_request"] = req.model_copy(update={"raw_query": None})
    return update


def _count_retry(state: AgentState, update: dict) -> dict:
    fb = update["validation_feedback"]
    if not fb.approved:
        update["retry_count"] = state.get("retry_count", 0) + 1
    return update


# --------------------------------------------------------------------------
# Montagem do grafo
# --------------------------------------------------------------------------
def build_graph(
    nlu: Agent,
    retrieval: Agent,
    validation: Agent,
    communication: Agent,
    max_retries: int = MAX_RETRIES,
):
    """Monta e compila o grafo. Os agentes entram por injecao de dependencia:
    hoje sao stubs; nas issues #7-#10 trocamos pelos reais sem mexer aqui."""
    r_nlu = _guard(route_after_nlu)
    r_retrieval = _guard(route_after_retrieval)
    r_validation = _guard(make_route_after_validation(max_retries))

    g = StateGraph(AgentState)

    g.add_node(NLU, _node(NLU, nlu, r_nlu, post=_scrub_raw_query))
    g.add_node(RETRIEVAL, _node(RETRIEVAL, retrieval, r_retrieval))
    g.add_node(VALIDATION, _node(VALIDATION, validation, r_validation, post=_count_retry))
    g.add_node(COMMUNICATION, _node(COMMUNICATION, communication, None))

    g.add_edge(START, NLU)
    g.add_conditional_edges(NLU, lambda s: r_nlu(s).next, [RETRIEVAL, COMMUNICATION])
    g.add_conditional_edges(RETRIEVAL, lambda s: r_retrieval(s).next, [VALIDATION, COMMUNICATION])
    g.add_conditional_edges(VALIDATION, lambda s: r_validation(s).next, [RETRIEVAL, COMMUNICATION])
    g.add_edge(COMMUNICATION, END)

    return g.compile()


def run(graph, raw_query: str, request_id: str) -> AgentState:
    """Ponto de entrada: monta o estado inicial e executa o grafo."""
    return graph.invoke({"request_id": request_id, "raw_query": raw_query, "retry_count": 0, "agent_trace": []})
