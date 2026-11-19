"""Orquestrador LangGraph do Bubbles.

Fluxo:

    START -> nlu --(intent_valid=false | clarification_needed)--> communication -> END
              |                                                        ^
              +--(ok)--> retrieval ------------------------------------+

O laco busca -> auditoria -> reconsulta NAO e mais do grafo: acontece DENTRO do no `retrieval`
(RetrievalPipeline ou, depois, o agente LLM), que sempre passa pelo gate de auditoria antes de
devolver `evidence_records`. O Validation e uma ferramenta, nao um agente (nao usa LLM).

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
from .observabilidade import observar
from .state import AgentState, TraceEntry

MAX_RETRIES = 2  # reconsultas que o Retrieval pode fazer apos o gate reprovar a busca

NLU = "nlu_guardrail_agent"
RETRIEVAL = "retrieval"
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
    """Depois do Retrieval so ha um destino (o Communication); a decisao registra POR QUE."""
    if state.get("evidence_records"):
        return Decision(COMMUNICATION, "evidencias aprovadas pelo gate de auditoria")
    req, resp, fb = state.get("structured_request"), state.get("search_response"), state.get("validation_feedback")
    if req is not None and req.clarification_needed:
        return Decision(COMMUNICATION, "clarification_needed: pergunta ao usuario antes de buscar")
    if fb is not None and not fb.approved:  # antes do "sem candidatos": reprovar e esgotar candidatos tambem cai aqui
        return Decision(COMMUNICATION, f"reprovado pelo gate apos {state.get('retry_count', 0)} reconsulta(s): abstencao")
    if resp is None or resp.status in ("NO_RESULTS", "OUT_OF_SCOPE") or resp.results_count == 0:
        return Decision(COMMUNICATION, f"busca sem candidatos ({resp.status if resp else 'sem resposta'}): abstencao")
    return Decision(COMMUNICATION, "sem evidencias aprovadas: abstencao")


def _guard(route: Callable[[AgentState], Decision]) -> Callable[[AgentState], Decision]:
    """Se qualquer agente falhou (state['error']), desvia para abstencao segura."""

    def guarded(state: AgentState) -> Decision:
        if state.get("error"):
            return Decision(COMMUNICATION, f"falha de agente ({state['error']}): abstencao segura")
        return route(state)

    return guarded


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
    def _executar(state: AgentState) -> dict:
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

    def run(state: AgentState) -> dict:
        tipo = "agent" if name in (NLU, COMMUNICATION) else "chain"
        entrada = sorted(k for k, v in state.items() if v not in (None, [], "") and k != "agent_trace")
        with observar(f"no.{name}", tipo, metadata={"input_keys": entrada}) as obs:
            update = _executar(state)
            t = update["agent_trace"][0]
            obs.update(output={"output_keys": t.output_keys, "next_agent": t.next_agent, "justificativa": t.justification, "nota": t.note},
                       **({"level": "ERROR", "status_message": update["error"]} if update.get("error") else {}))
            return update

    return run


def _scrub_raw_query(state: AgentState, update: dict) -> dict:
    """RNF02: descarta o texto livre assim que o NLU termina."""
    update["raw_query"] = None
    req = update.get("structured_request")
    if req is not None:
        update["structured_request"] = req.model_copy(update={"raw_query": None})
    return update


# --------------------------------------------------------------------------
# Montagem do grafo
# --------------------------------------------------------------------------
def build_graph(
    nlu: Agent,
    retrieval: Agent,
    communication: Agent,
):
    """Monta e compila o grafo (nlu -> retrieval -> communication). Os agentes entram por injecao.

    `retrieval` busca, audita (gate) e reconsulta; devolve search_response, evidence_records,
    validation_feedback e retry_count prontos. Ver RetrievalPipeline.
    """
    r_nlu = _guard(route_after_nlu)
    r_retrieval = _guard(route_after_retrieval)

    g = StateGraph(AgentState)

    g.add_node(NLU, _node(NLU, nlu, r_nlu, post=_scrub_raw_query))
    g.add_node(RETRIEVAL, _node(RETRIEVAL, retrieval, r_retrieval))
    g.add_node(COMMUNICATION, _node(COMMUNICATION, communication, None))

    g.add_edge(START, NLU)
    g.add_conditional_edges(NLU, lambda s: r_nlu(s).next, [RETRIEVAL, COMMUNICATION])
    g.add_edge(RETRIEVAL, COMMUNICATION)
    g.add_edge(COMMUNICATION, END)

    return g.compile()


def run(graph, raw_query: str, request_id: str) -> AgentState:
    """Ponto de entrada: monta o estado inicial e executa o grafo."""
    with observar("pedido", "agent", metadata={"request_id": request_id}) as obs:  # NUNCA o raw_query (RNF02)
        estado = graph.invoke({"request_id": request_id, "raw_query": raw_query, "retry_count": 0, "agent_trace": []})
        obs.update(output={"retry_count": estado.get("retry_count"), "erro": estado.get("error"),
                           "n_evidencias": len(estado.get("evidence_records") or []), "caminho": [t.agent for t in estado["agent_trace"]]})
        return estado
