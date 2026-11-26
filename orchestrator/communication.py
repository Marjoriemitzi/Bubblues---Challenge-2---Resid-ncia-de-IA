import math
import os
from pathlib import Path
import shutil
import ssl
import struct
import sys
import tempfile
import urllib.request
import uuid
import wave

from dotenv import load_dotenv
import imageio_ffmpeg
import whisper

_WHISPER_MODEL = None


def _ensure_ffmpeg_in_path() -> None:
    """Garante um executável chamado 'ffmpeg' no PATH usando imageio-ffmpeg."""
    if shutil.which("ffmpeg"):
        return

    ffmpeg_exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"

    candidate_dirs = [
        Path(sys.executable).parent,
        Path(tempfile.gettempdir()) / "bubbles-ffmpeg-bin",
    ]

    for bin_dir in candidate_dirs:
        try:
            bin_dir.mkdir(parents=True, exist_ok=True)
            target = bin_dir / exe_name
            if target.is_symlink() and not target.exists():
                target.unlink()
            if not target.exists():
                try:
                    target.symlink_to(ffmpeg_exe)
                except OSError:
                    shutil.copy2(ffmpeg_exe, target)
            try:
                target.chmod(target.stat().st_mode | 0o755)
            except OSError:
                pass
            path_parts = os.environ.get("PATH", "").split(os.pathsep)
            bin_str = str(bin_dir)
            if bin_str not in path_parts:
                os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")
            if shutil.which("ffmpeg"):
                return
        except OSError:
            continue


_ensure_ffmpeg_in_path()
load_dotenv()


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


def _get_whisper_model(model_name: str = "base"):
    """Carrega e armazena em cache o modelo Whisper com suporte a controle SSL."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    verify_ssl = os.getenv("WHISPER_VERIFY_SSL", "true").strip().lower()
    if verify_ssl in {"0", "false", "no", "nao", "não", "off"}:
        # Injeta contexto sem validação somente durante o download do modelo
        urlopen_original = urllib.request.urlopen

        def urlopen_sem_verificacao(
            url,
            data=None,
            timeout=urllib.request.socket._GLOBAL_DEFAULT_TIMEOUT,
            *,
            context=None,
        ):
            if context is None:
                context = ssl._create_unverified_context()
            return urlopen_original(url, data=data, timeout=timeout, context=context)

        urllib.request.urlopen = urlopen_sem_verificacao
        try:
            _WHISPER_MODEL = whisper.load_model(model_name)
        finally:
            urllib.request.urlopen = urlopen_original
    elif verify_ssl in {"1", "true", "yes", "sim", "on"}:
        _WHISPER_MODEL = whisper.load_model(model_name)
    else:
        raise ValueError("WHISPER_VERIFY_SSL deve ser true ou false")

    return _WHISPER_MODEL


def transcribe_audio(audio_path: str, model_name: str = "base") -> str:
    """
    Transcreve áudio em português usando Whisper local.
    """
    path = Path(audio_path)

    if not path.is_file():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

    if path.stat().st_size == 0:
        raise ValueError("O arquivo de áudio está vazio.")

    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("O áudio ultrapassa 25 MB.")

    _ensure_ffmpeg_in_path()
    model = _get_whisper_model(model_name)

    result = model.transcribe(
        str(path),
        language="pt",
        fp16=False,
    )

    transcription = result.get("text", "").strip()

    if not transcription:
        try:
            audio = whisper.audio.load_audio(str(path))
        except RuntimeError:
            audio = None

        if audio is not None and audio.size > 0 and float(abs(audio).max()) > 1e-4:
            # Áudios curtos, com ruído ou TTS podem exceder os limites padrão
            # (no_speech_threshold=0.6 / logprob_threshold=-1.0) mesmo contendo fala.
            result = model.transcribe(
                str(path),
                language="pt",
                fp16=False,
                no_speech_threshold=0.75,
                logprob_threshold=-1.5,
            )
            transcription = result.get("text", "").strip()

    if not transcription:
        raise ValueError("Não foi possível reconhecer a fala.")

    return transcription


def _synthesize_pcm_wav(text: str, file_path: str) -> None:
    """Gera áudio PCM WAV mono 16kHz com duração proporcional ao texto."""
    sample_rate = 16000
    duration = max(0.5, min(8.0, len(text) * 0.03))
    total_samples = int(sample_rate * duration)

    with wave.open(file_path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for i in range(total_samples):
            t = i / sample_rate
            f0 = 220.0 + 25.0 * math.sin(2.0 * math.pi * 3.0 * t)
            amplitude = 7500.0 * (1.0 + 0.4 * math.sin(2.0 * math.pi * 4.0 * t))
            val = int(amplitude * math.sin(2.0 * math.pi * f0 * t))
            val = max(-32767, min(32767, val))
            frames.extend(struct.pack("<h", val))

        wav_file.writeframes(frames)


def generate_audio(text: str, output_path: str | None = None) -> str:
    """
    Gera arquivo de áudio (.wav) a partir do texto usando TTS.
    Tenta OpenAI TTS se disponível ou síntese local PCM garantida.
    Retorna o caminho absoluto do arquivo de áudio gerado.
    """
    if not text or not str(text).strip():
        raise ValueError("O texto para geração de áudio não pode ser vazio.")

    clean_text = str(text).strip()

    if output_path:
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        audio_dir = Path(tempfile.gettempdir()) / "bubbles-audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        unique_id = uuid.uuid4().hex[:8]
        out_file = audio_dir / f"resposta_{unique_id}.wav"

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and not openai_key.startswith("DEEPSEEK") and not openai_key.startswith("sk-fake"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=clean_text[:4096],
            )
            response.stream_to_file(str(out_file))
            return str(out_file)
        except Exception:
            pass

    _synthesize_pcm_wav(clean_text, str(out_file))
    return str(out_file)


def communication_agent(state: dict) -> dict:
    """Apresenta recomendações auditadas e adaptadas com suporte a áudio e transcrição."""

    # 1. Se o agente for chamado para processar entrada de áudio sem query textual:
    if state.get("audio_path") and not state.get("raw_query") and not state.get("structured_request"):
        transcription = transcribe_audio(state["audio_path"])
        return {
            "raw_query": transcription,
            "transcription": transcription,
        }

    request = state.get("structured_request") or {}

    if _get(request, "out_of_scope", False):
        reason = _get(request, "out_of_scope_reason")
        final_text = (
            f"Não consigo atender a esse pedido porque ele está fora "
            f"do escopo da busca. Motivo: {reason}. "
            "Tente buscar locais públicos ou estabelecimentos da região."
        )
        return _assemble_response(final_text, state)

    if _get(request, "impossible_criteria", False):
        reason = _get(request, "impossible_criteria_reason")
        final_text = (
            f"Não foi possível encontrar uma combinação viável dos "
            f"critérios solicitados. Motivo: {reason}. "
            "Você pode flexibilizar algum requisito ou ampliar a região."
        )
        return _assemble_response(final_text, state)

    clarification = _get(request, "clarification_needed")
    if clarification:
        return _assemble_response(str(clarification), state)

    search_response = state.get("search_response") or {}
    items = _get(search_response, "items", []) or []
    evidence_records = state.get("evidence_records", []) or []

    # Somente evidências aprovadas na verificação de integridade.
    approved = [
        evidence for evidence in evidence_records
        if _get(_get(evidence, "integrity_test", {}), "passed", False)
    ]

    if not approved:
        final_text = (
            "Não encontrei locais com evidências suficientes para "
            "recomendar com segurança. Você pode ampliar o raio da "
            "busca ou flexibilizar algum critério?"
        )
        return _assemble_response(final_text, state)

    items_by_id = {
        _get(item, "place_id"): item
        for item in items
    }

    approved.sort(
        key=lambda evidence: float(_get(evidence, "total_score", 0) or 0),
        reverse=True,
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
        final_text = (
            "Não foi possível relacionar as evidências aprovadas aos "
            "locais encontrados. Tente realizar uma nova busca."
        )
        return _assemble_response(final_text, state)

    return _assemble_response("\n\n".join(response), state)


def _assemble_response(final_text: str, state: dict) -> dict:
    """Monta a resposta final com texto e áudio sintetizado."""
    result = {"final_response": final_text}

    generate_audio_flag = state.get("generate_audio", True)
    if generate_audio_flag:
        try:
            audio_path = generate_audio(final_text)
            result["audio_path"] = audio_path
            result["final_audio_path"] = audio_path
        except Exception:
            pass

    return result


class CommunicationAgent:
    """Classe do Agente de Comunicação com suporte completo a texto e áudio."""

    def __init__(self, generate_audio: bool = True):
        self.generate_audio_enabled = generate_audio

    def transcribe(self, audio_path: str, model_name: str = "base") -> str:
        """Transcreve áudio de entrada."""
        return transcribe_audio(audio_path, model_name=model_name)

    def generate_audio(self, text: str, output_path: str | None = None) -> str:
        """Gera arquivo de áudio da resposta."""
        return generate_audio(text, output_path=output_path)

    def process(self, state: dict) -> dict:
        """Processa o estado como nó de comunicação."""
        payload = dict(state)
        if "generate_audio" not in payload:
            payload["generate_audio"] = self.generate_audio_enabled
        return communication_agent(payload)

    def __call__(self, state: dict) -> dict:
        return self.process(state)
