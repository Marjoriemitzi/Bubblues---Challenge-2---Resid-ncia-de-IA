#!/usr/bin/env python3
"""Executa o orquestrador com os agentes REAIS de Retrieval e Validation (PostgreSQL).

NLU e Communication ainda sao stubs: o pedido vem dos argumentos abaixo, nao de texto livre.
Grava em evidencias_busca e evidencias_auditoria no banco do .env (data-pipeline/.env).

Exemplos:
  python scripts/run_orquestrador.py --regiao "Asa Sul" --categoria cafe --raio-km 2
  python scripts/run_orquestrador.py --categoria park --sem-acessibilidade --sem-modelo
  python scripts/run_orquestrador.py --regiao "Narnia"          # pede esclarecimento

--sem-modelo: nao baixa o sentence-transformers; usa o vetor de um lugar da categoria como
consulta (so para testar o fluxo; a ordem dos resultados nao reflete a vibe).
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.evidence_store import PostgresEvidenceStore  # noqa: E402
from orchestrator.graph import build_graph, run  # noqa: E402
from orchestrator.retrieval_common import _pipeline  # noqa: E402
from orchestrator.retrieval_pipeline import RetrievalPipeline  # noqa: E402
from orchestrator.stubs import stub_communication, stub_nlu  # noqa: E402
from orchestrator.validation_tool import EvidenceValidator  # noqa: E402


def _embedding_de_lugar(categoria):
    busca = _pipeline()[0]
    with busca.conectar() as con:
        linha = con.execute(
            "SELECT embedding::text FROM places WHERE categoria = %s AND embedding IS NOT NULL "
            "ORDER BY place_id LIMIT 1",
            (categoria,),
        ).fetchone()
    if not linha:
        sys.exit(f"Nenhum lugar com embedding na categoria '{categoria}'.")
    return json.loads(linha[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regiao", help="Ex.: 'Asa Sul'. Sem isso, usa o centro de Brasilia.")
    ap.add_argument("--categoria", default="cafe", help="places.categoria (cafe, park, restaurant...)")
    ap.add_argument("--atividade", default="conversa", help="vira parte do embedding da consulta")
    ap.add_argument("--vibe", default="tranquilo", help="vira parte do embedding da consulta")
    ap.add_argument("--raio-km", type=float, default=3.0)
    ap.add_argument("--ruido", choices=("baixo", "moderado", "indiferente"), default="baixo")
    ap.add_argument("--horario", help="preferred_time_slot, ex.: madrugada, tarde")
    ap.add_argument("--sem-acessibilidade", action="store_true", help="nao exige wheelchair=yes")
    ap.add_argument("--sem-modelo", action="store_true", help="nao carrega o sentence-transformers")
    ap.add_argument("--request-id", default=f"run-{uuid.uuid4().hex[:8]}")
    args = ap.parse_args()

    retrieval = RetrievalPipeline()
    if args.sem_modelo:
        vetor = _embedding_de_lugar(args.categoria)
        retrieval = RetrievalPipeline(embedder=lambda texto: vetor)

    grafo = build_graph(
        nlu=stub_nlu(
            target_amenities=[args.categoria],
            activity=args.atividade,
            vibe=args.vibe,
            noise_tolerance=args.ruido,
            spatial_constraints={"target_region": args.regiao, "max_radius_km": args.raio_km},
            temporal_constraints={"preferred_time_slot": args.horario},
            accessibility_requirements={"wheelchair_required": not args.sem_acessibilidade},
        ),
        retrieval=retrieval,
        validation=EvidenceValidator(store=PostgresEvidenceStore()),
        communication=stub_communication,
    )
    s = run(grafo, "(texto livre nao usado: NLU e stub)", args.request_id)

    print(f"request_id: {args.request_id}")
    for t in s["agent_trace"]:
        print(f"  {t.agent:22s} -> {t.next_agent:22s} {t.justification}")
    if s.get("error"):
        print(f"erro: {s['error']}")
    resp = s.get("search_response")
    if resp:
        print(f"busca: status={resp.status} n={resp.results_count} raio={resp.applied_filters.radius_km}km")
    for e in s.get("evidence_records", []):
        print(f"  ✔ {e.place_name} | score={e.total_score:.3f} | {e.osm_reference.osm_link}")
    fb = s.get("validation_feedback")
    if fb and not fb.approved:
        print(f"  ✘ reprovados: {fb.rejected_place_ids} | {fb.diagnostics[:2]}")
    print(f"resposta: {s.get('final_response')}")


if __name__ == "__main__":
    main()
