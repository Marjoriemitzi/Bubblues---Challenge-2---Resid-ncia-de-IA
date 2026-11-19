#!/usr/bin/env python3
"""Roda o NLUAgent (DeepSeek) nos pedidos de teste e verifica cada saida.

Gera, em docs/avaliacao/:
  structured_requests_nlu.json   saida bruta do NLU + achados da verificacao (por pedido)
  verificacao_nlu.md             relatorio legivel
Usa DEEPSEEK_API_KEY do .env e as categorias reais de places (PostgreSQL).
"""

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from orchestrator.llm_client import LLMClient  # noqa: E402
from orchestrator.nlu_agent import NLUAgent  # noqa: E402
from orchestrator.retrieval_common import _pipeline  # noqa: E402
from orchestrator.verificacao_nlu import ACAO_POR_TIPO, acao_obtida, verificar  # noqa: E402

PEDIDOS = RAIZ / "docs" / "avaliacao" / "pedidos_teste.json"
SAIDA_JSON = RAIZ / "docs" / "avaliacao" / "structured_requests_nlu.json"
SAIDA_MD = RAIZ / "docs" / "avaliacao" / "verificacao_nlu.md"


def main():
    pedidos = json.loads(PEDIDOS.read_text(encoding="utf-8"))
    busca = _pipeline()[0]
    with busca.conectar() as con:
        categorias = [r[0] for r in con.execute("SELECT DISTINCT categoria FROM places WHERE categoria IS NOT NULL")]
    llm = LLMClient()
    nlu = NLUAgent(llm, categorias)
    print(f"modelo={llm.model} categorias={len(categorias)} pedidos={len(pedidos)}", flush=True)

    resultados = []
    for p in pedidos:
        t0 = time.time()
        try:
            out = nlu({"request_id": f"eval-{p['id']}", "raw_query": p["query"]})
            req, nota, erro = out["structured_request"], out["note"], None
            achados = verificar(p, req, set(categorias))
        except Exception as exc:  # noqa: BLE001
            req, nota, erro, achados = None, "", f"{type(exc).__name__}: {exc}", []
        resultados.append({"id": p["id"], "tipo_pedido": p["tipo_pedido"], "query": p["query"], "erro": erro, "nota": nota,
                           "structured_request_nlu": req,
                           "achados": [a.__dict__ for a in achados], "segundos": round(time.time() - t0, 1)})
        n_err = sum(a.nivel == "ERRO" for a in achados)
        n_rev = sum(a.nivel == "REVISAR" for a in achados)
        print(f"{p['id']} {p['tipo_pedido'][:9]:9s} {'FALHOU: ' + erro if erro else f'ERRO={n_err} REVISAR={n_rev}'} ({resultados[-1]['segundos']}s, chamadas LLM acumuladas={llm.chamadas})", flush=True)

    SAIDA_JSON.write_text(json.dumps({"modelo": llm.model, "chamadas_llm": llm.chamadas, "itens": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")

    linhas = [f"# Verificação das saídas do NLU (DeepSeek `{llm.model}`)", "",
              "Gerado por `scripts/avaliacao/gerar_requests_nlu.py`. ERRO = contradiz o pedido; REVISAR = plausível, mas um humano deve olhar.", ""]
    for r in resultados:
        linhas += [f"## {r['id']} ({r['tipo_pedido']}, esperado: {ACAO_POR_TIPO[r['tipo_pedido']]})", f"> {r['query']}", ""]
        if r["erro"]:
            linhas += [f"**FALHOU:** `{r['erro']}`", ""]
            continue
        q = r["structured_request_nlu"]
        linhas += [f"- ação obtida: **{acao_obtida(q)}** | categorias: `{q['target_amenities']}` | região: `{q['spatial_constraints']['target_region']}` "
                   f"| ruído: `{q['noise_tolerance']}` | acessib.: `{q['accessibility_requirements']}`",
                   f"- atividade: {q['activity']} | vibe: {q['vibe']} | foco: `{q['search_vector_focus']}` | horário: `{q['temporal_constraints']}`"]
        if q.get("clarification_needed"):
            linhas.append(f"- pergunta: {q['clarification_needed']}")
        for a in r["achados"]:
            linhas.append(f"- **{a['nivel']}** `{a['campo']}`: {a['detalhe']}")
        if not r["achados"]:
            linhas.append("- sem achados")
        linhas.append("")
    SAIDA_MD.write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nescrito: {SAIDA_JSON.relative_to(RAIZ)} e {SAIDA_MD.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
