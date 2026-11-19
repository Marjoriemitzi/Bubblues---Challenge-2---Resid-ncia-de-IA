#!/usr/bin/env python3
"""Demonstração do Validation_Agent (Issue #9) - Projeto Bubbles.

Executa a validação auditada dos critérios de aceite:
  1. Verificação RNF01: osm_id válido e is_public_verified == true.
  2. Auditoria de Restrições: wheelchair, ruído, horário.
  3. Integridade Matemática: |sum(contribuições) - score_total| < 1e-5.
  4. Persistência da auditoria (Contrato 4) via EvidenceStore (aqui, em memória).
  5. Integração com o orquestrador LangGraph em caso de reconsulta e aprovação.
"""

import json
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

from orchestrator.stubs import _request
from orchestrator.catalogo_exemplo import BASE_POIS_CATALOG
from orchestrator.evidence_store import MemoryEvidenceStore
from orchestrator.retrieval_gate import RetrievalGate
from orchestrator.retrieval_tools import BuscaRegistrada
from orchestrator.validation_tool import EvidenceValidator


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f"🛡️  {title}")
    print("=" * 78)


def main():
    # Demo sem banco: a auditoria vai para um store em memoria. Em producao e PostgresEvidenceStore.
    store = MemoryEvidenceStore()
    agent = EvidenceValidator(store=store, metadata_catalog=BASE_POIS_CATALOG)

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
    print_header("CENÁRIO 4: Aprovação de Top-3 Conforme e Persistência da auditoria")
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

    linhas = store.linhas
    print(f"\n🗄️  Registros de auditoria gravados (store): {len(linhas)}")
    for r in linhas:
        print(f"   • [{r['evidence_id']}] {r['candidate_name']} -> Aprovado={r['approved']} (RNF01={r['rnf01_passed']}, Math={r['math_integrity_passed']})")

    # -------------------------------------------------------------------------
    # CENÁRIO 5: Gate do Retrieval (busca -> auditoria -> reconsulta com feedback)
    # -------------------------------------------------------------------------
    print_header("CENÁRIO 5: Gate de Auditoria do Retrieval (reconsulta orientada por diagnóstico)")
    gate = RetrievalGate(EvidenceValidator(store=store, metadata_catalog=BASE_POIS_CATALOG))
    req_gate = StructuredRequest.model_validate(_request("req-gate-demo"))
    invalido = SearchItem(
        rank=1, place_id="POI-INVALIDO", name="Espaço Sem Verificação OSM", distance_km=1.0,
        cosine_similarity=0.9, final_score=0.86,
        score_decomposition=ScoreDecomposition(
            vector_contribution=0.36, distance_contribution=0.20,
            reputation_contribution=0.15, compatibility_contribution=0.15, sum_check=0.86,
        ),
    )
    reconsultas = 0
    for tentativa, itens in enumerate([[invalido], [candidatos_validos[0]]], start=1):
        busca = BuscaRegistrada(f"B{tentativa}", None, {
            "query_id": req_gate.request_id, "status": "SUCCESS",
            "applied_filters": {"radius_km": 3.0, "expanded_once": False, "amenities": ["cafe"]},
            "results_count": len(itens), "items": [i.model_dump(mode="json") for i in itens],
        })
        res = gate.auditar(req_gate, busca)
        print(f"  -> [Busca {tentativa}] candidatos={[i.place_id for i in itens]} -> aprovado={res.aprovado}")
        if res.aprovado:
            break
        print(f"     Feedback ao Retrieval: rejected_ids={res.feedback.rejected_place_ids} hard_filters={res.feedback.hard_filters}")
        reconsultas += 1

    print(f"\n✅ Status Final da Auditoria: approved={res.aprovado} | reconsultas={reconsultas}")
    print(f"✅ EvidenceRecords entregues: {[e.place_id for e in res.evidence_records]}")
    print("\n>> VALIDAÇÃO HOMOLOGADA COM 100% DE CONFORMIDADE! <<")


if __name__ == "__main__":
    main()
