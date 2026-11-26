#!/usr/bin/env python3
"""Demonstracao do Communication_Agent com saida em audio (TTS) integrado ao LangGraph."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from orchestrator import CommunicationAgent, build_graph, run, validation_agent
from orchestrator.contracts import AppliedFilters, ScoreDecomposition, SearchItem, SearchResponse
from orchestrator.stubs import stub_nlu


def retrieval_demo(state):
    return {
        "search_response": SearchResponse(
            query_id=state["request_id"],
            status="SUCCESS",
            applied_filters=AppliedFilters(radius_km=3.0, expanded_once=False, amenities=["cafe"]),
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


def main():
    comm = CommunicationAgent(audio_output_dir="audio_outputs", enable_audio=True)
    graph = build_graph(
        nlu=stub_nlu(),
        retrieval=retrieval_demo,
        validation=validation_agent,
        communication=comm,
    )

    state = run(graph, "Quero um café tranquilo na Asa Sul com acesso para cadeirantes", "req-demo-audio")
    print("=== RESPOSTA TEXTUAL ===")
    print(state["final_response"])
    print("\n=== SAIDA DE AUDIO ===")
    print(state["audio_output"])


if __name__ == "__main__":
    main()
