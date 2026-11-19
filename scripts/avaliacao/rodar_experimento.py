#!/usr/bin/env python3
"""Experimento de baseline: roda o grafo REAL (Retrieval determinístico + Validation) sobre o dataset.

Dataset: `bubbles-retrieval-osm-v1` (Langfuse). Entrada de cada item: o structured_request já revisado
(o NLU é avaliado à parte). Saída = o que o grafo ENTREGA (evidence_records aprovados pelo validador).

Avaliadores (todos em código, sem LLM):
  acao_correta, violacao_restricao_entregue, entrega_fora_do_raio, evidencia_completa,
  p_at_3, ndcg_at_3, cobertura_rotulos, reconsultas, aprovado_na_1a_rodada, latencia_s, erro_de_agente.
Rótulos sem id do OSM no gabarito contam como NAO ROTULADOS (grau 0 no P@3/nDCG: limite inferior) e a
`cobertura_rotulos` mostra quanto do que foi entregue o anotador chegou a ver.

  python scripts/avaliacao/rodar_experimento.py [--nome retrieval-agente-llm] [--so TC-01,TC-07]
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402


def carregar_envs():
    """Carrega TODOS os .env do cwd e dos pais (o primeiro valor definido vence).
    find_dotenv() para no primeiro .env; em data-pipeline/ ele so tem as credenciais do banco."""
    for pasta in [Path.cwd(), RAIZ, *RAIZ.parents]:
        if (pasta / ".env").is_file():
            load_dotenv(pasta / ".env")


carregar_envs()
os.environ.setdefault("LANGFUSE_HOST", os.environ.get("LANGFUSE_BASE_URL", ""))

from langfuse import Evaluation, get_client  # noqa: E402

from orchestrator.evidence_store import MemoryEvidenceStore  # noqa: E402
from orchestrator.graph import build_graph, run  # noqa: E402
from orchestrator.retrieval_agent import RetrievalAgent  # noqa: E402
from orchestrator.retrieval_pipeline import RetrievalPipeline  # noqa: E402
from orchestrator.retrieval_tools import aquecer_modelo  # noqa: E402
from orchestrator.stubs import stub_communication  # noqa: E402
from orchestrator.validation_tool import EvidenceValidator  # noqa: E402

_AUTO_FALLBACK = __import__("orchestrator.retrieval_agent", fromlist=["_AUTO"])._AUTO
DATASET = "bubbles-retrieval-osm-v1"
AV = RAIZ / "docs" / "avaliacao"
RETRIEVAL = None  # definido em main(): pipeline determinístico ou agente LLM (uma instancia; o modelo carrega uma vez)


# --------------------------------------------------------------------------- tarefa
def tarefa(*, item, **kwargs):
    sr = item.input["structured_request"]
    grafo = build_graph(
        nlu=lambda state: {"structured_request": sr, "note": "structured_request do dataset"},
        retrieval=RETRIEVAL,
        communication=stub_communication,
    )
    t0 = time.time()
    estado = run(grafo, "(texto livre nao usado: NLU vem do dataset)", sr["request_id"])
    seg = round(time.time() - t0, 2)

    req, resp, fb = estado.get("structured_request"), estado.get("search_response"), estado.get("validation_feedback")
    itens = {i.place_id: i for i in resp.items} if resp else {}
    entregues = []
    for e in estado.get("evidence_records") or []:
        i = itens.get(e.place_id)
        entregues.append({
            "osm": f"{e.osm_reference.osm_type}/{e.osm_reference.osm_id}", "place_id": e.place_id, "nome": e.place_name,
            "score": e.total_score, "distancia_km": i.distance_km if i else None,
            "wheelchair": (i.osm_tags.get("wheelchair") if i else None), "osm_link": e.osm_reference.osm_link,
            "integridade": e.integrity_test.passed,
        })
    if req and req.clarification_needed:
        acao = "clarificar"
    elif req and not req.intent_valid:
        acao = "abster"
    else:
        acao = "recomendar" if entregues else "abster"
    return {
        "acao": acao, "entregues": entregues, "status_busca": resp.status if resp else None,
        "n_candidatos": resp.results_count if resp else 0, "retry_count": estado.get("retry_count", 0),
        "validacao_aprovada": fb.approved if fb else None, "erro": estado.get("error"),
        "trilha": [t.agent for t in estado["agent_trace"]], "segundos": seg,
        "nota_retrieval": next((t.note for t in estado["agent_trace"] if t.agent == "retrieval"), ""),
    }


# --------------------------------------------------------------------------- avaliadores (item)
def _recomendar(expected):
    return (expected or {}).get("acao") == "recomendar"


def ev_acao_correta(*, output, expected_output, **kw):
    ok = output["acao"] == expected_output["acao"]
    return Evaluation(name="acao_correta", value=1.0 if ok else 0.0, comment=f"esperado={expected_output['acao']} obtido={output['acao']}")


def ev_violacao(*, input, output, **kw):
    req = input["structured_request"]
    if not req["accessibility_requirements"]["wheelchair_required"]:
        return []
    ruins = [e["nome"] for e in output["entregues"] if e["wheelchair"] != "yes"]
    return Evaluation(name="violacao_restricao_entregue", value=float(len(ruins)), comment=f"wheelchair!=yes: {ruins}" if ruins else "nenhuma")


def ev_fora_raio(*, input, output, **kw):
    raio = input["structured_request"]["spatial_constraints"]["max_radius_km"]
    fora = [f"{e['nome']} ({e['distancia_km']} km)" for e in output["entregues"] if e["distancia_km"] is not None and e["distancia_km"] > raio]
    return Evaluation(name="entrega_fora_do_raio", value=float(len(fora)), comment=f"raio {raio} km; fora: {fora}" if fora else f"raio {raio} km; ok")


def ev_evidencia(*, output, expected_output, **kw):
    if not _recomendar(expected_output) or not output["entregues"]:
        return []
    ok = all(e["osm_link"].startswith("https://www.openstreetmap.org/") and e["integridade"] for e in output["entregues"])
    return Evaluation(name="evidencia_completa", value=1.0 if ok else 0.0)


def _graus(output, expected_output):
    rel = expected_output.get("relevancia") or {}
    return [rel.get(e["osm"]) for e in output["entregues"][:3]]  # None = nao rotulado


def ev_p3(*, output, expected_output, **kw):
    if not _recomendar(expected_output):
        return []
    g = _graus(output, expected_output)
    return Evaluation(name="p_at_3", value=sum(1 for x in g if x and x >= 1) / 3, comment=f"graus top-3 (None=nao rotulado): {g}")


def ev_ndcg(*, output, expected_output, **kw):
    if not _recomendar(expected_output):
        return []
    dcg = lambda gs: sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gs))  # noqa: E731
    obtido = [x or 0 for x in _graus(output, expected_output)]
    ideal = sorted((expected_output.get("relevancia") or {}).values(), reverse=True)[:3]
    if dcg(ideal) == 0:
        return []
    return Evaluation(name="ndcg_at_3", value=dcg(obtido) / dcg(ideal), comment=f"obtido={obtido} ideal={ideal}")


def ev_cobertura(*, output, expected_output, **kw):
    if not _recomendar(expected_output) or not output["entregues"]:
        return []
    rel = expected_output.get("relevancia") or {}
    n = sum(e["osm"] in rel for e in output["entregues"])
    return Evaluation(name="cobertura_rotulos", value=n / len(output["entregues"]), comment=f"{n}/{len(output['entregues'])} entregues tem rotulo")


def ev_reconsultas(*, output, **kw):
    return Evaluation(name="reconsultas", value=float(output["retry_count"]))


def ev_primeira_rodada(*, output, expected_output, **kw):
    if not _recomendar(expected_output):
        return []
    return Evaluation(name="aprovado_na_1a_rodada", value=1.0 if output["entregues"] and output["retry_count"] == 0 else 0.0)


def ev_latencia(*, output, **kw):
    return Evaluation(name="latencia_s", value=output["segundos"])


def ev_erro(*, output, **kw):
    return Evaluation(name="erro_de_agente", value=1.0 if output["erro"] else 0.0, comment=output["erro"] or "")


_NOTA = {"passos": r"passos=(\d+)", "tokens": r"tokens=(\d+)/(\d+)/(\d+)"}


def ev_fallback(*, output, **kw):
    if "agente llm" not in output["nota_retrieval"] and "FALLBACK" not in output["nota_retrieval"]:
        return []
    return Evaluation(name="usou_fallback", value=1.0 if "FALLBACK" in output["nota_retrieval"] else 0.0)


def ev_passos(*, output, **kw):
    m = re.search(_NOTA["passos"], output["nota_retrieval"])
    return Evaluation(name="passos_llm", value=float(m.group(1))) if m else []


def ev_tokens(*, output, **kw):
    m = re.search(_NOTA["tokens"], output["nota_retrieval"])
    if not m:
        return []
    return [Evaluation(name="tokens_prompt", value=float(m.group(1))), Evaluation(name="tokens_saida", value=float(m.group(2)))]


ITEM_EVALUATORS = [ev_fallback, ev_passos, ev_tokens, ev_acao_correta, ev_violacao, ev_fora_raio, ev_evidencia, ev_p3, ev_ndcg, ev_cobertura,
                   ev_reconsultas, ev_primeira_rodada, ev_latencia, ev_erro]


# --------------------------------------------------------------------------- avaliadores (run)
def _valores(item_results, nome):
    return [e.value for r in item_results for e in r.evaluations if e.name == nome and e.value is not None]


def _agg(nome_item, nome_run, fn):
    def run_ev(*, item_results, **kw):
        v = _valores(item_results, nome_item)
        if not v:  # sem dados (ex.: passos do LLM no modo pipeline): nao emite o score. O Langfuse REJEITA value=None
            return []
        return Evaluation(name=nome_run, value=fn(v), comment=f"n={len(v)}")
    return run_ev


media = lambda v: sum(v) / len(v)  # noqa: E731
RUN_EVALUATORS = [
    _agg("p_at_3", "media_p_at_3", media), _agg("ndcg_at_3", "media_ndcg_at_3", media),
    _agg("acao_correta", "taxa_acao_correta", media), _agg("violacao_restricao_entregue", "total_violacoes_entregues", sum),
    _agg("entrega_fora_do_raio", "total_entregas_fora_do_raio", sum), _agg("cobertura_rotulos", "media_cobertura_rotulos", media),
    _agg("aprovado_na_1a_rodada", "taxa_aprovado_na_1a_rodada", media), _agg("reconsultas", "media_reconsultas", media),
    _agg("latencia_s", "media_latencia_s", media), _agg("evidencia_completa", "taxa_evidencia_completa", media),
    _agg("erro_de_agente", "total_erros_de_agente", sum),
    _agg("usou_fallback", "total_fallbacks", sum), _agg("passos_llm", "media_passos_llm", media),
    _agg("tokens_prompt", "media_tokens_prompt", media), _agg("tokens_saida", "media_tokens_saida", media),
]


def _git(*a):
    return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nome", default="retrieval-agente-llm")
    ap.add_argument("--so", help="ids separados por virgula (teste rapido)")
    ap.add_argument("--modo", choices=("pipeline", "llm"), default="pipeline")
    ap.add_argument("--prompt", choices=("v1", "v2"), default="v1", help="modo llm: versao do prompt do agente")
    ap.add_argument("--sem-fallback", action="store_true", help="modo llm: mede o agente cru (sem cair no pipeline)")
    args = ap.parse_args()

    global RETRIEVAL
    validador = EvidenceValidator(store=MemoryEvidenceStore())
    if args.modo == "llm":
        RETRIEVAL = RetrievalAgent(validator=validador, fallback=None if args.sem_fallback else _AUTO_FALLBACK, prompt=args.prompt)
    else:
        RETRIEVAL = RetrievalPipeline(validator=validador)
    aquecer_modelo()  # carrega o modelo antes de cronometrar (a latencia nao inclui o download/carga)
    lf = get_client()
    dataset = lf.get_dataset(DATASET)
    if args.so:
        quer = {f"bubbles-osm-v1-{t.strip()}" for t in args.so.split(",")}
        dataset.items = [i for i in dataset.items if i.id in quer]
    sha, ramo = _git("rev-parse", "--short", "HEAD"), _git("rev-parse", "--abbrev-ref", "HEAD")
    sujo = bool(_git("status", "--porcelain", "--", "orchestrator", "data-pipeline"))
    meta = {
        "commit": sha + ("+alteracoes-locais" if sujo else ""), "branch": ramo, "dataset": DATASET, "gabarito": "osm_v1",
        "retrieval": ("agente LLM (DeepSeek)" + (" SEM fallback" if args.sem_fallback else " com fallback ao pipeline")) if args.modo == "llm" else "RetrievalPipeline determinístico (busca -> gate -> reconsulta interna)", "validation": "EvidenceValidator como ferramenta/gate, MAX_RETRIES=2", "llm": os.getenv("DEEPSEEK_MODEL", "deepseek-flash") if args.modo == "llm" else "-",
        "llm_reasoning_effort": os.getenv("DEEPSEEK_REASONING_EFFORT", "none") if args.modo == "llm" else "-",
        "llm_strict": os.getenv("DEEPSEEK_STRICT", "0") if args.modo == "llm" else "-", "prompt": args.prompt if args.modo == "llm" else "-",
        "embedding": "paraphrase-multilingual-mpnet-base-v2", "nlu": "structured_request do dataset (DeepSeek deepseek-chat revisado)",
        "politica_acessibilidade": "wheelchair=yes explicito", "k": "3", "anotador": "Claude (unico, nao cego)",
    }
    resultado = dataset.run_experiment(
        name=args.nome, run_name=f"{args.nome}-{sha}", description="Baseline do pipeline determinístico atual (grafo real, NLU do dataset).",
        task=tarefa, evaluators=ITEM_EVALUATORS, run_evaluators=RUN_EVALUATORS, max_concurrency=1, metadata=meta,
    )
    print(resultado.format())
    lf.flush()

    linhas = []
    for r in resultado.item_results:
        linhas.append({"id": (r.item.input or {}).get("id") if hasattr(r.item, "input") else None, "output": r.output,
                       "scores": {e.name: e.value for e in r.evaluations}, "trace_id": getattr(r, "trace_id", None)})
    run_scores = {e.name: e.value for e in (getattr(resultado, "run_evaluations", None) or [])}
    saida = AV / f"resultado_{args.nome}.json"
    saida.write_text(json.dumps({"metadata": meta, "run_name": f"{args.nome}-{sha}", "run_scores": run_scores, "itens": linhas},
                                ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("\nescrito", saida.relative_to(RAIZ))


if __name__ == "__main__":
    main()
