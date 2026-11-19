"""Communication_Agent (LLM): escreve a resposta final ao usuario a partir das evidencias auditadas.

Evolui o formatador do PR #15 (`communication.py`, deterministico), que continua sendo o FALLBACK e o caminho dos
desvios (fora de escopo, impossivel, esclarecimento, sem evidencia aprovada): neles a mensagem ja vem pronta do NLU.

Com evidencias aprovadas, o DeepSeek redige a resposta, mas o codigo controla o que ele pode dizer (RNF01):
  - o modelo recebe SO fatos vindos de `evidence_records` e `search_response` (nome, distancia, notas, tags, link OSM);
  - `avisos` calculados em codigo (raio ampliado, horario nao confirmado) sao obrigatorios no texto;
  - a resposta e VERIFICADA: todo lugar e todo link citados existem nas evidencias, nenhuma URL fora delas, toda
    distancia em km bate com os dados, e cada aviso aparece. Reprovou: o modelo recebe o motivo e tenta de novo;
    esgotou as tentativas ou o LLM falhou: formatador do PR #15 + os avisos escritos em codigo.

Nada do texto do usuario vai para `note` (RNF02).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from .communication import _get, _get_profile, communication_agent as formatador
from .state import AgentState

MAX_LUGARES = 3

SISTEMA = """Voce e o Communication do Bubbles, um sistema que recomenda ESPACOS PUBLICOS do Distrito Federal
(dados do OpenStreetMap). Escreva a resposta final ao usuario em portugues do Brasil, em texto simples (sem Markdown pesado).

REGRAS (inviolaveis)
1. Use SOMENTE os dados do JSON recebido. Nunca invente nome, endereco, horario, nota, preco ou caracteristica.
2. Cite TODOS os lugares recebidos, na ordem dada, cada um com nome, distancia (km, como veio) e o motivo da
   recomendacao tirado de `destaques`, e termine cada lugar com o link OSM exatamente como veio.
3. Se um dado nao veio (ex.: endereco nulo), nao fale dele; nao diga "nao informado" para tudo, so quando for relevante.
4. Os `avisos` sao obrigatorios: incorpore cada um ao texto com clareza, sem minimizar. Para o aviso de raio use a palavra
   "raio"; para o de horario use a palavra "horário".
5. Tom conforme `perfil`: "helena" = calmo e simples, frases curtas; "carla" = objetivo e direto; "neutro" = cordial.
6. Seja breve (ate ~150 palavras no total, alem dos links). Nao faca perguntas e nao prometa nada que o sistema nao fez."""

_RE_URL = re.compile(r"https?://[^\s)\]>\"']+")
_RE_KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*km", re.I)


class ComunicacaoReprovada(Exception):
    """O texto do modelo violou as regras de fundamentacao dentro do limite de tentativas."""


def _num(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def montar_fatos(state: AgentState) -> Optional[Dict[str, Any]]:
    """Fatos permitidos ao modelo, ou None quando o caso e um desvio/sem evidencia (caminho deterministico)."""
    req = state.get("structured_request")
    if req is None or state.get("error"):
        return None
    if _get(req, "out_of_scope", False) or _get(req, "impossible_criteria", False) or _get(req, "clarification_needed"):
        return None
    sr = state.get("search_response")
    itens = {_get(i, "place_id"): i for i in (_get(sr, "items", []) or [])}
    aprovadas = [e for e in (state.get("evidence_records") or []) if _get(_get(e, "integrity_test", {}), "passed", False)]
    aprovadas.sort(key=lambda e: float(_get(e, "total_score", 0) or 0), reverse=True)
    lugares: List[Dict[str, Any]] = []
    for e in aprovadas:
        item = itens.get(_get(e, "place_id"))
        link = _get(_get(e, "osm_reference", {}), "osm_link")
        nome = _get(e, "place_name")
        if item is None or not nome or not link:
            continue
        destaques = [str(n) for n in (_get(e, "grounding_notes", []) or []) if n]
        tags = _get(e, "matched_tags", []) or []
        if tags:
            destaques.append("Caracteristicas registradas no OpenStreetMap: " + ", ".join(str(t) for t in tags))
        lugares.append({
            "posicao": len(lugares) + 1, "nome": nome, "distancia_km": round(float(_get(item, "distance_km", 0) or 0), 2),
            "endereco": _get(item, "address"), "destaques": destaques, "link_osm": link,
        })
        if len(lugares) == MAX_LUGARES:
            break
    if not lugares:
        return None

    avisos: List[Dict[str, str]] = []
    pedido = _num(_get(_get(req, "spatial_constraints", {}), "max_radius_km"))
    filtros = _get(sr, "applied_filters", {})
    aplicado = _num(_get(filtros, "radius_km"))
    if _get(filtros, "expanded_once", False) or (pedido and aplicado and aplicado > pedido):
        avisos.append({"tipo": "raio", "texto": f"O raio da busca foi ampliado de {pedido:g} km para {aplicado:g} km porque "
                       "nao havia resultados suficientes no raio pedido, entao os lugares podem estar mais longe do que o desejado."
                       if pedido and aplicado else "O raio da busca foi ampliado porque nao havia resultados suficientes."})
    tc = _get(req, "temporal_constraints", {})
    horario = " ".join(x for x in (_get(tc, "preferred_time_slot"), _get(tc, "specific_hours")) if x)
    if horario:
        sem = [p["nome"] for p, e in zip(lugares, aprovadas_na_ordem(aprovadas, lugares))
               if not any(str(n).startswith("Horário de funcionamento") for n in (_get(e, "grounding_notes", []) or []))]
        if sem:
            avisos.append({"tipo": "horario", "texto": f"Nao foi possivel confirmar no OpenStreetMap o horario pedido ('{horario}') para: "
                           + ", ".join(sem) + ". Vale confirmar com o local antes de ir."})
    return {"perfil": _get_profile(state), "lugares": lugares, "avisos": avisos,
            "_raios": [x for x in (pedido, aplicado) if x is not None]}


def aprovadas_na_ordem(aprovadas: List[Any], lugares: List[Dict[str, Any]]) -> List[Any]:
    por_link = {_get(_get(e, "osm_reference", {}), "osm_link"): e for e in aprovadas}
    return [por_link[l["link_osm"]] for l in lugares]


def verificar(texto: str, fatos: Dict[str, Any]) -> Optional[str]:
    """None se o texto esta fundamentado; senao, o motivo (volta ao modelo)."""
    t = (texto or "").strip()
    if not t:
        return "resposta vazia"
    links = {l["link_osm"] for l in fatos["lugares"]}
    for url in _RE_URL.findall(t):
        if url.rstrip(".,;") not in links:
            return f"URL que nao esta nas evidencias: {url}"
    for l in fatos["lugares"]:
        if l["link_osm"] not in t:
            return f"falta o link OSM de {l['nome']}"
        if l["nome"].lower() not in t.lower():
            return f"falta o lugar {l['nome']}"
    permitidos = [l["distancia_km"] for l in fatos["lugares"]] + fatos["_raios"]
    for m in _RE_KM.findall(t):
        v = float(m.replace(",", "."))
        if not any(abs(v - p) <= 0.011 for p in permitidos):
            return f"distancia {m} km nao existe nos dados"
    baixo = t.lower()
    for a in fatos["avisos"]:
        palavra = "raio" if a["tipo"] == "raio" else "horário"
        if palavra not in baixo and not (a["tipo"] == "horario" and "horario" in baixo):
            return f"falta o aviso obrigatorio de {a['tipo']}"
    return None


class CommunicationAgent:
    def __init__(self, llm: Any, fallback: Callable[[AgentState], Dict[str, Any]] = formatador, max_tentativas: int = 2):
        self.llm = llm
        self.fallback = fallback
        self.max_tentativas = max_tentativas

    def _fallback(self, state: AgentState, fatos: Dict[str, Any], motivo: str) -> Dict[str, Any]:
        base = dict(self.fallback(state))
        if fatos["avisos"]:
            base["final_response"] = str(base.get("final_response", "")) + "\n\nAvisos:\n" + "\n".join(f"- {a['texto']}" for a in fatos["avisos"])
        base["note"] = f"comunicacao: formatador deterministico ({motivo})"
        return base

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        fatos = montar_fatos(state)
        if fatos is None:
            return {**self.fallback(state), "note": "comunicacao: desvio ou sem evidencia (deterministico)"}
        publico = {k: v for k, v in fatos.items() if not k.startswith("_")}
        mensagens: List[Dict[str, Any]] = [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": json.dumps(publico, ensure_ascii=False)},
        ]
        problema = ""
        for tentativa in range(1, self.max_tentativas + 1):
            try:
                msg = self.llm.chat(mensagens, temperature=0.2, max_tokens=900)
            except Exception as exc:  # LLM fora do ar: o usuario ainda recebe a resposta auditada
                return self._fallback(state, fatos, f"llm falhou: {type(exc).__name__}")
            texto = (msg.content or "").strip()
            problema = verificar(texto, fatos) or ""
            if not problema:
                return {"final_response": texto, "note": f"comunicacao llm ({getattr(self.llm, 'model', '?')}); tentativas={tentativa}"}
            mensagens += [{"role": "assistant", "content": texto},
                          {"role": "user", "content": f"Reprovado na verificacao: {problema}. Reescreva a resposta inteira respeitando as regras."}]
        return self._fallback(state, fatos, f"texto reprovado: {problema[:60]}")


def criar_comunicacao(modo: Optional[str] = None, llm: Any = None) -> Callable[[AgentState], Dict[str, Any]]:
    """`COMMUNICATION_MODE=llm` (padrao) cria o agente LLM (sem DEEPSEEK_API_KEY e sem pedir `llm`, cai no formatador); `deterministic` devolve o formatador do PR #15."""
    explicito = bool(modo or os.getenv("COMMUNICATION_MODE"))
    modo = (modo or os.getenv("COMMUNICATION_MODE") or "llm").strip().lower()
    if modo == "deterministic":
        return formatador
    if modo != "llm":
        raise ValueError(f"COMMUNICATION_MODE invalido: {modo!r}; use 'llm' ou 'deterministic'")
    if llm is None:
        from .llm_client import LLMClient, LLMError  # noqa: PLC0415

        try:
            llm = LLMClient()
        except LLMError:
            if explicito:
                raise
            return formatador  # sem chave do DeepSeek e sem pedir llm: degrada para o formatador, sem quebrar
    return CommunicationAgent(llm)
