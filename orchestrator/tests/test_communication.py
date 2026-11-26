import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import wave

import pytest

from orchestrator.communication import (
    CommunicationAgent,
    communication_agent,
    generate_audio,
    transcribe_audio,
)


def make_state(profile="carla_mendes"):
    return {
        "user_profile": profile,
        "structured_request": {
            "intent_valid": True,
            "out_of_scope": False,
            "impossible_criteria": False,
            "activity": "café",
            "clarification_needed": None,
        },
        "search_response": {
            "items": [
                {
                    "place_id": "1",
                    "name": "Café Central",
                    "address": "Asa Sul",
                    "distance_km": 1.2,
                },
                {
                    "place_id": "2",
                    "name": "Espaço Verde",
                    "address": "Asa Norte",
                    "distance_km": 2.5,
                },
                {
                    "place_id": "3",
                    "name": "Praça Cultural",
                    "address": "Plano Piloto",
                    "distance_km": 3.0,
                },
            ]
        },
        "evidence_records": [
            {
                "place_id": "1",
                "place_name": "Café Central",
                "total_score": 0.95,
                "matched_tags": ["amenity=cafe"],
                "grounding_notes": ["Possui área de convivência."],
                "integrity_test": {"passed": True},
            },
            {
                "place_id": "2",
                "place_name": "Espaço Verde",
                "total_score": 0.85,
                "matched_tags": ["leisure=park"],
                "grounding_notes": ["Possui área verde."],
                "integrity_test": {"passed": True},
            },
            {
                "place_id": "3",
                "place_name": "Praça Cultural",
                "total_score": 0.75,
                "matched_tags": ["leisure=common"],
                "grounding_notes": ["Possui espaço público."],
                "integrity_test": {"passed": True},
            },
        ],
    }


def test_communication_presents_top_three():
    result = communication_agent(make_state())

    assert "Café Central" in result["final_response"]
    assert "Espaço Verde" in result["final_response"]
    assert "Praça Cultural" in result["final_response"]
    assert "1.20 km" in result["final_response"]
    assert "final_audio_path" in result
    assert Path(result["final_audio_path"]).exists()


def test_communication_adapts_to_dona_helena():
    result = communication_agent(make_state("dona_helena"))

    assert "com calma" in result["final_response"]
    assert "Por que foi recomendado" in result["final_response"]
    assert "final_audio_path" in result


def test_communication_abstains_without_evidence():
    state = make_state()
    state["evidence_records"] = []

    result = communication_agent(state)

    assert "Não encontrei locais" in result["final_response"]


def test_communication_ignores_evidence_without_approval():
    state = make_state()
    state["evidence_records"][0]["integrity_test"]["passed"] = False

    result = communication_agent(state)

    assert "Café Central" not in result["final_response"]


def test_transcribe_audio_file_not_found():
    with pytest.raises(FileNotFoundError, match="Arquivo de áudio não encontrado"):
        transcribe_audio("/caminho/inexistente/audio.wav")


def test_transcribe_audio_empty_file(tmp_path):
    empty_file = tmp_path / "vazio.wav"
    empty_file.write_bytes(b"")

    with pytest.raises(ValueError, match="vazio"):
        transcribe_audio(str(empty_file))


def test_transcribe_audio_file_too_large(tmp_path):
    large_file = tmp_path / "grande.wav"
    large_file.write_bytes(b"fake data")

    with patch.object(Path, "stat") as mock_stat:
        mock_stat_res = MagicMock()
        mock_stat_res.st_size = 26 * 1024 * 1024  # 26 MB
        mock_stat.return_value = mock_stat_res

        with pytest.raises(ValueError, match="ultrapassa 25 MB"):
            transcribe_audio(str(large_file))


def test_transcribe_audio_invalid_ssl_env(tmp_path, monkeypatch):
    test_file = tmp_path / "audio.wav"
    test_file.write_bytes(b"RIFF....WAVE")

    monkeypatch.setenv("WHISPER_VERIFY_SSL", "invalido")
    with patch("orchestrator.communication._WHISPER_MODEL", None):
        with pytest.raises(ValueError, match="WHISPER_VERIFY_SSL deve ser true ou false"):
            transcribe_audio(str(test_file))


def test_transcribe_audio_success(tmp_path):
    audio_file = tmp_path / "fala.wav"
    audio_file.write_bytes(b"RIFF....WAVE")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "  Quero um café calmo na Asa Sul  "}

    with patch("orchestrator.communication._get_whisper_model", return_value=mock_model):
        texto = transcribe_audio(str(audio_file))
        assert texto == "Quero um café calmo na Asa Sul"
        mock_model.transcribe.assert_called_once_with(str(audio_file), language="pt", fp16=False)


def test_transcribe_audio_no_speech_detected(tmp_path):
    audio_file = tmp_path / "silencio.wav"
    audio_file.write_bytes(b"RIFF....WAVE")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "   "}

    with patch("orchestrator.communication._get_whisper_model", return_value=mock_model):
        with pytest.raises(ValueError, match="Não foi possível reconhecer a fala"):
            transcribe_audio(str(audio_file))


def test_generate_audio_empty_text():
    with pytest.raises(ValueError, match="vazio"):
        generate_audio("")

    with pytest.raises(ValueError, match="vazio"):
        generate_audio("    ")


def test_generate_audio_creates_valid_wav(tmp_path):
    output_path = tmp_path / "saida_teste.wav"
    res_path = generate_audio("Olá Dona Helena, encontrei cafés tranquilos na Asa Sul.", output_path=str(output_path))

    assert res_path == str(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    with wave.open(str(output_path), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
        assert w.getsampwidth() == 2
        assert w.getnframes() > 0


def test_communication_agent_disabled_audio():
    state = make_state()
    state["generate_audio"] = False

    result = communication_agent(state)
    assert "Café Central" in result["final_response"]
    assert "final_audio_path" not in result
    assert "audio_path" not in result


def test_communication_agent_transcribes_input_audio(tmp_path):
    audio_file = tmp_path / "entrada.wav"
    audio_file.write_bytes(b"RIFF....WAVE")

    with patch("orchestrator.communication.transcribe_audio", return_value="Pedido falado"):
        result = communication_agent({"audio_path": str(audio_file)})
        assert result["raw_query"] == "Pedido falado"
        assert result["transcription"] == "Pedido falado"


def test_communication_agent_class(tmp_path):
    agent = CommunicationAgent(generate_audio=True)

    # Test transcribe method
    audio_file = tmp_path / "audio_class.wav"
    audio_file.write_bytes(b"RIFF....WAVE")
    with patch("orchestrator.communication.transcribe_audio", return_value="Texto teste"):
        assert agent.transcribe(str(audio_file)) == "Texto teste"

    # Test generate_audio method
    out_audio = tmp_path / "audio_out.wav"
    created = agent.generate_audio("Mensagem teste", output_path=str(out_audio))
    assert Path(created).exists()

    # Test callable interface
    state = make_state()
    res = agent(state)
    assert "final_response" in res
    assert "final_audio_path" in res
