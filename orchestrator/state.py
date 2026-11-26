"""Estado compartilhado (AgentState) do grafo multiagente.

CONCEITO LANGGRAPH #1 - State
O "estado" e o quadro-branco que todos os nos (agentes) leem e escrevem.
Cada no recebe o estado inteiro e devolve so o PEDACO que quer alterar;
o LangGraph faz o merge. Chaves sem "reducer" sao SOBRESCRITAS.

CONCEITO LANGGRAPH #2 - Reducer
`Annotated[list, operator.add]` diz "ao receber uma atualizacao nessa chave,
CONCATENE em vez de sobrescrever". E assim que o agent_trace acumula o
historico de todos os agentes sem que ninguem precise ler/reescrever a lista.
"""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, TypedDict

from pydantic import BaseModel

from .contracts import EvidenceRecord, SearchResponse, StructuredRequest, ValidationFeedback


class TraceEntry(BaseModel):
    """Uma linha do log de colaboracao (agent_trace). Nunca guarda texto livre do usuario."""

    timestamp: datetime
    agent: str
    input_keys: list[str]  # quais campos do estado o agente leu
    output_keys: list[str]  # quais campos ele escreveu
    note: str = ""  # resumo escrito pelo agente (sem dados pessoais)
    next_agent: str  # para onde o orquestrador roteou
    justification: str  # por que essa transicao


class AgentState(TypedDict, total=False):
    request_id: str
    raw_query: str | None  # RNF02: vira None apos o NLU
    audio_path: str | None  # Caminho do arquivo de áudio (entrada ou resposta)
    final_audio_path: str | None  # Caminho do áudio da resposta gerada pelo agente de comunicação
    transcription: str | None  # Transcrição do áudio de entrada
    generate_audio: bool | None  # Controle de síntese de voz (TTS)
    user_profile: str | None  # Perfil do usuário (ex: helena, carla, neutro)
    structured_request: StructuredRequest | None
    search_response: SearchResponse | None
    validation_feedback: ValidationFeedback | None
    evidence_records: list[EvidenceRecord]
    retry_count: int  # quantas reconsultas ja foram feitas
    final_response: str | None
    error: str | None  # "<agente>: <TipoDaExcecao>" quando um agente falha
    agent_trace: Annotated[list[TraceEntry], operator.add]
