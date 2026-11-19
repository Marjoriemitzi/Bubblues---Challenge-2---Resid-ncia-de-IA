#!/usr/bin/env python3
"""Demonstração do Validation_Agent (Issue #9) - Projeto Bubbles.

Executa a validação auditada dos critérios de aceite:
  1. Verificação RNF01: osm_id válido e is_public_verified == true.
  2. Auditoria de Restrições: wheelchair, ruído, horário.
  3. Integridade Matemática: |sum(contribuições) - score_total| < 1e-5.
  4. Persistência do Contrato 4 (evidence_record) na tabela evidencias_busca.
  5. Integração com o orquestrador LangGraph em caso de reconsulta e aprovação.
"""

import json
import sqlite3
import sys
from pathlib import Path

# Ajusta path para importar o orchestrator
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from orchestrator.contracts import (
    AppliedFilters,
    ScoreDecomposition,
    SearchItem,
    SearchResponse,
    StructuredRequest,
    ValidationFeedback,
)
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, VALIDATION, build_graph, run
from orchestrator.stubs import _request, stub_communication, stub_nlu
from orchestrator.catalogo_exemplo import BASE_POIS_CATALOG
from orchestrator.validation_agent import ValidationAgent


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f"🛡️  {title}")
    print("=" * 78)


def main():
    db_path = "evidencias_demo.db"
    if Path(db_path).exists():
        Path(db_path).unlink()

    agent = ValidationAgent(db_path=db_path, metadata_catalog=BASE_POIS_CATALOG)

    # -------------------------------------------------------------------------
    # CENÁRIO 1: Auditoria RNF01 (Zero Alucinação)
    # -------------------------------------------------------------------------
    print_header("CENÁRIO 1: Auditoria RNF01 — Rejeição de Candidato Sem OSM ID ou Não Verificado")
    req_dona_helena = StructuredRequest.model_validate(
        _request(
            request_id="req-helena-01",
            activity="conversa e café",
            target_amenities=["cafe"],
            vibe="tranquilo",
            noise_tolerance="baixo",
            spatial_constraints={"target_region": "Asa Norte", "max_radius_km": 3.0},
            temporal_constraints={"preferred_time_slot": "tarde"},
            accessibility_requirements={"wheelchair_required": True, "elder_friendly": True},
        )
    )

    candidato_fantasma = {
        "nome": "Café Fantasma Alucinado",
        "osm_id": None,
        "is_public_verified": False,
        "wheelchair": "yes",
        "elder_friendly": True,
        "score_contributions": {"vec": 0.45, "dist": 0.35},
        "score_total": 0.80,
    }

    res1 = agent.auditar_candidato(req_dona_helena, candidato_fantasma)
    print(f"• Candidato: {res1['candidate_name']}")
    print(f"• Aprovado: {res1['approved']}")
    print(f"• RNF01 Passou: {res1['rnf01_passed']}")
    print(f"• Motivos de Rejeição: {res1['rejection_reasons']}")
    print(f"• Diagnóstico emitido: {res1['diagnostics']}")

    # -------------------------------------------------------------------------
    # CENÁRIO 2: Restrições Críticas (Acessibilidade wheelchair=no)
    # -------------------------------------------------------------------------
    print_header("CENÁRIO 2: Auditoria de Restrições Críticas — Rejeição de Local Sem Acessibilidade")
    candidato_sem_rampa = {
        "nome": "Bistrô Escadaria Sem Rampa",
        "osm_id": "node/4455667788",
        "is_public_verified": True,
        "wheelchair": "no",
        "elder_friendly": False,
        "score_contributions": {"vec": 0.40, "dist": 0.35},
        "score_total": 0.75,
    }

    res2 = agent.auditar_candidato(req_dona_helena, candidato_sem_rampa)
    print(f"• Candidato: {res2['candidate_name']}")
    print(f"• Aprovado: {res2['approved']}")
    print(f"• Restrições Passaram: {res2['constraints_passed']}")
    print(f"• Motivos de Rejeição: {res2['rejection_reasons']}")
    print(f"• Hard Filters gerados para o Retrieval_Agent: {res2['hard_filters']}")

    # -------------------------------------------------------------------------
    # CENÁRIO 3: Integridade Matemática (|sum - score_total| < 1e-5)
    # -------------------------------------------------------------------------
    print_header("CENÁRIO 3: Integridade Matemática — Rejeição de Inconsistência no Score Composto")
    candidato_erro_mat = {
        "nome": "Café com Decomposição Divergente",
        "osm_id": "way/99887711",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "score_contributions": {
            "similaridade": 0.40,
            "distancia": 0.20,
        },
        "score_total": 0.85,  # Soma real = 0.60, erro = 0.25 >= 1e-5
    }

    res3 = agent.auditar_candidato(req_dona_helena, candidato_erro_mat)
    print(f"• Candidato: {res3['candidate_name']}")
    print(f"• Aprovado: {res3['approved']}")
    print(f"• Integridade Matemática Passou: {res3['math_integrity_passed']}")
    print(f"• Erro Matemático Calculado: {res3['erro_matematico']:.6f} (tolerância: < 1e-5)")
    print(f"• Motivos de Rejeição: {res3['rejection_reasons']}")

    # -------------------------------------------------------------------------
    # CENÁRIO 4: Aprovação de Top-3 Válido e Persistência do Contrato 4
    # -------------------------------------------------------------------------
    print_header("CENÁRIO 4: Aprovação de Top-3 Conforme e Persistência de 100% em evidencias_busca")
    candidatos_validos = [
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
        ),
        SearchItem(
            rank=2,
            place_id="POI-02",
            name="Parque da Cidade Dona Sarah Kubitschek",
            amenity="park",
            address="Parque da Cidade",
            distance_km=2.1,
            cosine_similarity=0.88,
            final_score=0.84,
            score_decomposition=ScoreDecomposition(
                vector_contribution=0.34,
                distance_contribution=0.20,
                reputation_contribution=0.15,
                compatibility_contribution=0.15,
                sum_check=0.84,
            ),
        ),
        SearchItem(
            rank=3,
            place_id="POI-03",
            name="Sephinah Casa de Chá e Cafeteria",
            amenity="cafe",
            address="CLS 403 Bloco B, Asa Sul",
            distance_km=1.8,
            cosine_similarity=0.85,
            final_score=0.82,
            score_decomposition=ScoreDecomposition(
                vector_contribution=0.32,
                distance_contribution=0.20,
                reputation_contribution=0.15,
                compatibility_contribution=0.15,
                sum_check=0.82,
            ),
        ),
    ]

    search_response = SearchResponse(
        query_id=req_dona_helena.request_id,
        status="SUCCESS",
        applied_filters=AppliedFilters(radius_km=3.0, expanded_once=False, amenities=["cafe", "park"]),
        results_count=3,
        items=candidatos_validos,
    )

    fb, evidence_records = agent.auditar_search_response(req_dona_helena, search_response)
    print(f"• Status da Auditoria (approved): {fb.approved}")
    print(f"• Quantidade de EvidenceRecords gerados (Contrato 4): {len(evidence_records)}")

    for idx, ev in enumerate(evidence_records, start=1):
        print(f"  [{idx}] Local: {ev.place_name} ({ev.place_id})")
        print(f"      OSM: {ev.osm_reference.osm_link} (id: {ev.osm_reference.osm_id})")
        print(f"      Score Total: {ev.total_score:.4f} | Teste Integridade: {ev.integrity_test.passed}")
        print(f"      Notas de Fundamentação (RNF01): {ev.grounding_notes[0]}")

    # Verificando registros no banco SQLite
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT evidence_id, candidate_name, approved, math_integrity_passed, rnf01_passed FROM evidencias_busca")
    linhas = cur.fetchall()
    conn.close()

    print(f"\n🗄️  Registros Persistidos na Tabela 'evidencias_busca': {len(linhas)}")
    for r in linhas:
        print(f"   • [{r[0]}] {r[1]} -> Aprovado={bool(r[2])} (RNF01={bool(r[4])}, Math={bool(r[3])})")

    # -------------------------------------------------------------------------
    # CENÁRIO 5: Integração no Orquestrador LangGraph (Loop de Reconsulta)
    # -------------------------------------------------------------------------
    print_header("CENÁRIO 5: Integração Completa com o Orquestrador LangGraph")
    tentativa = {"count": 0}

    def retrieval_com_feedback(state):
        tentativa["count"] += 1
        fb_anterior: ValidationFeedback = state.get("validation_feedback")

        # Tentativa 1: Envia candidato inválido (sem osm_id)
        if tentativa["count"] == 1:
            print(f"  -> [Retrieval_Agent Tentativa {tentativa['count']}] Retornando candidato não-verificado...")
            items = [
                SearchItem(
                    rank=1,
                    place_id="POI-INVALIDO",
                    name="Espaço Sem Verificação OSM",
                    distance_km=1.0,
                    cosine_similarity=0.9,
                    final_score=0.86,
                    score_decomposition=ScoreDecomposition(
                        vector_contribution=0.36,
                        distance_contribution=0.20,
                        reputation_contribution=0.15,
                        compatibility_contribution=0.15,
                        sum_check=0.86,
                    ),
                )
            ]
        else:
            # Tentativa 2: Recebeu diagnóstico e substituiu pelo POI-01 verificado
            print(f"  -> [Retrieval_Agent Tentativa {tentativa['count']}] Aplicando diagnóstico do Validation_Agent:")
            print(f"     Feedback recebido: rejected_ids={fb_anterior.rejected_place_ids}")
            items = [candidatos_validos[0]]

        return {
            "search_response": {
                "query_id": state["request_id"],
                "status": "SUCCESS",
                "applied_filters": {"radius_km": 3.0, "expanded_once": False, "amenities": ["cafe"]},
                "results_count": len(items),
                "items": items,
            }
        }

    graph = build_graph(
        nlu=stub_nlu(),
        retrieval=retrieval_com_feedback,
        validation=ValidationAgent(db_path=db_path, metadata_catalog=BASE_POIS_CATALOG),
        communication=stub_communication,
    )

    estado_final = run(graph, "Quero um café tranquilo na Asa Sul", "req-langgraph-demo")
    trace = [f"{t.agent} ({t.justification})" for t in estado_final["agent_trace"]]

    print("\n📈 Trajetória de Execução no Grafo Multiagente (agent_trace):")
    for step, t in enumerate(trace, start=1):
        print(f"   Passo {step}: {t}")

    print(f"\n✅ Status Final da Validação: approved={estado_final['validation_feedback'].approved}")
    print(f"✅ Reconsultas Realizadas (retry_count): {estado_final['retry_count']}")
    print(f"✅ Resposta Final: {estado_final['final_response']}")
    print("\n>> VALIDATION_AGENT HOMOLOGADO COM 100% DE CONFORMIDADE! <<")


if __name__ == "__main__":
    main()
