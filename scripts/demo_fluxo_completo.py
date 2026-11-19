#!/usr/bin/env python3
"""Demonstracao: uma PERGUNTA em texto livre percorre o fluxo completo e os componentes colaboram.

    NLU (LLM) -> Retrieval (agente LLM + tools, ou pipeline) -> gate de auditoria -> Communication

Usa o DeepSeek, o PostgreSQL e o modelo de embeddings de verdade. Registra cada passo (chamadas ao LLM, tools, gate)
e gera um relato em Markdown. Grava a consulta e a auditoria no banco (evidencias_busca / evidencias_auditoria).

  python scripts/demo_fluxo_completo.py "Quero um cafe calmo e acessivel para cadeirante na Asa Sul, de manha, para ler"
  python scripts/demo_fluxo_completo.py "..." --modo deterministic            # Retrieval sem LLM
  python scripts/demo_fluxo_completo.py "..." --md docs/demo_fluxo_completo.md  # grava o relato
  python scripts/demo_fluxo_completo.py "..." --comunicacao orchestrator.communication:communication_agent   # formatador sem LLM
"""

import argparse
import importlib
import importlib.util
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

from orchestrator.evidence_store import PostgresEvidenceStore  # noqa: E402
from orchestrator.graph import run  # noqa: E402
from orchestrator.llm_client import LLMClient, extrair_chamadas  # noqa: E402
from orchestrator.nlu_agent import NLUAgent  # noqa: E402
from orchestrator.observabilidade import descarregar  # noqa: E402
from orchestrator.retrieval_common import _pipeline  # noqa: E402
from orchestrator.retrieval_factory import modo_atual, montar_grafo  # noqa: E402
from orchestrator.retrieval_gate import RetrievalGate  # noqa: E402
from orchestrator.retrieval_tools import RetrievalTools, _resumo_tool, aquecer_modelo  # noqa: E402
from orchestrator.validation_tool import EvidenceValidator  # noqa: E402

EVENTOS: list = []
T0 = time.time()


def _gravar(tipo, **dados):
    EVENTOS.append({"t": time.time() - T0, "tipo": tipo, **dados})


def instrumentar():
    """Grava, em ordem, o que cada componente fez (so neste script; o codigo do orquestrador nao muda)."""
    exec_orig, chat_orig, aud_orig = RetrievalTools.executar, LLMClient.chat, RetrievalGate.auditar

    def executar(self, nome, argumentos):
        res = exec_orig(self, nome, argumentos)
        _gravar("tool", nome=nome, args=argumentos, resumo=_resumo_tool(nome, res))
        return res

    def chat(self, messages, **kw):
        t = time.time()
        msg = chat_orig(self, messages, **kw)
        quem = "nlu" if kw.get("json_mode") else ("retrieval" if kw.get("tools") else "communication")
        _gravar("llm", quem=quem, dur=time.time() - t, chamadas=[(c.nome, c.argumentos) for c in extrair_chamadas(msg)],
                texto=(msg.content or "") if not extrair_chamadas(msg) else "")
        return msg

    def auditar(self, req, busca, place_ids=None):
        r = aud_orig(self, req, busca, place_ids)
        _gravar("gate", busca=busca.busca_id, selecao=list(place_ids) if place_ids else None, aprovado=r.aprovado,
                evidencias=[e.place_name for e in r.evidence_records], rejeitados=r.feedback.rejected_place_ids,
                hard_filters=r.feedback.hard_filters, diagnostico=r.feedback.diagnostics[:3])
        return r

    RetrievalTools.executar, LLMClient.chat, RetrievalGate.auditar = executar, chat, auditar


def carregar_comunicacao(spec):
    if not spec:
        return None, "Communication Agent (LLM), do grafo padrao"
    alvo, _, fn = spec.partition(":")
    if alvo.endswith(".py"):
        s = importlib.util.spec_from_file_location("comunicacao_externa", alvo)
        mod = importlib.util.module_from_spec(s)
        s.loader.exec_module(mod)
    else:
        mod = importlib.import_module(alvo)
    return getattr(mod, fn or "communication_agent"), spec


def curto(x, n=140):
    t = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return t if len(t) <= n else t[: n - 1] + "…"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pergunta")
    ap.add_argument("--modo", choices=("deterministic", "llm"), default="llm")
    ap.add_argument("--comunicacao", help="'arquivo.py:funcao' ou 'modulo:funcao' (padrao: Communication Agent LLM)")
    ap.add_argument("--md", help="grava o relato em Markdown neste arquivo")
    ap.add_argument("--request-id", default="demo-fluxo")
    a = ap.parse_args()

    instrumentar()
    aquecer_modelo()
    busca = _pipeline()[0]
    with busca.conectar() as con:
        categorias = [r[0] for r in con.execute("SELECT DISTINCT categoria FROM places WHERE categoria IS NOT NULL")]
    comunicacao, nome_com = carregar_comunicacao(a.comunicacao)  # None = o do grafo padrao
    validator = EvidenceValidator(store=PostgresEvidenceStore())
    grafo = montar_grafo(NLUAgent(LLMClient(), categorias), comunicacao, a.modo, validator=validator)

    global T0
    T0 = time.time()
    estado = run(grafo, a.pergunta, a.request_id)
    descarregar()
    relato = montar_relato(a, estado, nome_com)
    print(relato)
    if a.md:
        Path(a.md).write_text(relato, encoding="utf-8")
        print(f"\n[relato gravado em {a.md}]", file=sys.stderr)


def montar_relato(a, estado, nome_com):
    L = [f"> **Pergunta do usuário:** {a.pergunta}", "",
         f"Modo do Retrieval: `{modo_atual(a.modo)}` · Communication: {nome_com} · request_id `{a.request_id}`", ""]
    req = estado.get("structured_request")
    L += ["### 1. NLU Agent (LLM): texto livre → `structured_request` (Contrato 2)", ""]
    if req is not None:
        L += ["| Campo | Valor |", "|---|---|",
              f"| intenção válida / fora de escopo / impossível | {req.intent_valid} / {req.out_of_scope} / {req.impossible_criteria} |",
              f"| atividade | {req.activity} |", f"| categorias (da base) | `{req.target_amenities}` |", f"| clima (vibe) | {req.vibe} |",
              f"| tolerância a ruído | {req.noise_tolerance} |",
              f"| região · raio | {req.spatial_constraints.target_region} · {req.spatial_constraints.max_radius_km} km |",
              f"| turno · horário | {req.temporal_constraints.preferred_time_slot} · {req.temporal_constraints.specific_hours} |",
              f"| acessibilidade | cadeira de rodas={req.accessibility_requirements.wheelchair_required}, idosos={req.accessibility_requirements.elder_friendly}, pet={req.accessibility_requirements.pet_friendly} |",
              f"| foco semântico | `{req.search_vector_focus}` |", f"| pergunta de esclarecimento | {req.clarification_needed} |", ""]
        L += ["O texto livre foi **descartado** logo depois (RNF02): `raw_query` = `None` no estado.", ""]
    L += ["### 2. Retrieval: o que aconteceu por dentro (cronologia)", ""]
    n_llm = 0
    for e in EVENTOS:
        if e["tipo"] == "llm" and e["quem"] == "nlu":
            L.append(f"- `{e['t']:5.1f}s` **NLU** chamou o LLM ({e['dur']:.1f} s) e devolveu o JSON validado pelo contrato.")
        elif e["tipo"] == "llm" and e["quem"] == "communication":
            L.append(f"- `{e['t']:5.1f}s` **Communication** chamou o LLM ({e['dur']:.1f} s) para redigir a resposta; o texto passa por verificação em código.")
        elif e["tipo"] == "llm":
            n_llm += 1
            if e["chamadas"]:
                L.append(f"- `{e['t']:5.1f}s` **LLM, passo {n_llm}** ({e['dur']:.1f} s) pediu: " + "; ".join(f"`{n}({curto(g, 70)})`" for n, g in e["chamadas"]))
            else:
                L.append(f"- `{e['t']:5.1f}s` **LLM, passo {n_llm}** ({e['dur']:.1f} s) decidiu: `{curto(e['texto'], 200)}`")
        elif e["tipo"] == "tool":
            L.append(f"  - `{e['t']:5.1f}s` tool **{e['nome']}** → `{curto(e['resumo'], 220)}`")
        elif e["tipo"] == "gate":
            L.append(f"- `{e['t']:5.1f}s` **GATE** auditou a busca `{e['busca']}`"
                     + (f" (seleção {e['selecao']})" if e["selecao"] else "") + f": **{'APROVADO' if e['aprovado'] else 'REPROVADO'}**"
                     + (f"; evidências: {e['evidencias']}" if e["aprovado"] else f"; rejeitados {e['rejeitados']}, filtros novos {e['hard_filters']}, motivo: {curto(e['diagnostico'], 200)}"))
    L.append("")
    L += ["### 3. Evidências entregues (Contrato 4, auditadas e gravadas no PostgreSQL)", ""]
    ev = estado.get("evidence_records") or []
    itens = {i.place_id: i for i in estado["search_response"].items} if estado.get("search_response") else {}
    if ev:
        L += ["| # | Lugar | Distância | Score | Fonte no OpenStreetMap | Integridade do score |", "|---|---|---:|---:|---|---|"]
        for k, e in enumerate(ev, 1):
            i = itens.get(e.place_id)
            L.append(f"| {k} | **{e.place_name}** | {i.distance_km:.2f} km | {e.total_score:.3f} | {e.osm_reference.osm_link} | {'ok' if e.integrity_test.passed else 'FALHOU'} |")
        L += ["", "Notas de fundamentação do primeiro lugar (só fatos vindos do banco):", ""]
        L += [f"- {n}" for n in ev[0].grounding_notes]
    else:
        L.append("_Nenhuma evidência aprovada (abstenção ou esclarecimento)._")
    L += ["", f"### 4. Communication → resposta ao usuário", "", "```text", str(estado.get("final_response")), "```", ""]
    L += ["### 5. Trilha do grafo (`agent_trace`)", "", "| Nó | Próximo | Justificativa |", "|---|---|---|"]
    for t in estado["agent_trace"]:
        L.append(f"| `{t.agent}` | `{t.next_agent}` | {t.justification} |")
    nota = next((t.note for t in estado["agent_trace"] if t.agent == "retrieval"), "")
    L += ["", f"Nota do Retrieval: `{nota}`", ""]
    if estado.get("error"):
        L += [f"**Erro de agente:** `{estado['error']}`", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
