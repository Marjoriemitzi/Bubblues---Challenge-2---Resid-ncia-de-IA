#!/usr/bin/env python3
"""Comparacao LLM puro x RAG (4 configuracoes) com tracing/avaliacao no Langfuse.

Configuracoes
  A  llm_puro        : LLM sem recuperacao (conhecimento parametrico).
  B  rag_sem_llm     : embeddings + score hibrido (0.40 sim, 0.25 dist, 0.15 rep, 0.20 compat),
                       abstencao por limiar de similaridade. Nenhuma chamada a LLM.
  C  rag_llm_gerador : B (top-5) -> LLM escolhe ate 3 so entre os candidatos e decide abstencao.
  D  rag_llm_completo: LLM interpreta o pedido (filtros/escopo) -> recuperacao hibrida com
                       compatibilidade derivada dos filtros -> LLM gera resposta ancorada.

Gabarito: docs/avaliacao/pedidos_teste.json (18 pedidos congelados) sobre o catalogo de 25 POIs.
Langfuse e ativado se LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY existirem (LANGFUSE_BASE_URL opcional;
usa o cliente singleton, carregando o .env antes de instanciar).
Estrutura do trace: run_experiment (raiz = pedido) > retrieve-places (retriever) > embed-text (embedding)
e generations por etapa (A_llm_puro, D_interpretador, C_gerador/D_gerador).
"""

import argparse
import difflib
import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import requests
from contextlib import nullcontext

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODELO_EMB = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
PESOS = {"sim": 0.40, "dist": 0.25, "rep": 0.15, "compat": 0.20}
LIMIAR_SIM = 0.35  # abstencao do RAG sem LLM (hiperparametro; ver sensibilidade no relatorio)
TOP_CONTEXTO = 5
ABSTENCAO_ESPERADA = {"TC-17", "TC-18"}

CATALOGO = json.loads((AQUI / "catalogo_pois.json").read_text(encoding="utf8"))
POR_ID = {p["id"]: p for p in CATALOGO}
PEDIDOS = json.loads((RAIZ / "docs/avaliacao/pedidos_teste.json").read_text(encoding="utf8"))
NOMES_OSM = (AQUI / "osm_df_nomes.txt").read_text(encoding="utf8").splitlines()

LANGFUSE = None
MODELO_LLM = "qwen2.5:7b"


# ----------------------------------------------------------------- utilitarios
def norm(txt):
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", txt).split()


def norm_s(txt):
    return " ".join(norm(txt))


OSM_NORM = {norm_s(n) for n in NOMES_OSM if len(norm_s(n)) >= 4}
CAT_NORM = {p["id"]: norm_s(p["name"]) for p in CATALOGO}


def casar_catalogo(nome):
    """Devolve o id do POI do catalogo que corresponde ao nome citado (ou None)."""
    n = norm_s(nome)
    if not n:
        return None
    melhor, escore = None, 0.0
    for pid, cn in CAT_NORM.items():
        r = difflib.SequenceMatcher(None, n, cn).ratio()
        if n in cn or cn in n:
            r = max(r, 0.9)
        if r > escore:
            melhor, escore = pid, r
    return melhor if escore >= 0.8 else None


def existe_no_osm(nome):
    n = norm_s(nome)
    if len(n) < 4:
        return False
    if n in OSM_NORM:
        return True
    return any((n in o or o in n) and min(len(n), len(o)) >= 8 for o in OSM_NORM)


def item_campo(item, campo):
    return item[campo] if isinstance(item, dict) else getattr(item, campo)


def _obs(nome, tipo="span", **campos):
    """Observacao aninhada do Langfuse; no-op quando o tracing esta desligado."""
    if not LANGFUSE:
        return nullcontext()
    return LANGFUSE.start_as_current_observation(name=nome, as_type=tipo, **campos)


# ------------------------------------------------------------------------ LLM
def llm_json(nome, sistema, usuario):
    """Chama o Ollama em modo JSON (temperatura 0, seed fixa); registra uma generation no Langfuse."""
    msgs = [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]
    corpo = {"model": MODELO_LLM, "messages": msgs, "stream": False, "format": "json",
             "options": {"temperature": 0, "seed": 42, "num_ctx": 4096}}

    def chamar():
        r = requests.post(f"{OLLAMA}/api/chat", json=corpo, timeout=600).json()
        return r["message"]["content"], r.get("prompt_eval_count", 0), r.get("eval_count", 0)

    t0 = time.perf_counter()
    with _obs(nome, "generation", model=MODELO_LLM, input=msgs,
              model_parameters={"temperature": 0, "seed": 42},
              metadata={"servidor": "ollama"}) as g:
        try:
            texto, tin, tout = chamar()
        except Exception as erro:  # rede/Ollama fora do ar: o erro precisa aparecer no trace
            if g:
                g.update(level="ERROR", status_message=f"{type(erro).__name__}: {erro}")
            raise
        try:
            dado = json.loads(texto)
        except json.JSONDecodeError:
            dado = {"_json_invalido": True, "_bruto": texto}
        if g:
            g.update(output=texto, usage_details={"input": tin, "output": tout},
                     metadata={"json_valido": str(not dado.get("_json_invalido", False))},
                     **({"level": "WARNING", "status_message": "resposta nao e JSON valido"}
                        if dado.get("_json_invalido") else {}))
    return dado, {"tokens_in": tin, "tokens_out": tout, "t": time.perf_counter() - t0}


# ------------------------------------------------------------------ recuperacao
_modelo = None
_emb_poi = None


def embutir(textos):
    global _modelo
    with _obs("embed-text", "embedding", model=MODELO_EMB, input=textos[:3],
              metadata={"textos": str(len(textos))}) as o:
        if _modelo is None:
            from sentence_transformers import SentenceTransformer
            _modelo = SentenceTransformer(MODELO_EMB)
        vetores = _modelo.encode(textos, normalize_embeddings=True)
        if o:
            o.update(output={"vetores": len(vetores), "dimensoes": int(vetores.shape[-1])})
        return vetores


def texto_poi(p):
    return (f"nome: {p['name']}. categoria: {p['amenity']} / {p['category']}. "
            f"ambiente: {p['vibe']}, ruido {p['noise_level']}. cozinha: {p['cuisine']}. "
            f"indicado para: {', '.join(p['suitable_for'])}. etiquetas: {', '.join(p['tags'])}. "
            f"endereco: {p['address']}")


def recuperar(consulta, filtros=None):
    """Ranking hibrido (observacao `retrieve-places`). `filtros` (config D) alimenta a compatibilidade."""
    with _obs("retrieve-places", "retriever", input={"consulta": consulta, "filtros": filtros},
              metadata={"pesos": json.dumps(PESOS), "catalogo": str(len(CATALOGO))}) as o:
        linhas = _recuperar(consulta, filtros)
        if o:
            o.update(output=[{"id": r["id"], "nome": POR_ID[r["id"]]["name"], "sim": round(r["sim"], 4),
                              "score": round(r["score"], 4)} for r in linhas[:TOP_CONTEXTO]])
        return linhas


def _recuperar(consulta, filtros=None):
    global _emb_poi
    if _emb_poi is None:
        _emb_poi = embutir([texto_poi(p) for p in CATALOGO])
    sims = _emb_poi @ embutir([consulta])[0]
    linhas = []
    for p, s in zip(CATALOGO, sims):
        rep = (0.4 * p["google_rating"] + 0.6 * p["app_rating"]) / 5
        comp, partes = 0.5, []
        if filtros:
            cats = [c for c in filtros.get("categorias", []) if c]
            if cats:
                partes.append(float(p["amenity"] in cats))
            if filtros.get("cadeirante"):
                partes.append(float(p["wheelchair"] == "yes"))
            if partes:
                comp = sum(partes) / len(partes)
            raio = filtros.get("raio_km")
            if raio and p["distance_km"] > raio:
                comp *= 0.5
        total = (PESOS["sim"] * max(0, s) + PESOS["dist"] / (1 + p["distance_km"] / 5)
                 + PESOS["rep"] * rep + PESOS["compat"] * comp)
        linhas.append({"id": p["id"], "sim": float(s), "score": float(total)})
    linhas.sort(key=lambda x: (-x["score"], x["id"]))
    return linhas


def ficha(pid):
    p = POR_ID[pid]
    return (f"[{pid}] {p['name']} | tipo: {p['category']} | ambiente: {p['vibe']}, ruído {p['noise_level']} | "
            f"acessível a cadeirante: {p['wheelchair']} | horário: {p['opening_hours']} | "
            f"distância: {p['distance_km']} km | indicado para: {', '.join(p['suitable_for'])} | "
            f"nota: Google {p['google_rating']}, app {p['app_rating']}")


# ---------------------------------------------------------- 4 configuracoes
SIS_BASE = ("Você é o assistente do Bubbles, que sugere locais públicos seguros em Brasília-DF para "
            "encontros presenciais em pequenos grupos. Só atende pedidos de encontros sociais. ")


def cfg_a(consulta):
    dado, m = llm_json(
        "A_llm_puro",
        SIS_BASE + 'Responda em JSON: {"abstain": bool, "motivo": str, "locais": [{"nome": str}]}. '
        "Se o pedido for fora do escopo ou impossível, use abstain=true e locais vazio. "
        "Caso contrário recomende até 3 estabelecimentos reais de Brasília, pelo nome.",
        consulta)
    nomes = [l.get("nome", "") if isinstance(l, dict) else str(l) for l in dado.get("locais", [])][:3]
    abst = bool(dado.get("abstain")) or not nomes
    recs = [{"nome": n, "id": casar_catalogo(n), "em_osm": existe_no_osm(n)} for n in nomes] if not abst else []
    return {"abstained": abst, "recomendados": recs, "texto": dado.get("motivo", ""), "metricas_llm": [m]}


def cfg_b(consulta):
    rank = recuperar(consulta)
    topo = rank[:3]
    abst = rank[0]["sim"] < LIMIAR_SIM
    recs = [] if abst else [{"nome": POR_ID[r["id"]]["name"], "id": r["id"], "em_osm": True,
                             "score": r["score"], "sim": r["sim"]} for r in topo]
    return {"abstained": abst, "recomendados": recs, "max_sim": rank[0]["sim"],
            "contexto": [r["id"] for r in rank[:TOP_CONTEXTO]], "metricas_llm": []}


def _gerar(consulta, ctx_ids, nome):
    contexto = "\n".join(ficha(i) for i in ctx_ids)
    dado, m = llm_json(
        nome,
        SIS_BASE + "Use APENAS os locais do CONTEXTO; nunca cite outro. Escolha até 3 que atendam o pedido. "
        'Se nenhum atender (restrição impossível, pedido fora do escopo), use abstain=true. '
        'Responda em JSON: {"abstain": bool, "motivo": str, "escolhidos": [{"id": "POI-xx", "justificativa": str}]}.',
        f"PEDIDO: {consulta}\n\nCONTEXTO:\n{contexto}")
    esc = dado.get("escolhidos", []) if isinstance(dado.get("escolhidos"), list) else []
    ids = [e.get("id") for e in esc if isinstance(e, dict)][:3]
    abst = bool(dado.get("abstain")) or not ids
    recs = [] if abst else [{"nome": POR_ID[i]["name"] if i in POR_ID else str(i), "id": i if i in POR_ID else None,
                             "fora_do_contexto": i not in ctx_ids, "em_osm": i in POR_ID} for i in ids]
    return abst, recs, dado.get("motivo", ""), m


def cfg_c(consulta):
    rank = recuperar(consulta)
    ctx = [r["id"] for r in rank[:TOP_CONTEXTO]]
    abst, recs, motivo, m = _gerar(consulta, ctx, "C_gerador")
    return {"abstained": abst, "recomendados": recs, "texto": motivo, "contexto": ctx, "metricas_llm": [m]}


CATS = sorted({p["amenity"] for p in CATALOGO})


def cfg_d(consulta):
    req, m1 = llm_json(
        "D_interpretador",
        SIS_BASE + "Interprete o pedido. Responda em JSON: "
        '{"fora_do_escopo": bool, "impossivel": bool, "motivo": str, "categorias": [str], '
        '"cadeirante": bool, "raio_km": number|null, "consulta_reescrita": str}. '
        f"'categorias' deve usar só estes valores: {CATS}. 'impossivel' = combinação de exigências "
        "incompatível entre si ou impossível de existir. 'consulta_reescrita' = o pedido resumido em uma frase "
        "descritiva do local ideal.",
        consulta)
    if req.get("fora_do_escopo") or req.get("impossivel"):
        return {"abstained": True, "recomendados": [], "texto": req.get("motivo", ""), "filtros": req,
                "contexto": [], "metricas_llm": [m1]}
    filtros = {"categorias": [c for c in req.get("categorias", []) if c in CATS],
               "cadeirante": bool(req.get("cadeirante")),
               "raio_km": req.get("raio_km") if isinstance(req.get("raio_km"), (int, float)) else None}
    rank = recuperar(f"{consulta}. {req.get('consulta_reescrita', '')}", filtros)
    ctx = [r["id"] for r in rank[:TOP_CONTEXTO]]
    abst, recs, motivo, m2 = _gerar(consulta, ctx, "D_gerador")
    return {"abstained": abst, "recomendados": recs, "texto": motivo, "filtros": filtros,
            "contexto": ctx, "metricas_llm": [m1, m2]}


CONFIGS = {"A_llm_puro": cfg_a, "B_rag_sem_llm": cfg_b, "C_rag_llm_gerador": cfg_c, "D_rag_llm_completo": cfg_d}


def fazer_task(fn):
    def task(*, item, **_):
        t0 = time.perf_counter()
        saida = fn(item_campo(item, "input")["pedido"])
        saida["latencia_s"] = time.perf_counter() - t0
        saida["tokens"] = sum(m["tokens_in"] + m["tokens_out"] for m in saida["metricas_llm"])
        return saida
    return task


# ------------------------------------------------------------------ avaliadores
def _ev(nome, valor, comentario=None):
    return {"name": nome, "value": valor, "comment": comentario}


def avaliar(*, input, output, expected_output, metadata=None, **_):
    esperados = expected_output["relevantes"]
    ids = [r["id"] for r in output["recomendados"] if r["id"]]
    tc = input["id"]
    saida = []
    if tc in ABSTENCAO_ESPERADA:
        saida.append(_ev("abstencao_correta", float(output["abstained"]),
                         "esperado abster-se (impossivel/fora do escopo)"))
    else:
        saida.append(_ev("precision_at_3", sum(i in esperados for i in ids[:3]) / 3))
        dcg = sum(1 / math.log2(k + 2) for k, i in enumerate(ids[:3]) if i in esperados)
        idcg = sum(1 / math.log2(k + 2) for k in range(min(3, len(esperados))))
        saida.append(_ev("ndcg_at_3", dcg / idcg if idcg else 0.0))
        saida.append(_ev("falsa_abstencao", float(output["abstained"])))
    recs = output["recomendados"]
    if recs:
        saida.append(_ev("existe_no_osm", sum(r["em_osm"] for r in recs) / len(recs),
                         "fracao dos locais citados que existem no OSM-DF"))
        saida.append(_ev("no_catalogo", sum(bool(r["id"]) for r in recs) / len(recs),
                         "fracao dos locais citados presentes no catalogo verificado"))
        saida.append(_ev("ancorado", float(not any(r.get("fora_do_contexto") for r in recs)
                                           and all(r["id"] for r in recs)),
                         "todos os locais citados vem do contexto recuperado/catalogo"))
    saida.append(_ev("latencia_s", output["latencia_s"]))
    saida.append(_ev("tokens", float(output["tokens"])))
    return saida


def agregar(*, item_results, **_):
    """Run-level: media de cada metrica sobre os itens em que ela existe."""
    por = {}
    for r in item_results:
        for e in r.evaluations:
            if e.value is not None:
                por.setdefault(e.name, []).append(float(e.value))
    return [_ev(f"media_{k}", float(np.mean(v)), f"n={len(v)}") for k, v in por.items()]


# ----------------------------------------------------------------------- main
def main():
    global LANGFUSE, MODELO_LLM
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=MODELO_LLM)
    ap.add_argument("--configs", nargs="*", default=list(CONFIGS))
    ap.add_argument("--dataset", default="bubbles-pedidos-teste-v1")
    ap.add_argument("--saida", default=str(RAIZ / "docs/relatorio/rag_comparison/resultados.json"))
    args = ap.parse_args()
    MODELO_LLM = args.modelo

    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        from langfuse import Langfuse
        LANGFUSE = Langfuse()
        print("Langfuse autenticado:", LANGFUSE.auth_check())

    dados = [{"id": p["id"], "input": {"id": p["id"], "pedido": p["query"], "persona": p["persona"]},
              "expected_output": {"relevantes": p["locais_esperados_relevantes"], "tipo": p["tipo_pedido"]},
              "metadata": {"tipo_pedido": p["tipo_pedido"]}} for p in PEDIDOS]
    itens = dados
    if LANGFUSE:
        LANGFUSE.create_dataset(name=args.dataset, description="18 pedidos congelados do Bubbles (pedidos_teste.json)")
        for d in dados:
            LANGFUSE.create_dataset_item(dataset_name=args.dataset, id=f"{args.dataset}-{d['id']}",
                                         input=d["input"], expected_output=d["expected_output"],
                                         metadata=d["metadata"])
        itens = LANGFUSE.get_dataset(args.dataset).items

    resumo, detalhes = {}, {}
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    for nome in args.configs:
        task = fazer_task(CONFIGS[nome])
        print(f"== {nome}")
        meta = {"llm": "nenhum" if nome.startswith("B") else MODELO_LLM, "embeddings": MODELO_EMB,
                "limiar_sim": str(LIMIAR_SIM), "top_contexto": str(TOP_CONTEXTO)}
        if LANGFUSE:
            res = LANGFUSE.run_experiment(name=f"rag-vs-llm/{nome}", run_name=f"{nome}-{carimbo}",
                                          description=__doc__.split("\n")[0], data=itens, task=task,
                                          evaluators=[avaliar], run_evaluators=[agregar],
                                          max_concurrency=1, metadata=meta)
            linhas = [(item_campo(r.item, "input")["id"], r.output, r.evaluations) for r in res.item_results]
            medias = {e.name: e.value for e in res.run_evaluations}
            print("   ", res.dataset_run_url if hasattr(res, "dataset_run_url") else "")
        else:
            linhas, acum = [], {}
            for d in dados:
                o = task(item=d)
                ev = avaliar(input=d["input"], output=o, expected_output=d["expected_output"])
                linhas.append((d["id"], o, [SimpleNamespace(**e) for e in ev]))
                for e in ev:
                    acum.setdefault(f"media_{e['name']}", []).append(float(e["value"]))
            medias = {k: float(np.mean(v)) for k, v in acum.items()}
        resumo[nome] = {k: round(v, 4) for k, v in medias.items()}
        detalhes[nome] = [{"id": i, "saida": o,
                           "metricas": {e.name: e.value for e in ev}} for i, o, ev in linhas]
        print("   ", resumo[nome])

    Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.saida).write_text(json.dumps(
        {"gerado_em": carimbo, "llm": MODELO_LLM, "embeddings": MODELO_EMB, "limiar_sim": LIMIAR_SIM,
         "langfuse": bool(LANGFUSE), "resumo": resumo, "detalhes": detalhes},
        ensure_ascii=False, indent=1, default=str), encoding="utf8")
    if LANGFUSE:
        LANGFUSE.flush()
    print("Salvo em", args.saida)


if __name__ == "__main__":
    main()
