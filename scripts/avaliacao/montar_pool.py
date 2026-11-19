#!/usr/bin/env python3
"""Monta o pool de candidatos reais (OSM) a rotular, a partir dos structured_requests finais.

Para cada pedido a recomendar/clarificar roda o Retrieval real (modelo de embedding real,
filtros obrigatorios) e junta o top-N. Tambem inclui os mesmos candidatos SEM o filtro de
acessibilidade/ruido ("contraste"), para o anotador ver o que os filtros cortam.
Saida: docs/avaliacao/pool_candidatos.json
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from orchestrator.contracts import StructuredRequest  # noqa: E402
from orchestrator.retrieval_agent import texto_do_embedding  # noqa: E402
from orchestrator.retrieval_tools import ContextoBusca, RetrievalTools  # noqa: E402

FINAL = RAIZ / "docs" / "avaliacao" / "structured_requests_final.json"
SAIDA = RAIZ / "docs" / "avaliacao" / "pool_candidatos.json"
TOP = 8
CONTRASTE = 5


def _busca(tools, regioes, req, k):
    cands = tools.executar("resolver_regiao", {"nome": req.spatial_constraints.target_region})["regioes"] if req.spatial_constraints.target_region else []
    lat, lon = (cands[0]["latitude"], cands[0]["longitude"]) if cands else (-15.7939, -47.8828)
    return tools.executar("buscar_lugares", {
        "latitude": lat, "longitude": lon, "raio_km": req.spatial_constraints.max_radius_km,
        "categorias": req.target_amenities, "texto_consulta": texto_do_embedding(req)[:290], "k": k,
    }), (lat, lon, cands[0]["nome"] if cands else None)


def main():
    itens = json.loads(FINAL.read_text(encoding="utf-8"))["itens"]
    saida = []
    for it in itens:
        req = StructuredRequest.model_validate(it["structured_request"])
        if not req.intent_valid:
            saida.append({"id": it["id"], "acao_esperada": it["acao_esperada"], "candidatos": []})
            continue
        ctx = ContextoBusca.de_pedido(req)
        tools = RetrievalTools(ctx, f"pool-{it['id']}")
        principal, local = _busca(tools, None, req, TOP)
        cand = {i["place_id"]: {**i, "origem": "pipeline"} for i in principal.get("itens", [])}
        # contraste: mesma busca sem exigir acessibilidade/ruido
        livre = ContextoBusca.de_pedido(req)
        livre.etiquetas, livre.tolerancia_sensorial = {}, "indiferente"
        extra, _ = _busca(RetrievalTools(livre, f"pool-{it['id']}-livre"), None, req, TOP + CONTRASTE)
        for i in extra.get("itens", []):
            if i["place_id"] not in cand and len([c for c in cand.values() if c["origem"] == "contraste"]) < CONTRASTE:
                cand[i["place_id"]] = {**i, "origem": "contraste"}
        saida.append({"id": it["id"], "acao_esperada": it["acao_esperada"], "local_resolvido": local,
                      "raio_km": req.spatial_constraints.max_radius_km, "ajustes": principal.get("ajustes"),
                      "candidatos": list(cand.values())})
        print(f"{it['id']}: {len(cand)} candidatos (pipeline={sum(c['origem']=='pipeline' for c in cand.values())})", flush=True)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print("escrito", SAIDA.relative_to(RAIZ))


if __name__ == "__main__":
    main()
