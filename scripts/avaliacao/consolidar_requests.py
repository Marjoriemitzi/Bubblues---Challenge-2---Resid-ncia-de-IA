#!/usr/bin/env python3
"""Fecha os structured_requests de avaliacao: saida do NLU + correcoes objetivas documentadas.

Unica correcao automatica: max_radius_km vem de `restricoes.raio_max_km` do dataset (metadado de
teste que nao aparece no texto, logo o NLU nao tem como saber). Todo o resto e a saida do NLU.
Notas manuais por caso (divergencias, riscos) ficam em NOTAS abaixo.
Saida: docs/avaliacao/structured_requests_final.json
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from orchestrator.contracts import StructuredRequest  # noqa: E402
from orchestrator.verificacao_nlu import ACAO_POR_TIPO, verificar  # noqa: E402

AV = RAIZ / "docs" / "avaliacao"
NOTAS = {
    "TC-01": "elder_friendly=true e inferencia de 'minha faixa etaria' (persona idosa); aceita.",
    "TC-04": "Dataset marca acessibilidade=yes por 'pistas planas', mas o texto nao pede cadeira de rodas/rampa: NLU manteve wheelchair_required=false (divergencia do dataset, nao erro do NLU). vibe 'tranquilo' e leve inferencia (so afeta o embedding).",
    "TC-05": "vibe 'tranquilo' e leve inferencia (so afeta o embedding).",
    "TC-06": "Categoria unica food_court (8 lugares no DF): recall baixo esperado; 'feirinha ao ar livre' poderia incluir park.",
    "TC-14": "Dataset marca acessibilidade=yes, mas o texto nao fala de acessibilidade: wheelchair_required=false mantido. vibe 'tranquilo' e leve inferencia.",
    "TC-15": "'perto da universidade' nao e regiao: target_region=null (busca no centro de Brasilia); 'universidade' foi para o foco semantico.",
    "TC-16": "Ambiguo: acao esperada clarificar; as categorias listadas sao so palpite do NLU.",
}


def main():
    pedidos = {p["id"]: p for p in json.loads((AV / "pedidos_teste.json").read_text(encoding="utf-8"))}
    nlu = json.loads((AV / "structured_requests_nlu.json").read_text(encoding="utf-8"))
    base = StructuredRequest  # valida o formato final
    categorias = set()
    import re
    itens = []
    for it in nlu["itens"]:
        p = pedidos[it["id"]]
        orig = it["structured_request_nlu"]
        final = json.loads(json.dumps(orig))
        correcoes = []
        raio = (p.get("restricoes") or {}).get("raio_max_km")
        if raio and final["intent_valid"]:
            correcoes.append(f"max_radius_km {final['spatial_constraints']['max_radius_km']} -> {raio} (metadado do dataset, nao esta no texto)")
            final["spatial_constraints"]["max_radius_km"] = float(raio)
        base.model_validate(final)
        itens.append({"id": it["id"], "tipo_pedido": it["tipo_pedido"], "acao_esperada": ACAO_POR_TIPO[it["tipo_pedido"]],
                      "query": it["query"], "structured_request": final, "nlu_original": orig,
                      "correcoes": correcoes, "nota": NOTAS.get(it["id"])})
    (AV / "structured_requests_final.json").write_text(
        json.dumps({"origem": f"NLUAgent ({nlu['modelo']}) + correcoes objetivas", "itens": itens}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(itens)} casos; {sum(bool(i['correcoes']) for i in itens)} com correcao de raio")


if __name__ == "__main__":
    main()
