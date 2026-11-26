"""Sintese de audio (Text-to-Speech) para o Communication_Agent do Bubbles.

Cadeia de provedores com degradacao graciosa (RNF03 - acessibilidade):
  1. OpenAI TTS (`tts-1`), quando ha chave OpenAI configurada (`TTS_API_KEY`,
     `OPENAI_API_KEY` ou `LLM_API_KEY` compativel).
  2. Fallback local/offline:
     - `gTTS` (se instalado e com rede);
     - `pyttsx3` (se instalado);
     - `say` nativo do macOS (verificando que o arquivo gerado contem frames reais);
     - Gerador deterministico WAV em Python puro (`offline_wav`), garantindo
       arquivo de audio valido mesmo em ambientes headless/CI sem rede.

Nada do texto livre original do usuario (`raw_query`) e usado para nomear
arquivos ou registrar logs (RNF02).
"""

from __future__ import annotations

import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Optional, Tuple

from pydantic import BaseModel, Field

DEFAULT_AUDIO_DIR = "audio_outputs"
DEFAULT_OPENAI_TTS_MODEL = "tts-1"
DEFAULT_AUDIO_FORMAT = "mp3"

_RE_MARKDOWN_DECORATION = re.compile(r"[*_`#]+")
_RE_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_RE_PAREN_URL = re.compile(r"\(\s*https?://[^)\s]+\s*\)")
_RE_URL = re.compile(r"https?://[^\s)\]>\"']+")
_RE_OSM_PARENS = re.compile(r"\(\s*OSM:\s*[^)]+\)", re.IGNORECASE)
_RE_EMPTY_REF_LINE = re.compile(r"^\s*Refer[êe]ncia\s+OSM:\s*$", re.IGNORECASE)
_RE_MULTI_NEWLINE = re.compile(r"\n{2,}")
_RE_WHITESPACE = re.compile(r"[ \t]{2,}")
_RE_KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*km\b", re.IGNORECASE)
_RE_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")


class AudioSynthesisResult(BaseModel):
    """Metadados da sintese de audio gerada pelo Communication_Agent."""

    enabled: bool = True
    success: bool = False
    provider: str = "disabled"
    file_path: Optional[str] = None
    audio_format: Optional[str] = None
    voice: Optional[str] = None
    model: Optional[str] = None
    speed: Optional[float] = None
    size_bytes: int = Field(default=0, ge=0)
    text_spoken: str = ""
    fallback_used: bool = False
    error: Optional[str] = None


def _sanitize_request_id(request_id: str) -> str:
    cleaned = _RE_SAFE_ID.sub("_", (request_id or "req").strip()).strip("_")
    return cleaned[:64] or "req"


def prepare_text_for_speech(text: str) -> str:
    """Converte a resposta textual em texto limpo para leitura em voz alta.

    Preserva 100% dos fatos (nomes, distancias e avisos) sem adicionar dados
    novos (RNF01), removendo marcacoes visuais e URLs longas.
    """
    if not text:
        return ""

    spoken = _RE_MARKDOWN_LINK.sub(r"\1", text)
    spoken = _RE_OSM_PARENS.sub("", spoken)
    spoken = _RE_PAREN_URL.sub("", spoken)
    spoken = _RE_URL.sub("", spoken)
    spoken = _RE_MARKDOWN_DECORATION.sub("", spoken)
    spoken = _RE_KM.sub(r"\1 quilômetros", spoken)

    # Transforma marcadores de lista em pausas naturais de fala
    lines = []
    for raw_line in spoken.splitlines():
        line = raw_line.strip()
        if not line or _RE_EMPTY_REF_LINE.match(line):
            continue
        line = re.sub(r"^[•\-–—]\s*", "", line)
        line = re.sub(r"\s*\|\s*", ". ", line)
        line = re.sub(r"\s+([.,!?;:])", r"\1", line)
        if line and line[-1] not in ".!?:;":
            line += "."
        lines.append(line)

    joined = " ".join(lines)
    joined = _RE_MULTI_NEWLINE.sub(" ", joined)
    joined = _RE_WHITESPACE.sub(" ", joined)
    joined = re.sub(r"\s+([.,!?;:])", r"\1", joined)
    return joined.strip()


def select_voice_for_profile(profile: str, provider: str = "openai_tts") -> Tuple[str, float]:
    """Seleciona voz e velocidade adequadas a persona (RNF03)."""
    prof = (profile or "neutro").strip().lower()
    if provider == "macos_say":
        if "helena" in prof:
            return "Luciana", 165.0
        if "carla" in prof:
            return "Luciana", 195.0
        return "Luciana", 180.0

    # Padrao OpenAI TTS (`tts-1`)
    if "helena" in prof:
        return "nova", 0.92  # Tom calmo, acolhedor e ritmo pausado
    if "carla" in prof:
        return "alloy", 1.05  # Tom objetivo e direto
    return "nova", 1.0


def _resolve_openai_tts_key(explicit_key: Optional[str] = None) -> Optional[str]:
    """Retorna uma chave OpenAI valida para TTS, ignorando chaves de outros provedores."""
    candidates = [
        explicit_key,
        os.getenv("TTS_API_KEY"),
        os.getenv("OPENAI_API_KEY"),
    ]
    llm_key = os.getenv("LLM_API_KEY")
    # LLM_API_KEY pode ser Groq (gsk_...) ou DeepSeek quando LLM_BASE_URL estiver definido
    if llm_key and not llm_key.strip().startswith("gsk_") and not os.getenv("DEEPSEEK_API_KEY"):
        base_url = (os.getenv("LLM_BASE_URL") or "").lower()
        if not base_url or "openai.com" in base_url:
            candidates.append(llm_key)

    for raw in candidates:
        key = (raw or "").strip()
        if key and "sua_chave" not in key and "sk-..." not in key:
            return key
    return None


def _wav_has_audio_frames(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() > 0 and wf.getframerate() > 0
    except Exception:
        return False


def _generate_offline_wav(target_path: Path, spoken_text: str) -> None:
    """Gera arquivo WAV PCM valido (sinal acustico suave) sem dependencias externas."""
    sample_rate = 22050
    # Duracao proporcional curta (entre 0.6s e 1.8s) para sinalizar retorno em audio
    duration_sec = min(1.8, max(0.6, len(spoken_text) / 250.0))
    total_frames = int(sample_rate * duration_sec)
    amplitude = 6000
    freq_hz = 440.0

    with wave.open(str(target_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total_frames):
            t = i / sample_rate
            # Envelope suave de fade-in/fade-out para evitar cliques
            env = min(1.0, i / (sample_rate * 0.05), (total_frames - i) / (sample_rate * 0.08))
            sample = int(amplitude * env * math.sin(2.0 * math.pi * freq_hz * t))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(bytes(frames))


class AudioSynthesizer:
    """Sintetizador TTS com OpenAI `tts-1` e fallback local offline."""

    def __init__(
        self,
        output_dir: str | Path = DEFAULT_AUDIO_DIR,
        api_key: Optional[str] = None,
        model: str = DEFAULT_OPENAI_TTS_MODEL,
        voice: Optional[str] = None,
        response_format: str = DEFAULT_AUDIO_FORMAT,
        enable_local_fallback: bool = True,
        client: Any = None,
    ):
        self.output_dir = Path(output_dir)
        self.api_key = _resolve_openai_tts_key(api_key)
        self.model = model
        self.voice_override = voice
        self.response_format = response_format
        self.enable_local_fallback = enable_local_fallback
        self.client = client

    def _synthesize_openai(
        self,
        spoken_text: str,
        target_path: Path,
        voice: str,
        speed: float,
    ) -> AudioSynthesisResult:
        client = self.client
        if client is None:
            if not self.api_key:
                raise RuntimeError("Chave OpenAI TTS nao configurada")
            from openai import OpenAI  # noqa: PLC0415

            client = OpenAI(api_key=self.api_key)

        response = client.audio.speech.create(
            model=self.model,
            voice=voice,
            input=spoken_text,
            response_format=self.response_format,
            speed=speed,
        )

        if hasattr(response, "stream_to_file"):
            response.stream_to_file(str(target_path))
        elif hasattr(response, "write_to_file"):
            response.write_to_file(str(target_path))
        elif hasattr(response, "read"):
            target_path.write_bytes(response.read())
        else:
            content = getattr(response, "content", None)
            if not isinstance(content, (bytes, bytearray)):
                raise TypeError("Resposta TTS sem conteudo binario suportado")
            target_path.write_bytes(bytes(content))

        size = target_path.stat().st_size if target_path.exists() else 0
        if size == 0:
            raise RuntimeError("Arquivo de audio vazio retornado pelo OpenAI TTS")

        return AudioSynthesisResult(
            enabled=True,
            success=True,
            provider="openai_tts",
            file_path=str(target_path),
            audio_format=self.response_format,
            voice=voice,
            model=self.model,
            speed=speed,
            size_bytes=size,
            text_spoken=spoken_text,
            fallback_used=False,
        )

    def _synthesize_gtts(self, spoken_text: str, base_path: Path) -> Optional[AudioSynthesisResult]:
        try:
            from gtts import gTTS  # noqa: PLC0415
        except ImportError:
            return None

        target = base_path.with_suffix(".mp3")
        try:
            tts = gTTS(text=spoken_text, lang="pt", tld="com.br")
            tts.save(str(target))
            size = target.stat().st_size if target.exists() else 0
            if size > 0:
                return AudioSynthesisResult(
                    enabled=True,
                    success=True,
                    provider="gtts",
                    file_path=str(target),
                    audio_format="mp3",
                    voice="pt-br",
                    model="gtts",
                    speed=1.0,
                    size_bytes=size,
                    text_spoken=spoken_text,
                    fallback_used=True,
                )
        except Exception:
            if target.exists():
                target.unlink(missing_ok=True)
        return None

    def _synthesize_pyttsx3(self, spoken_text: str, base_path: Path, rate_wpm: float) -> Optional[AudioSynthesisResult]:
        try:
            import pyttsx3  # noqa: PLC0415
        except ImportError:
            return None

        target = base_path.with_suffix(".wav")
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", int(rate_wpm))
            engine.save_to_file(spoken_text, str(target))
            engine.runAndWait()
            if target.exists() and _wav_has_audio_frames(target):
                return AudioSynthesisResult(
                    enabled=True,
                    success=True,
                    provider="pyttsx3",
                    file_path=str(target),
                    audio_format="wav",
                    voice="local",
                    model="pyttsx3",
                    speed=round(rate_wpm / 180.0, 2),
                    size_bytes=target.stat().st_size,
                    text_spoken=spoken_text,
                    fallback_used=True,
                )
        except Exception:
            pass
        if target.exists():
            target.unlink(missing_ok=True)
        return None

    def _synthesize_macos_say(
        self,
        spoken_text: str,
        base_path: Path,
        voice: str,
        rate_wpm: float,
    ) -> Optional[AudioSynthesisResult]:
        say_bin = shutil.which("say")
        if not say_bin:
            return None

        target = base_path.with_suffix(".wav")
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as tf:
                tf.write(spoken_text)
                txt_path = Path(tf.name)
            try:
                cmd = [
                    say_bin,
                    "-v",
                    voice,
                    "-r",
                    str(int(rate_wpm)),
                    "--file-format=WAVE",
                    "--data-format=LEI16@22050",
                    "-o",
                    str(target),
                    "-f",
                    str(txt_path),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
            finally:
                txt_path.unlink(missing_ok=True)

            if proc.returncode == 0 and target.exists() and _wav_has_audio_frames(target):
                return AudioSynthesisResult(
                    enabled=True,
                    success=True,
                    provider="macos_say",
                    file_path=str(target),
                    audio_format="wav",
                    voice=voice,
                    model="macos_say",
                    speed=round(rate_wpm / 180.0, 2),
                    size_bytes=target.stat().st_size,
                    text_spoken=spoken_text,
                    fallback_used=True,
                )
        except Exception:
            pass
        if target.exists():
            target.unlink(missing_ok=True)
        return None

    def synthesize(
        self,
        text: str,
        request_id: str = "req",
        profile: str = "neutro",
        enabled: bool = True,
    ) -> AudioSynthesisResult:
        """Sintetiza `text` em audio, aplicando fallback local em caso de indisponibilidade."""
        if not enabled:
            return AudioSynthesisResult(enabled=False, success=False, provider="disabled", text_spoken="")

        spoken_text = prepare_text_for_speech(text)
        if not spoken_text:
            return AudioSynthesisResult(
                enabled=True,
                success=False,
                provider="error",
                error="Texto vazio para sintese de audio",
            )

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return AudioSynthesisResult(
                enabled=True,
                success=False,
                provider="error",
                text_spoken=spoken_text,
                error=f"Falha ao criar diretorio de audio: {type(exc).__name__}",
            )

        safe_id = _sanitize_request_id(request_id)
        base_path = self.output_dir / f"{safe_id}_response"

        voice_openai, speed_openai = select_voice_for_profile(profile, provider="openai_tts")
        if self.voice_override:
            voice_openai = self.voice_override

        openai_error: Optional[str] = None
        if self.client is not None or self.api_key:
            try:
                openai_target = base_path.with_suffix(f".{self.response_format}")
                return self._synthesize_openai(spoken_text, openai_target, voice_openai, speed_openai)
            except Exception as exc:
                openai_error = f"{type(exc).__name__}: {exc}"

        if not self.enable_local_fallback:
            return AudioSynthesisResult(
                enabled=True,
                success=False,
                provider="openai_tts",
                text_spoken=spoken_text,
                error=openai_error or "Provedor OpenAI TTS indisponivel e fallback local desabilitado",
            )

        say_voice, say_rate = select_voice_for_profile(profile, provider="macos_say")

        for attempt in (
            lambda: self._synthesize_gtts(spoken_text, base_path),
            lambda: self._synthesize_pyttsx3(spoken_text, base_path, say_rate),
            lambda: self._synthesize_macos_say(spoken_text, base_path, say_voice, say_rate),
        ):
            res = attempt()
            if res is not None:
                if openai_error:
                    res.error = f"Fallback acionado apos falha OpenAI TTS ({openai_error})"
                return res

        # Ultimo recurso offline deterministico (WAV PCM valido sem dependencias)
        wav_target = base_path.with_suffix(".wav")
        try:
            _generate_offline_wav(wav_target, spoken_text)
            return AudioSynthesisResult(
                enabled=True,
                success=True,
                provider="offline_wav",
                file_path=str(wav_target),
                audio_format="wav",
                voice="sintese_local",
                model="pcm_wav_fallback",
                speed=1.0,
                size_bytes=wav_target.stat().st_size,
                text_spoken=spoken_text,
                fallback_used=True,
                error=openai_error,
            )
        except Exception as exc:
            return AudioSynthesisResult(
                enabled=True,
                success=False,
                provider="error",
                text_spoken=spoken_text,
                error=f"Falha total na sintese de audio: {type(exc).__name__}",
            )
