"""Communication_Agent do Bubbles com suporte a saida em texto e audio (TTS).

Responsabilidades:
  1. Apresentar ao usuario exclusivamente locais aprovados em `evidence_records`
     com `integrity_test.passed == True` e correspondentes em `search_response`
     (RNF01 - zero alucinacao).
  2. Tratar desvios com transparencia e seguranca:
     - Erro de execucao de agente anterior (`state["error"]`)
     - Pedido fora de escopo (`out_of_scope`) ou impossivel (`impossible_criteria`)
     - Esclarecimento necessario (`clarification_needed`)
     - Ausencia de evidencias aprovadas
  3. Adaptar o tom da comunicacao e a cadencia da voz ao perfil da persona
     (Dona Helena, Carla ou neutro - RNF03).
  4. Gerar resposta em audio (TTS via OpenAI `tts-1` com fallback local offline)
     para acessibilidade e baixa carga cognitiva, sem nunca bloquear o retorno
     textual caso o TTS falhe.
  5. Nao registrar dados pessoais ou `raw_query` em `note` (RNF02).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .audio import AudioSynthesisResult, AudioSynthesizer, DEFAULT_AUDIO_DIR
from .state import AgentState

MAX_LUGARES = 3


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Acessa campos de dicionarios ou modelos Pydantic."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _format_metadata(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value) if value is not None else ""


def _resolve_profile(state: AgentState) -> str:
    """Identifica o perfil/persona a partir do estado ou requisitos de acessibilidade."""
    profile = str(state.get("user_profile") or "").strip().lower()
    if "helena" in profile:
        return "helena"
    if "carla" in profile:
        return "carla"

    req = state.get("structured_request")
    acess = _get(req, "accessibility_requirements")
    if _get(acess, "wheelchair_required", False) or _get(acess, "elder_friendly", False):
        return "helena"

    return "neutro"


def _build_justification(evidence: Any) -> str:
    notes = _get(evidence, "grounding_notes", []) or []
    tags = _get(evidence, "matched_tags", []) or []

    parts = [str(note) for note in notes if note]
    if tags:
        parts.append("Características registradas no OpenStreetMap: " + _format_metadata(tags))

    if not parts:
        return "Local público verificado e aprovado nos critérios da busca."
    return " ".join(parts)


def format_grounded_response(state: AgentState) -> tuple[str, str]:
    """Gera a resposta textual estritamente fundamentada em evidencias (RNF01).

    Retorna `(texto_final, categoria_fluxo)`.
    """
    profile = _resolve_profile(state)

    if state.get("error"):
        return (
            "Desculpe, não consegui concluir sua busca com segurança neste momento. "
            "Por favor, tente novamente em alguns instantes.",
            "abstencao_erro",
        )

    req = state.get("structured_request")
    if req is None:
        return (
            "Não foi possível interpretar sua solicitação no momento. "
            "Você pode tentar reformular o pedido?",
            "abstencao_sem_requisicao",
        )

    if _get(req, "out_of_scope", False):
        reason = _get(req, "out_of_scope_reason") or "Solicitação fora do escopo de encontros presenciais."
        return (
            f"Não consigo atender a esse pedido porque ele está fora do escopo do Bubbles. "
            f"Motivo: {reason} "
            "Posso ajudar você a encontrar cafés, livrarias, parques ou centros culturais públicos para encontros em grupo.",
            "abstencao_fora_escopo",
        )

    if _get(req, "impossible_criteria", False):
        reason = _get(req, "impossible_criteria_reason") or "Critérios incompatíveis ou indisponíveis."
        return (
            f"Não foi possível encontrar uma combinação viável para os critérios solicitados. "
            f"Motivo: {reason} "
            "Tente flexibilizar o horário, o tipo de ambiente ou ampliar a região.",
            "abstencao_impossivel",
        )

    clarification = _get(req, "clarification_needed")
    if clarification:
        return str(clarification), "esclarecimento"

    search_response = state.get("search_response")
    items = _get(search_response, "items", []) or []
    evidence_records = state.get("evidence_records", []) or []

    approved = [
        ev for ev in evidence_records
        if _get(_get(ev, "integrity_test", {}), "passed", False)
    ]

    if not approved or not items:
        return (
            "Não encontrei locais com evidências suficientes para recomendar com segurança. "
            "Você gostaria de ampliar o raio da busca ou flexibilizar algum requisito?",
            "abstencao_sem_evidencia",
        )

    items_by_id = {_get(item, "place_id"): item for item in items}
    approved.sort(key=lambda ev: float(_get(ev, "total_score", 0.0) or 0.0), reverse=True)

    if profile == "helena":
        intro = "Olá! Encontrei estas opções seguras e confortáveis para você. Veja as informações com calma:"
    elif profile == "carla":
        intro = "Separei os locais mais compatíveis com sua busca. Confira os destaques:"
    else:
        intro = "Olá! Confira os locais públicos verificados e aprovados na validação:"

    blocks: List[str] = [intro]
    selected_count = 0

    for ev in approved:
        place_id = _get(ev, "place_id")
        item = items_by_id.get(place_id)
        name = _get(ev, "place_name")
        if item is None or not name:
            continue

        selected_count += 1
        address = _get(item, "address")
        distance = _get(item, "distance_km")
        distance_text = f"{float(distance):.2f} km" if distance is not None else "Distância não informada"
        justification = _build_justification(ev)
        osm_link = _get(_get(ev, "osm_reference", {}), "osm_link")

        lines = [f"{selected_count}. {name}"]
        if address:
            lines.append(f"Endereço: {address}")
        lines.append(f"Distância: {distance_text}")
        lines.append(f"Por que foi recomendado: {justification}")
        if osm_link:
            lines.append(f"Referência OSM: {osm_link}")

        blocks.append("\n".join(lines))
        if selected_count >= MAX_LUGARES:
            break

    if selected_count == 0:
        return (
            "Não encontrei locais com evidências suficientes para recomendar com segurança. "
            "Você gostaria de ampliar o raio da busca ou flexibilizar algum requisito?",
            "abstencao_sem_correspondencia",
        )

    filtros = _get(search_response, "applied_filters", {})
    if _get(filtros, "expanded_once", False):
        raio = _get(filtros, "radius_km")
        aviso_raio = (
            f"Aviso: o raio da busca foi ampliado para {raio} km para localizar opções compatíveis."
            if raio is not None
            else "Aviso: o raio da busca foi ampliado para localizar opções compatíveis."
        )
        blocks.append(aviso_raio)

    return "\n\n".join(blocks), "recomendacao"


class CommunicationAgent:
    """Agente de Comunicacao oficial do Bubbles com saida multimodal (Texto + Audio)."""

    def __init__(
        self,
        audio_synthesizer: Optional[AudioSynthesizer] = None,
        enable_audio: Optional[bool] = None,
        audio_output_dir: str | Path = DEFAULT_AUDIO_DIR,
    ):
        if enable_audio is None:
            env_flag = (os.getenv("COMMUNICATION_AUDIO_ENABLED") or "true").strip().lower()
            enable_audio = env_flag not in ("0", "false", "no", "off")
        self.enable_audio = enable_audio
        self.audio_synthesizer = audio_synthesizer or AudioSynthesizer(output_dir=audio_output_dir)

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        text, flow_kind = format_grounded_response(state)
        profile = _resolve_profile(state)

        state_audio_flag = state.get("audio_enabled")
        should_speak = self.enable_audio if state_audio_flag is None else bool(state_audio_flag)

        req_id = str(state.get("request_id") or "req")
        audio_result: AudioSynthesisResult = self.audio_synthesizer.synthesize(
            text=text,
            request_id=req_id,
            profile=profile,
            enabled=should_speak,
        )

        return {
            "final_response": text,
            "audio_output": audio_result.model_dump(),
            "note": f"comunicacao ({flow_kind}, perfil={profile}, audio={audio_result.provider})",
        }


def criar_comunicacao(
    enable_audio: Optional[bool] = None,
    audio_output_dir: str | Path = DEFAULT_AUDIO_DIR,
    audio_synthesizer: Optional[AudioSynthesizer] = None,
) -> Callable[[AgentState], Dict[str, Any]]:
    """Factory do Communication_Agent pronto para injecao no `build_graph`."""
    return CommunicationAgent(
        audio_synthesizer=audio_synthesizer,
        enable_audio=enable_audio,
        audio_output_dir=audio_output_dir,
    )


_default_communication_agent = CommunicationAgent()


def communication_agent(state: AgentState) -> Dict[str, Any]:
    """Funcao de agente injetavel diretamente no `build_graph` do LangGraph."""
    return _default_communication_agent(state)
