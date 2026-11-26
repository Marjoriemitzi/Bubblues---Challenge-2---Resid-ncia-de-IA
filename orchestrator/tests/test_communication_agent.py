"""Testes unitarios e de integracao para Communication_Agent e sintese de audio (TTS)."""

from __future__ import annotations

import wave
from pathlib import Path

from orchestrator import (
    AudioSynthesizer,
    CommunicationAgent,
    build_graph,
    run,
    validation_agent,
)
from orchestrator.audio import prepare_text_for_speech, select_voice_for_profile
from orchestrator.contracts import AppliedFilters, ScoreDecomposition, SearchItem, SearchResponse
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, VALIDATION
from orchestrator.stubs import _request, stub_nlu


class _FakeSpeechResponse:
    def __init__(self, payload: bytes):
        self.content = payload

    def stream_to_file(self, path: str) -> None:
        Path(path).write_bytes(self.content)


class _FakeSpeechEndpoint:
    def __init__(self, payload: bytes = b"ID3FAKEAUDIOBYTES", fail: bool = False):
        self.payload = payload
        self.fail = fail
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("OpenAI TTS timeout simulado")
        return _FakeSpeechResponse(self.payload)


class _FakeOpenAIClient:
    def __init__(self, payload: bytes = b"ID3FAKEAUDIOBYTES", fail: bool = False):
        self.speech_endpoint = _FakeSpeechEndpoint(payload=payload, fail=fail)
        self.audio = type("_Audio", (), {"speech": self.speech_endpoint})()


def _sample_state(tmp_path: Path, profile: str = "dona_helena") -> dict:
    return {
        "request_id": "req-comm-01",
        "user_profile": profile,
        "structured_request": _request(
            "req-comm-01",
            accessibility_requirements={"wheelchair_required": True, "elder_friendly": True},
        ),
        "search_response": {
            "query_id": "req-comm-01",
            "status": "SUCCESS",
            "applied_filters": {"radius_km": 3.0, "expanded_once": False, "amenities": ["cafe"]},
            "results_count": 2,
            "items": [
                {
                    "rank": 1,
                    "place_id": "POI-01",
                    "name": "Ernesto Cafés Especiais",
                    "amenity": "cafe",
                    "address": "CLS 115 Bloco C, Asa Sul",
                    "distance_km": 1.2,
                    "cosine_similarity": 0.92,
                    "final_score": 0.86,
                    "score_decomposition": {
                        "vector_contribution": 0.36,
                        "distance_contribution": 0.20,
                        "reputation_contribution": 0.15,
                        "compatibility_contribution": 0.15,
                        "sum_check": 0.86,
                    },
                },
                {
                    "rank": 2,
                    "place_id": "POI-03",
                    "name": "Sephinah Casa de Chá e Cafeteria",
                    "amenity": "cafe",
                    "address": "CLS 403 Bloco B, Asa Sul",
                    "distance_km": 1.8,
                    "cosine_similarity": 0.88,
                    "final_score": 0.82,
                    "score_decomposition": {
                        "vector_contribution": 0.32,
                        "distance_contribution": 0.20,
                        "reputation_contribution": 0.15,
                        "compatibility_contribution": 0.15,
                        "sum_check": 0.82,
                    },
                },
            ],
        },
        "evidence_records": [
            {
                "evidence_id": "EV-11111111",
                "query_id": "req-comm-01",
                "place_id": "POI-01",
                "place_name": "Ernesto Cafés Especiais",
                "osm_reference": {
                    "osm_id": 482910482,
                    "osm_type": "node",
                    "osm_link": "https://www.openstreetmap.org/node/482910482",
                },
                "matched_tags": ["cafe", "calmo", "acessivel"],
                "factors": [],
                "total_score": 0.86,
                "integrity_test": {"sum_equals_total": True, "all_factors_in_range_0_1": True, "passed": True},
                "grounding_notes": ["Acessibilidade confirmada: wheelchair=yes."],
            },
            {
                "evidence_id": "EV-22222222",
                "query_id": "req-comm-01",
                "place_id": "POI-03",
                "place_name": "Sephinah Casa de Chá e Cafeteria",
                "osm_reference": {
                    "osm_id": 593817261,
                    "osm_type": "node",
                    "osm_link": "https://www.openstreetmap.org/node/593817261",
                },
                "matched_tags": ["cafe", "silencioso"],
                "factors": [],
                "total_score": 0.82,
                "integrity_test": {"sum_equals_total": True, "all_factors_in_range_0_1": True, "passed": True},
                "grounding_notes": ["Ambiente silencioso ideal para leitura."],
            },
        ],
    }


def test_prepare_text_for_speech_removes_urls_and_markdown():
    raw = (
        "**1. Café Central** (OSM: node/123)\n"
        "• Distância: 1.50 km\n"
        "Verificado no OpenStreetMap (https://www.openstreetmap.org/node/123).\n"
        "Referência OSM: https://www.openstreetmap.org/node/123"
    )
    spoken = prepare_text_for_speech(raw)
    assert "**" not in spoken
    assert "https://" not in spoken
    assert "OSM: node/123" not in spoken
    assert "(" not in spoken
    assert "Referência OSM" not in spoken
    assert "1.50 quilômetros" in spoken
    assert "Café Central" in spoken


def test_select_voice_for_profile_adapts_cadence():
    voice_h, speed_h = select_voice_for_profile("dona_helena")
    voice_c, speed_c = select_voice_for_profile("carla")
    assert voice_h == "nova"
    assert speed_h < 1.0
    assert voice_c == "alloy"
    assert speed_c > 1.0


def test_audio_synthesizer_openai_tts_mock(tmp_path):
    fake_client = _FakeOpenAIClient(payload=b"FAKE_MP3_STREAM")
    synth = AudioSynthesizer(output_dir=tmp_path, client=fake_client)

    res = synth.synthesize("Olá! Café tranquilo encontrado.", request_id="../req/unsafe?1", profile="helena")

    assert res.success is True
    assert res.provider == "openai_tts"
    assert res.fallback_used is False
    assert res.audio_format == "mp3"
    assert res.voice == "nova"
    assert res.speed < 1.0
    assert res.file_path is not None
    out_file = Path(res.file_path)
    assert out_file.exists()
    assert out_file.parent == tmp_path
    assert out_file.read_bytes() == b"FAKE_MP3_STREAM"
    assert fake_client.speech_endpoint.calls[0]["model"] == "tts-1"


def test_audio_synthesizer_falls_back_locally_when_openai_fails(tmp_path):
    failing_client = _FakeOpenAIClient(fail=True)
    synth = AudioSynthesizer(output_dir=tmp_path, client=failing_client)

    res = synth.synthesize("Locais verificados na Asa Sul.", request_id="req-fallback", profile="neutro")

    assert res.success is True
    assert res.fallback_used is True
    assert res.provider in ("gtts", "pyttsx3", "macos_say", "offline_wav")
    assert res.file_path is not None
    out_file = Path(res.file_path)
    assert out_file.exists()
    assert res.size_bytes > 0
    if res.audio_format == "wav":
        with wave.open(str(out_file), "rb") as wf:
            assert wf.getnframes() > 0


def test_audio_synthesizer_disabled(tmp_path):
    synth = AudioSynthesizer(output_dir=tmp_path)
    res = synth.synthesize("Texto qualquer", request_id="req-off", enabled=False)

    assert res.enabled is False
    assert res.success is False
    assert res.provider == "disabled"
    assert res.file_path is None


def test_communication_agent_generates_grounded_text_and_audio(tmp_path):
    fake_client = _FakeOpenAIClient(payload=b"AUDIO_OK")
    agent = CommunicationAgent(
        audio_synthesizer=AudioSynthesizer(output_dir=tmp_path, client=fake_client),
        enable_audio=True,
    )
    state = _sample_state(tmp_path, profile="dona_helena")

    result = agent(state)

    assert "Ernesto Cafés Especiais" in result["final_response"]
    assert "Sephinah Casa de Chá e Cafeteria" in result["final_response"]
    assert "com calma" in result["final_response"]
    assert result["audio_output"]["success"] is True
    assert result["audio_output"]["provider"] == "openai_tts"
    assert Path(result["audio_output"]["file_path"]).exists()


def test_communication_agent_ignores_unapproved_evidence(tmp_path):
    agent = CommunicationAgent(audio_output_dir=tmp_path, enable_audio=True)
    state = _sample_state(tmp_path)
    state["evidence_records"][0]["integrity_test"]["passed"] = False

    result = agent(state)

    assert "Ernesto Cafés Especiais" not in result["final_response"]
    assert "Sephinah Casa de Chá e Cafeteria" in result["final_response"]
    assert result["audio_output"]["success"] is True


def test_communication_agent_abstains_with_audio_on_out_of_scope(tmp_path):
    agent = CommunicationAgent(audio_output_dir=tmp_path, enable_audio=True)
    state = {
        "request_id": "req-oos",
        "structured_request": _request(
            "req-oos",
            intent_valid=False,
            out_of_scope=True,
            out_of_scope_reason="Frete comercial não faz parte do Bubbles.",
        ),
    }

    result = agent(state)

    assert "fora do escopo" in result["final_response"]
    assert "Frete comercial" in result["final_response"]
    assert result["audio_output"]["success"] is True
    assert Path(result["audio_output"]["file_path"]).exists()


def test_communication_agent_respects_state_audio_flag(tmp_path):
    agent = CommunicationAgent(audio_output_dir=tmp_path, enable_audio=True)
    state = _sample_state(tmp_path)
    state["audio_enabled"] = False

    result = agent(state)

    assert "Ernesto Cafés Especiais" in result["final_response"]
    assert result["audio_output"]["enabled"] is False
    assert result["audio_output"]["provider"] == "disabled"


def test_langgraph_end_to_end_with_validation_and_audio_communication(tmp_path):
    fake_client = _FakeOpenAIClient(payload=b"E2E_AUDIO")
    comm = CommunicationAgent(
        audio_synthesizer=AudioSynthesizer(output_dir=tmp_path, client=fake_client),
        enable_audio=True,
    )

    def retrieval_valido(state):
        return {
            "search_response": SearchResponse(
                query_id=state["request_id"],
                status="EXPANDED_RADIUS",
                applied_filters=AppliedFilters(radius_km=8.0, expanded_once=True, amenities=["cafe"]),
                results_count=1,
                items=[
                    SearchItem(
                        rank=1,
                        place_id="POI-01",
                        name="Ernesto Cafés Especiais",
                        amenity="cafe",
                        address="CLS 115 Bloco C, Asa Sul",
                        distance_km=1.2,
                        cosine_similarity=0.92,
                        final_score=0.86,
                        score_decomposition=ScoreDecomposition(
                            vector_contribution=0.36,
                            distance_contribution=0.20,
                            reputation_contribution=0.15,
                            compatibility_contribution=0.15,
                            sum_check=0.86,
                        ),
                    )
                ],
            )
        }

    graph = build_graph(
        nlu=stub_nlu(),
        retrieval=retrieval_valido,
        validation=validation_agent,
        communication=comm,
    )

    query_sensivel = "Sou a Dona Helena e preciso de um café tranquilo na Asa Sul"
    final_state = run(graph, query_sensivel, "req-e2e-audio")

    assert [t.agent for t in final_state["agent_trace"]] == [NLU, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert final_state["raw_query"] is None
    assert "Dona Helena" not in final_state["agent_trace"][-1].note
    assert "Ernesto Cafés Especiais" in final_state["final_response"]
    assert "raio da busca foi ampliado" in final_state["final_response"]
    assert final_state["audio_output"]["success"] is True
    assert Path(final_state["audio_output"]["file_path"]).exists()
