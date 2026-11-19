#!/usr/bin/env python3
"""Recalcula P@3 e nDCG@3 de runs ja executados com o gabarito ATUAL (docs/avaliacao/rotulos_osm_v1.json).

Os scores gravados no Langfuse foram calculados com os rotulos que existiam na hora do run; quando o gabarito
ganha rotulos (lugares novos entregues por uma variante), a comparacao justa e recalcular TODOS os runs com o
mesmo gabarito, sem rodar nada de novo (usa o `output` salvo em resultado_<run>.json).

  python scripts/avaliacao/recalcular_scores.py retrieval-pipeline-gate retrieval-agente-llm
"""

import json
import math
import sys
from pathlib import Path

AV = Path(__file__).resolve().parents[2] / "docs" / "avaliacao"


def dcg(gs):
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gs))


def carregar_gabarito():
    rot = json.loads((AV / "rotulos_osm_v1.json").read_text(encoding="utf-8"))["casos"]
    return {tid: {l["osm"]: l["grau"] for l in c["labels"]} for tid, c in rot.items() if c["acao_esperada"] == "recomendar" and c["labels"]}


def pontuar(entregues, rel):
    graus = [rel.get(e["osm"]) for e in entregues[:3]]
    p3 = sum(1 for g in graus if g and g >= 1) / 3
    ideal = sorted(rel.values(), reverse=True)[:3]
    ndcg = dcg([g or 0 for g in graus]) / dcg(ideal) if dcg(ideal) else None
    cob = (sum(g is not None for g in graus) / len(graus)) if graus else None
    return {"p3": p3, "ndcg": ndcg, "cobertura": cob, "graus": graus}


def main(nomes):
    gab = carregar_gabarito()
    tabela = {}
    for nome in nomes:
        run = json.loads((AV / f"resultado_{nome}.json").read_text(encoding="utf-8"))
        tabela[nome] = {i["id"]: pontuar(i["output"]["entregues"], gab[i["id"]]) for i in run["itens"] if i["id"] in gab}
    print(f"{'caso':6s} " + " ".join(f"{n[-22:]:>24s}" for n in nomes))
    for tid in sorted(gab):
        print(f"{tid:6s} " + " ".join(f"P@3={tabela[n][tid]['p3']:.2f} nDCG={tabela[n][tid]['ndcg'] if tabela[n][tid]['ndcg'] is None else format(tabela[n][tid]['ndcg'], '.2f'):>4} cob={tabela[n][tid]['cobertura']:.2f}".rjust(24) for n in nomes))
    print("\nmedias (gabarito atual):")
    resumo = {}
    for n in nomes:
        v = tabela[n].values()
        nd = [x["ndcg"] for x in v if x["ndcg"] is not None]
        resumo[n] = {"p3": sum(x["p3"] for x in v) / len(v), "ndcg": sum(nd) / len(nd), "cobertura": sum(x["cobertura"] for x in v) / len(v)}
        print(f"  {n:28s} P@3={resumo[n]['p3']:.3f}  nDCG@3={resumo[n]['ndcg']:.3f}  cobertura={resumo[n]['cobertura']:.2f}  (n={len(v)})")
    return tabela, resumo


if __name__ == "__main__":
    main(sys.argv[1:] or ["retrieval-pipeline-gate", "retrieval-agente-llm"])
