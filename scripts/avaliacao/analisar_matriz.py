#!/usr/bin/env python3
"""Analise da Fase F: varias repeticoes por configuracao, mesmo gabarito, e o que ainda nao tem rotulo.

  python scripts/avaliacao/analisar_matriz.py            # tabela + lugares entregues sem rotulo
  python scripts/avaliacao/analisar_matriz.py --md       # grava docs/avaliacao/fase_f_resultados.md

Le docs/avaliacao/resultado_f-<config>-r<k>.json e rotulos_osm_v1.json (gabarito vigente).
"""

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

AV = Path(__file__).resolve().parents[2] / "docs" / "avaliacao"
sys.path.insert(0, str(Path(__file__).parent))
from recalcular_scores import carregar_gabarito, pontuar  # noqa: E402

CONFIGS = ["pipeline", "flash", "flash-strict", "flash-thinking", "flash-prompt2"]
ROTULO = {"pipeline": "pipeline (determinístico)", "flash": "agente base (flash, sem thinking)", "flash-strict": "agente + strict",
          "flash-thinking": "agente + thinking", "flash-prompt2": "agente + prompt v2 (otimista*)"}


def carregar(config):
    runs = []
    for f in sorted(AV.glob(f"resultado_f-{config}-r*.json")):
        runs.append(json.loads(f.read_text(encoding="utf-8")))
    return runs


def pontuar_run(run, gab):
    return {i["id"]: pontuar(i["output"]["entregues"], gab[i["id"]]) for i in run["itens"] if i["id"] in gab}


def media_sd(v):
    return (st.mean(v), st.stdev(v) if len(v) > 1 else 0.0) if v else (float("nan"), 0.0)


def main(md=False):
    gab = carregar_gabarito()
    dados, sem_rotulo = {}, {}
    for c in CONFIGS:
        runs = carregar(c)
        if not runs:
            continue
        pts = [pontuar_run(r, gab) for r in runs]
        dados[c] = {"runs": runs, "pts": pts}
        for r in runs:
            for i in r["itens"]:
                if i["id"] in gab:
                    for e in i["output"]["entregues"][:3]:
                        if e["osm"] not in gab[i["id"]]:
                            sem_rotulo.setdefault((i["id"], e["osm"]), (e["nome"], e["place_id"], c))

    linhas = []
    pipe = dados["pipeline"]["pts"][0]
    for c, d in dados.items():
        p3 = [st.mean(x["p3"] for x in pt.values()) for pt in d["pts"]]
        nd = [st.mean(x["ndcg"] for x in pt.values() if x["ndcg"] is not None) for pt in d["pts"]]
        cob = [st.mean(x["cobertura"] for x in pt.values() if x["cobertura"] is not None) for pt in d["pts"]]
        vazias = sum(1 for pt in d["pts"] for x in pt.values() if x["cobertura"] is None) / len(d["pts"])  # casos sem nenhuma entrega, por run
        lat = [r["run_scores"]["media_latencia_s"] for r in d["runs"]]
        tok = [(r["run_scores"].get("media_tokens_prompt") or 0, r["run_scores"].get("media_tokens_saida") or 0) for r in d["runs"]]
        # por caso: media das repeticoes contra o pipeline (vitoria/empate/derrota com folga de 0,05)
        v = e = dr = 0
        for tid in pipe:
            m = st.mean(pt[tid]["ndcg"] for pt in d["pts"] if pt[tid]["ndcg"] is not None)
            diff = m - pipe[tid]["ndcg"]
            v, e, dr = v + (diff > 0.05), e + (abs(diff) <= 0.05), dr + (diff < -0.05)
        (p3m, p3s), (ndm, nds) = media_sd(p3), media_sd(nd)
        linhas.append({"config": c, "n": len(d["runs"]), "p3": (p3m, p3s), "p3_faixa": (min(p3), max(p3)), "ndcg": (ndm, nds), "ndcg_faixa": (min(nd), max(nd)),
                       "cob": st.mean(cob), "vazias": vazias, "lat": st.mean(lat), "tok": (st.mean(t[0] for t in tok), st.mean(t[1] for t in tok)),
                       "vs_pipeline": (v, e, dr), "fallbacks": sum(r["run_scores"].get("total_fallbacks") or 0 for r in d["runs"])})
    saida = ["| Configuração | Runs | P@3 (média ± dp) | faixa P@3 | nDCG@3 (média ± dp) | faixa nDCG@3 | Cobertura | Latência | Tokens (prompt/saída) | Casos vs pipeline (V/E/D)† | Sem entrega |",
             "|---|---:|---|---|---|---|---:|---:|---|---|---:|"]
    for l in linhas:
        saida.append(f"| {ROTULO[l['config']]} | {l['n']} | {l['p3'][0]:.3f} ± {l['p3'][1]:.3f} | {l['p3_faixa'][0]:.2f}–{l['p3_faixa'][1]:.2f} | "
                     f"{l['ndcg'][0]:.3f} ± {l['ndcg'][1]:.3f} | {l['ndcg_faixa'][0]:.2f}–{l['ndcg_faixa'][1]:.2f} | {l['cob']:.2f} | {l['lat']:.1f} s | "
                     f"{l['tok'][0]:.0f} / {l['tok'][1]:.0f} | " + ("-" if l["config"] == "pipeline" else "{}/{}/{}".format(*l["vs_pipeline"])) + f" | {l['vazias']:.1f} |")
    if md:
        return "\n".join(saida), linhas, sem_rotulo, dados, gab
    print("\n".join(saida))
    print(f"\nlugares entregues (top-3) SEM rotulo no gabarito: {len(sem_rotulo)}")
    for (tid, osm), (nome, pid, c) in sorted(sem_rotulo.items()):
        print(f"  {tid} {nome:34s} {osm:24s} place_id={pid} (visto em {c})")
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true")
    main(ap.parse_args().md)
