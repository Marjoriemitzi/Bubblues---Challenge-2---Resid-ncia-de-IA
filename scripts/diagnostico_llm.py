#!/usr/bin/env python3
"""Diagnostico do LLM (DeepSeek) com tool calling REAL sobre as ferramentas do Retrieval.

Para cada configuracao (modelo, thinking, strict) roda um loop curto: o modelo resolve a regiao, busca
(PostgreSQL + embedding real) e valida; mostra as chamadas de ferramenta, tokens, latencia e se algum filtro
obrigatorio foi tentado/violado. Tambem prova que, no modo thinking, omitir `reasoning_content` da 400.

  python scripts/diagnostico_llm.py                 # matriz padrao
  python scripts/diagnostico_llm.py --so flash-sem-thinking --max-passos 6
  python scripts/diagnostico_llm.py --provar-400    # inclui a prova do reasoning_content
Grava linhas em evidencias_busca (cada buscar_lugares registra a consulta).
"""

import argparse
import copy
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402


def carregar_envs():
    for pasta in [Path.cwd(), RAIZ, *RAIZ.parents]:
        if (pasta / ".env").is_file():
            load_dotenv(pasta / ".env")


carregar_envs()

from orchestrator.contracts import StructuredRequest  # noqa: E402
from orchestrator.llm_client import (  # noqa: E402
    LLMClient,
    LLMError,
    extrair_chamadas,
    mensagem_de_ferramenta,
    mensagem_para_dict,
)
from orchestrator.retrieval_tools import ContextoBusca, RetrievalTools, aquecer_modelo  # noqa: E402
from orchestrator.stubs import _request  # noqa: E402
from orchestrator.validation_tool import EvidenceValidator  # noqa: E402

CONFIGS = {
    "chat-legado": dict(model="deepseek-chat", reasoning_effort=None, strict=False),
    "flash-sem-thinking": dict(model="deepseek-flash", reasoning_effort="none", strict=False),
    "flash-strict": dict(model="deepseek-flash", reasoning_effort="none", strict=True),
    "flash-thinking": dict(model="deepseek-flash", reasoning_effort="high", strict=False),
    "v4pro-sem-thinking": dict(model="deepseek-v4-pro", reasoning_effort="none", strict=False),
}
SISTEMA = (
    "Voce e o Retrieval do Bubbles: acha lugares publicos do DF para um pedido ja estruturado. Use as ferramentas: "
    "primeiro resolva a regiao (se houver), depois busque lugares com buscar_lugares usando o raio e as categorias do "
    "pedido e valide a busca com validar_candidatos. Termine com UMA frase em texto dizendo o busca_id escolhido e "
    "quantos lugares foram aprovados. Nunca invente lugares."
)


def pedido():
    req = StructuredRequest.model_validate(_request(
        "diag-llm", target_amenities=["cafe"], activity="ler e conversar", vibe="calmo",
        spatial_constraints={"target_region": "Asa Sul", "max_radius_km": 5.0},
        accessibility_requirements={"wheelchair_required": True}, search_vector_focus=["silencioso", "leitura"],
    ))
    return req


def rodar(nome, cfg, max_passos, provar_400=False):
    req = pedido()
    llm = LLMClient(**cfg)
    tools = RetrievalTools(
        ContextoBusca.de_pedido(req), req.request_id, req=req, validator=EvidenceValidator(),  # sem store: consultivo
    )
    resumo = req.model_dump(exclude={"raw_query"})
    msgs = [{"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Pedido estruturado: " + json.dumps(resumo, ensure_ascii=False)}]
    print(f"\n=== {nome}: modelo={cfg['model']} thinking={cfg['reasoning_effort']} strict={cfg['strict']}", flush=True)
    t0 = time.time()
    chamadas_feitas, erros_de_tool, final, achou_reasoning = [], 0, None, False
    for passo in range(1, max_passos + 1):
        t1 = time.time()
        msg = llm.chat(msgs, tools=tools.schemas(), tool_choice="auto", max_tokens=1500)
        achou_reasoning = achou_reasoning or bool(getattr(msg, "reasoning_content", None))
        pedidas = extrair_chamadas(msg)
        print(f"  passo {passo} ({time.time()-t1:.1f}s): {[c.nome for c in pedidas] or 'texto final'}", flush=True)
        msgs.append(mensagem_para_dict(msg))
        if not pedidas:
            final = msg.content
            break
        for c in pedidas:
            res = tools.executar(c.nome, c.argumentos)
            erros_de_tool += "erro" in res
            chamadas_feitas.append((c.nome, c.argumentos[:110], "ERRO: " + res["erro"][:90] if "erro" in res else "ok"))
            msgs.append(mensagem_de_ferramenta(c.id, res))
    seg = time.time() - t0
    for nome_t, args, r in chamadas_feitas:
        print(f"    - {nome_t}({args}) -> {r}")
    print(f"  final: {(final or '(sem texto final)')[:200]}")
    print(f"  tempo={seg:.1f}s  uso={llm.uso.como_dict()}  erros_de_tool={erros_de_tool}  reasoning_content_recebido={achou_reasoning}")
    print(f"  buscas no RunLog={tools.runlog.total}  filtros obrigatorios no contexto={tools.contexto.etiquetas}/{tools.contexto.tolerancia_sensorial}")

    if provar_400 and achou_reasoning:
        quebrado = copy.deepcopy(msgs)
        for m in quebrado:
            m.pop("reasoning_content", None)
        try:
            llm.chat(quebrado, tools=tools.schemas(), max_tokens=200)
            print("  PROVA 400: a API NAO recusou o historico sem reasoning_content (comportamento diferente do documentado)")
        except LLMError as e:
            print(f"  PROVA 400: sem reasoning_content a API recusou, como documentado -> {e}")
    return {"nome": nome, "ok": final is not None, "tempo": seg, "uso": llm.uso.como_dict(), "erros_de_tool": erros_de_tool,
            "chamadas": len(chamadas_feitas), "raciocinio": achou_reasoning}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", help="nomes separados por virgula: " + ", ".join(CONFIGS))
    ap.add_argument("--max-passos", type=int, default=7)
    ap.add_argument("--provar-400", action="store_true")
    args = ap.parse_args()
    nomes = [n.strip() for n in args.so.split(",")] if args.so else list(CONFIGS)
    print("modelos visiveis:", LLMClient().listar_modelos())
    aquecer_modelo()
    print("modelo de embedding carregado", flush=True)
    resultados = []
    for n in nomes:
        try:
            resultados.append(rodar(n, CONFIGS[n], args.max_passos, args.provar_400))
        except LLMError as e:
            print(f"  FALHOU: {e}")
            resultados.append({"nome": n, "ok": False, "erro": str(e)})
    print("\n=== RESUMO")
    for r in resultados:
        if r.get("ok"):
            u = r["uso"]
            print(f"  {r['nome']:20s} ok  {r['tempo']:5.1f}s  chamadas_tool={r['chamadas']}  erros_tool={r['erros_de_tool']}  tokens(p/c/raz)={u['prompt_tokens']}/{u['completion_tokens']}/{u['reasoning_tokens']}")
        else:
            print(f"  {r['nome']:20s} FALHOU  {r.get('erro', 'sem texto final')}")


if __name__ == "__main__":
    main()
