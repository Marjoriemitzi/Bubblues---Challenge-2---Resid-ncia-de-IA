"""Horario de funcionamento: o `opening_hours` do OSM contra o que o pedido exige.

Duas pontas, ambas deterministicas e sem LLM:
  - `parse_opening_hours(texto)`: subconjunto util do formato OSM (dias, faixas, "24/7", "off", varias regras,
    virada de meia-noite, feriados `PH` ignorados). Qualquer coisa fora disso (meses, semanas, sunrise, texto livre
    em portugues) devolve None = "nao confirmado".
  - `extrair_exigencias(slot, texto)`: o que o usuario pediu em `preferred_time_slot` e `specific_hours`:
    "ate 22h", "as 03:30", "14:00 - 18:00", "sabado a noite", "manha de domingo", "fim de semana"...

PRINCIPIOS (RNF01): so REJEITA com evidencia. Horario ausente, ilegivel ou pedido sem exigencia de horario nunca
reprova. E e tolerante nas fronteiras: um turno ("tarde") exige apenas SOBREPOSICAO com o horario do lugar.

    avaliar_horario("Mo-Fr 08:15-17:30", "noite", None)  -> ("incompativel", "...")
    avaliar_horario("09:00-17:00", None, "ate 22h")       -> ("incompativel", "...")
    avaliar_horario("Tu-Su 09:00-17:00", None, "manha de domingo") -> ("compativel", None)
    avaliar_horario("restricted", "tarde", None)          -> ("nao_confirmado", None)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

DIAS_OSM = ["mo", "tu", "we", "th", "fr", "sa", "su"]
_IDX = {d: i for i, d in enumerate(DIAS_OSM)}
DIAS_TEXTO = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
NOMES = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
# Janelas (minutos desde 00:00). "noite" vai ate 24:00; a madrugada seguinte vem da virada de meia-noite do lugar.
JANELAS = {"madrugada": (0, 360), "manha": (360, 720), "tarde": (720, 1140), "noite": (1080, 1440)}

Agenda = Dict[int, List[Tuple[int, int]]]  # dia (0=segunda) -> intervalos (inicio, fim) em minutos


def _norm(t: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# opening_hours do OSM
# --------------------------------------------------------------------------
_RE_HORA = re.compile(r"\d{1,2}:\d{2}")
_RE_FAIXA = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$")


def _dias_da_regra(spec: str) -> Optional[Set[int]]:
    """'Mo-Fr', 'Mo,We,Sa-Su', 'PH,Su': devolve os dias da semana; None se tiver algo que nao entendemos.
    Conjunto vazio = regra so de feriados (PH/SH), que ignoramos."""
    dias: Set[int] = set()
    so_feriado = False
    for item in [i.strip().lower() for i in spec.split(",") if i.strip()]:
        if item in ("ph", "sh"):
            so_feriado = True
            continue
        m = re.fullmatch(r"([a-z]{2})(?:\s*-\s*([a-z]{2}))?", item)
        if not m or m.group(1) not in _IDX or (m.group(2) is not None and m.group(2) not in _IDX):
            return None
        a = _IDX[m.group(1)]
        b = _IDX[m.group(2)] if m.group(2) else a
        d = a
        while True:  # tolera intervalo que vira a semana (Sa-Mo)
            dias.add(d)
            if d == b:
                break
            d = (d + 1) % 7
    if not dias and not so_feriado:
        return set(range(7))  # regra sem dias = todos os dias
    return dias


def parse_opening_hours(texto: Optional[str]) -> Optional[Agenda]:
    """Agenda por dia da semana, ou None se o texto estiver fora do subconjunto que entendemos."""
    if not texto or not str(texto).strip():
        return None
    t = str(texto).strip()
    if t.lower() == "24/7":
        return {d: [(0, 1440)] for d in range(7)}

    base: Agenda = {d: [] for d in range(7)}
    sobra: Agenda = {d: [] for d in range(7)}  # parte que passa da meia-noite entra no dia seguinte
    houve_regra = False
    # Semantica do OSM: ';' separa regras que SOBRESCREVEM os dias da anterior; uma ',' depois de um horario e antes de
    # um dia ("Mo-Fr 11:00-21:00, Sa 09:00-21:00") separa regras ADITIVAS do mesmo bloco. Nao confundir com
    # "Mo,We 09:00" (virgula entre dias) nem "08:00-12:00,14:00-18:00" (virgula entre faixas).
    regras: List[Tuple[int, str]] = []  # (indice do bloco ';', regra)
    for i, bloco in enumerate(t.split(";")):
        regras += [(i, r) for r in re.split(r"(?<=\d)\s*,\s*(?=(?:Mo|Tu|We|Th|Fr|Sa|Su|PH|SH)\b)", bloco)]
    zerados: Set[Tuple[int, int]] = set()  # (bloco, dia) ja sobrescritos neste bloco
    for bloco_i, regra in [(i, r.strip()) for i, r in regras if r.strip()]:
        m = _RE_HORA.search(regra)
        fechado = False
        if m:
            spec, horas = regra[: m.start()].strip(), regra[m.start():].strip()
        elif re.search(r"\b(off|closed)$", regra.strip(), re.I):
            spec, horas, fechado = re.sub(r"\s*\b(off|closed)$", "", regra.strip(), flags=re.I), "", True
        else:
            return None
        dias = _dias_da_regra(spec)
        if dias is None:
            return None
        intervalos: List[Tuple[int, int]] = []
        if not fechado:
            for faixa in [h.strip() for h in horas.split(",") if h.strip()]:
                f = _RE_FAIXA.match(faixa)
                if not f:
                    return None
                ini, fim = int(f[1]) * 60 + int(f[2]), int(f[3]) * 60 + int(f[4])
                if ini > 1440 or fim > 1440 or int(f[2]) > 59 or int(f[4]) > 59:
                    return None
                if fim <= ini:
                    fim += 1440
                intervalos.append((ini, fim))
        if not dias:
            continue  # regra so de feriado
        houve_regra = True
        for d in dias:
            if (bloco_i, d) not in zerados:
                base[d] = []  # um bloco novo (';') sobrescreve o dia; regras aditivas (',') do mesmo bloco somam
                zerados.add((bloco_i, d))
        for d in dias:
            for ini, fim in intervalos:
                if fim > 1440:
                    base[d].append((ini, 1440))
                    sobra[(d + 1) % 7].append((0, fim - 1440))
                else:
                    base[d].append((ini, fim))
    if not houve_regra:
        return None
    return {d: sorted(base[d] + sobra[d]) for d in range(7)}


# --------------------------------------------------------------------------
# o que o pedido exige
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Exigencia:
    tipo: str  # "janela" (sobreposicao) | "em" (aberto neste minuto) | "ate" (aberto ate este minuto, inclusive)
    inicio: int = 0
    fim: int = 0
    descricao: str = ""


def _T(p: str) -> str:
    return rf"(?P<{p}h>\d{{1,2}})(?:h(?P<{p}a>\d{{2}})?|:(?P<{p}b>\d{{2}}))"


def _min(m: "re.Match", p: str) -> Optional[int]:
    h = int(m.group(p + "h"))
    mi = int(m.group(p + "a") or m.group(p + "b") or 0)
    return h * 60 + mi if 0 <= h <= 24 and 0 <= mi <= 59 else None


def extrair_exigencias(slot: Optional[str], texto: Optional[str]) -> Tuple[Optional[Set[int]], List[Exigencia]]:
    """(dias exigidos ou None = qualquer dia, exigencias). Lista vazia = o pedido nao restringe horario."""
    t = _norm(texto)
    exig: List[Exigencia] = []

    def consome(padrao: str, fn):
        nonlocal t
        for m in list(re.finditer(padrao, t)):
            e = fn(m)
            if e:
                exig.append(e)
        t = re.sub(padrao, " ", t)

    consome(rf"\bate\s+(?:as\s+)?{_T('a')}", lambda m: _ex("ate", _min(m, "a"), None, m.group(0)))
    consome(rf"{_T('a')}\s*(?:-|a|as|ate)\s*{_T('b')}", lambda m: _ex("janela", _min(m, "a"), _min(m, "b"), m.group(0)))
    consome(rf"\b(?:a partir d[ae]s?|depois d[ae]s?|as|a)\s+{_T('a')}", lambda m: _ex("em", _min(m, "a"), None, m.group(0)))
    consome(_T("a"), lambda m: _ex("em", _min(m, "a"), None, m.group(0)))

    dias: Optional[Set[int]] = None
    achados = {i for nome, i in DIAS_TEXTO.items() if re.search(rf"\b{nome}", t)}
    if re.search(r"fim de semana|fins de semana|finais? de semana", t):
        achados |= {5, 6}
    if re.search(r"dias? uteis|durante a semana|dia de semana", t):
        achados |= {0, 1, 2, 3, 4}
    if achados:
        dias = achados

    turnos = {s for s in JANELAS if re.search(rf"\b{s}", t)}
    s = _norm(slot)
    if s in JANELAS:
        turnos.add(s)
    if turnos:
        # varios turnos citados = "qualquer um deles" (ex.: slot 'tarde' + texto 'sabado a noite')
        exig.append(Exigencia("turnos", descricao="/".join(sorted(turnos))))
    if dias and not exig:
        exig.append(Exigencia("janela", 0, 1440, "dia inteiro"))  # so o dia: tem que abrir em algum momento
    return dias, exig


def _ex(tipo: str, a: Optional[int], b: Optional[int], desc: str) -> Optional[Exigencia]:
    if a is None or (tipo == "janela" and b is None):
        return None
    if tipo == "janela" and b is not None and b <= a:
        b += 1440
    return Exigencia(tipo, a, b or 0, desc.strip())


# --------------------------------------------------------------------------
# avaliacao
# --------------------------------------------------------------------------
def _satisfaz(e: Exigencia, intervalos: List[Tuple[int, int]]) -> bool:
    if e.tipo == "janela":
        return any(s < e.fim and f > e.inicio for s, f in intervalos)
    if e.tipo == "em":
        return any(s <= e.inicio < f or (e.inicio == 1440 and f == 1440) for s, f in intervalos)
    if e.tipo == "ate":  # aberto durante o minuto anterior ao horario pedido
        alvo = max(e.inicio - 1, 0)
        return any(s <= alvo < f for s, f in intervalos)
    if e.tipo == "turnos":
        return any(s < JANELAS[n][1] and f > JANELAS[n][0] for n in e.descricao.split("/") for s, f in intervalos)
    return True


def avaliar_horario(
    opening_hours: Optional[str], preferred_slot: Optional[str], specific_hours: Optional[str]
) -> Tuple[str, Optional[str]]:
    """('sem_restricao' | 'nao_confirmado' | 'compativel' | 'incompativel', motivo)."""
    dias, exigencias = extrair_exigencias(preferred_slot, specific_hours)
    if not exigencias:
        return "sem_restricao", None
    agenda = parse_opening_hours(opening_hours)
    if agenda is None:
        return "nao_confirmado", None

    candidatos = sorted(dias) if dias is not None else list(range(7))
    if any(all(_satisfaz(e, agenda[d]) for e in exigencias) for d in candidatos):
        return "compativel", None

    pedido = " ".join(x for x in (_norm(preferred_slot), _norm(specific_hours)) if x)
    onde = f" em {'/'.join(NOMES[d] for d in sorted(dias))}" if dias is not None else " em nenhum dia"
    return "incompativel", f"Horário de funcionamento '{opening_hours}' não atende ao pedido ('{pedido}'){onde}."
