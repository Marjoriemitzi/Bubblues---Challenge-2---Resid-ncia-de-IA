#!/usr/bin/env python3
"""Cria/atualiza no Langfuse o dataset `bubbles-retrieval-osm-v1` (18 casos), de forma idempotente.

Fontes (docs/avaliacao/): pedidos_teste.json, structured_requests_final.json, rotulos_osm_v1.json.
Credenciais: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL do .env da raiz.
Cada item tem id fixo (`bubbles-osm-v1-TC-XX`), entao rodar de novo atualiza em vez de duplicar.

  python scripts/avaliacao/criar_dataset_langfuse.py --dry-run   # so mostra o que enviaria
  python scripts/avaliacao/criar_dataset_langfuse.py             # envia
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import find_dotenv, load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
AV = RAIZ / "docs" / "avaliacao"
NOME = "bubbles-retrieval-osm-v1"
DESCRICAO = (
    "Pedidos de teste do Bubbles com structured_request (NLU DeepSeek revisado) e relevancia graduada 0/1/2 "
    "sobre lugares reais do OSM do DF. Anotador unico (IA), nao cego: use como baseline, nao como verdade."
)


def construir_itens():
    pedidos = {p["id"]: p for p in json.loads((AV / "pedidos_teste.json").read_text(encoding="utf-8"))}
    final = {i["id"]: i for i in json.loads((AV / "structured_requests_final.json").read_text(encoding="utf-8"))["itens"]}
    rot = json.loads((AV / "rotulos_osm_v1.json").read_text(encoding="utf-8"))
    baseline = {m["id"]: m for m in rot["baseline_pipeline"]}
    itens = []
    for tid, f in final.items():
        caso = rot["casos"][tid]
        labels = caso["labels"]
        itens.append({
            "id": f"bubbles-osm-v1-{tid}",
            "input": {"id": tid, "pedido": f["query"], "structured_request": f["structured_request"]},
            "expectedOutput": {
                "acao": caso["acao_esperada"],
                "relevancia": {l["osm"]: l["grau"] for l in labels},  # chave estavel: osm tipo/id (place_id muda a cada curadoria)
                "max_p3": baseline[tid]["max_p3"] if tid in baseline else None,
            },
            "metadata": {
                "gabarito": "osm_v1",
                "tipo_pedido": pedidos[tid]["tipo_pedido"],
                "persona": pedidos[tid]["persona"],
                "nucleo": caso["nucleo"],
                "nlu": {"modelo": "deepseek-chat", "correcoes": f["correcoes"], "nota": f["nota"]},
                "anotador": "Claude (unico, nao cego)",
                "n_rotulos": len(labels),
                "n_grau2": sum(l["grau"] == 2 for l in labels),
                "rotulos_detalhe": [
                    {k: l[k] for k in ("osm", "place_id", "nome", "categoria", "origem", "grau", "evidencia", "confianca", "motivo")}
                    for l in labels
                ],
                "baseline_pipeline": baseline.get(tid),
            },
        })
    return itens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    itens = construir_itens()
    if args.dry_run:
        print(f"dataset '{NOME}': {len(itens)} itens")
        print(json.dumps(itens[0], ensure_ascii=False, indent=1)[:2500])
        return

    load_dotenv(find_dotenv(usecwd=True))
    base, auth = os.environ["LANGFUSE_BASE_URL"].rstrip("/"), (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
    api = lambda m, p, **kw: requests.request(m, f"{base}/api/public/{p}", auth=auth, timeout=60, **kw)

    r = api("POST", "datasets", json={"name": NOME, "description": DESCRICAO, "metadata": {
        "gabarito": "osm_v1", "fonte_pedidos": "docs/avaliacao/pedidos_teste.json", "escala": "0/1/2",
        "limitacoes": "anotador unico (IA), nao cego; web cobre pouco o comercio de Brasilia; 1 inclui 'nao confirmado'"}})
    r.raise_for_status()
    print("dataset:", r.json().get("name"), r.json().get("id"))
    for it in itens:
        resp = api("POST", "dataset-items", json={"datasetName": NOME, **it})
        if resp.status_code >= 300:
            sys.exit(f"falhou {it['id']}: {resp.status_code} {resp.text[:300]}")
        print("  ok", it["id"])
    proj = api("GET", "projects").json()["data"][0]["id"]
    print(f"\nlink: {base}/project/{proj}/datasets/{r.json()['id']}")


if __name__ == "__main__":
    main()
