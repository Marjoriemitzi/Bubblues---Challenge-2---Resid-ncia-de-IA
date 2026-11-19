"""Verificacao independente da saida do NLU contra o que cada pedido de teste declara.

Nao confia no proprio modelo: parte da `tipo_pedido`/`restricoes` do dataset, de palavras-chave
do texto e das categorias reais da base. Cada achado e ERRO (contradiz o pedido) ou REVISAR
(plausivel, mas um humano deve olhar). `raio_max_km` de `restricoes` e metadado de teste que nao
aparece no texto, entao nao e cobrado.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

ACAO_POR_TIPO = {
    "Padrao": "recomendar",
    "Ambiguo": "clarificar",
    "Fora_De_Escopo": "abster",
    "Sem_Resultado_Possivel": "abster",
}
# Categorias de `places` que sao respostas razoaveis para cada pedido (julgamento do anotador).
CATEGORIAS_PLAUSIVEIS: Dict[str, Set[str]] = {
    "TC-01": {"cafe", "bakery"},
    "TC-02": {"bar", "cafe", "pub", "restaurant"},
    "TC-03": {"library", "arts_centre", "cafe", "community_centre", "gallery"},
    "TC-04": {"park", "garden"},
    "TC-05": {"cafe"},
    "TC-06": {"food_court", "park", "restaurant", "mall", "attraction"},
    "TC-07": {"restaurant"},
    "TC-08": {"cinema", "theatre", "cafe"},
    "TC-09": {"community_centre", "arts_centre"},
    "TC-10": {"park", "playground"},
    "TC-11": {"cafe", "bakery"},
    "TC-12": {"park", "pitch", "sports_centre", "playground"},
    "TC-13": {"restaurant"},
    "TC-14": {"garden", "park", "nature_reserve"},
    "TC-15": {"cafe", "fast_food", "bakery"},
}
REGIOES_TEXTO = ["asa sul", "asa norte", "plano piloto", "lago sul", "lago norte", "sudoeste", "aguas claras", "taguatinga"]
RUIDO_BAIXO = {"tranquilo", "silencioso", "muito_silencioso"}
HORARIO_ESPERADO = {"manha": "manha", "final_tarde": "tarde", "tarde": "tarde", "noite": "noite", "domingo_manha": "manha", "noite_ate_22h": "noite"}


def _norm(t: Any) -> str:
    s = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Achado:
    nivel: str  # ERRO | REVISAR
    campo: str
    detalhe: str


def acao_obtida(req: Dict[str, Any]) -> str:
    if not req["intent_valid"]:
        return "abster"
    return "clarificar" if req.get("clarification_needed") else "recomendar"


def verificar(pedido: Dict[str, Any], req: Dict[str, Any], categorias_base: Set[str]) -> List[Achado]:
    a: List[Achado] = []
    tid, texto, restr = pedido["id"], _norm(pedido["query"]), pedido.get("restricoes") or {}
    esperada, obtida = ACAO_POR_TIPO[pedido["tipo_pedido"]], acao_obtida(req)

    # 1. acao
    if obtida != esperada:
        a.append(Achado("ERRO", "acao", f"esperado '{esperada}', NLU resultou em '{obtida}'"))
    if esperada == "abster":
        flag = "out_of_scope" if pedido["tipo_pedido"] == "Fora_De_Escopo" else "impossible_criteria"
        if not req.get(flag) and not req["intent_valid"]:
            a.append(Achado("REVISAR", flag, f"abstencao correta, mas flag esperada '{flag}' esta falsa"))
        return a  # o resto nao se aplica a abstencao

    # 2. categorias
    cats = set(req["target_amenities"])
    if not cats and esperada == "recomendar":
        a.append(Achado("ERRO", "target_amenities", "vazio num pedido a recomendar"))
    if cats - categorias_base:
        a.append(Achado("ERRO", "target_amenities", f"categorias que nao existem na base: {sorted(cats - categorias_base)}"))
    plausiveis = CATEGORIAS_PLAUSIVEIS.get(tid)
    if plausiveis and cats:
        if not cats & plausiveis:
            a.append(Achado("ERRO", "target_amenities", f"{sorted(cats)} sem intersecao com o plausivel {sorted(plausiveis)}"))
        elif cats - plausiveis:
            a.append(Achado("REVISAR", "target_amenities", f"fora do esperado: {sorted(cats - plausiveis)} (plausivel: {sorted(plausiveis)})"))

    # 3. acessibilidade / pet
    acc = req["accessibility_requirements"]
    if restr.get("acessibilidade") == "yes" and not acc["wheelchair_required"]:
        a.append(Achado("ERRO", "wheelchair_required", "pedido exige acessibilidade e o NLU deixou false"))
    if acc["wheelchair_required"] and restr.get("acessibilidade") != "yes":
        a.append(Achado("ERRO" if not re.search(r"cadeira|rampa|escada|mobilidade", texto) else "REVISAR",
                        "wheelchair_required", "true sem o pedido declarar acessibilidade"))
    if restr.get("pet_friendly") and not acc["pet_friendly"]:
        a.append(Achado("ERRO", "pet_friendly", "pedido cita pets e o NLU deixou false"))
    if acc["pet_friendly"] and not restr.get("pet_friendly"):
        a.append(Achado("REVISAR", "pet_friendly", "true sem o pedido declarar pets"))
    if acc["elder_friendly"] and not re.search(r"idos|terceira idade|faixa etaria|60|70", texto):
        a.append(Achado("REVISAR", "elder_friendly", "true sem mencao a idosos no texto"))

    # 4. ruido
    if restr.get("ambiente") in RUIDO_BAIXO and req["noise_tolerance"] != "baixo":
        a.append(Achado("ERRO", "noise_tolerance", f"ambiente '{restr['ambiente']}' pede baixo; NLU: {req['noise_tolerance']}"))
    if req["noise_tolerance"] == "baixo" and restr.get("ambiente") not in RUIDO_BAIXO and not re.search(r"silenc|calm|tranquil|barulho|discreto", texto):
        a.append(Achado("REVISAR", "noise_tolerance", "baixo sem o texto pedir silencio/calma"))

    # 5. regiao
    mencionadas = [r for r in REGIOES_TEXTO if r in texto]
    regiao = _norm(req["spatial_constraints"].get("target_region"))
    if mencionadas and (not regiao or not any(m in regiao or regiao in m for m in mencionadas)):
        a.append(Achado("ERRO", "target_region", f"texto cita {mencionadas}; NLU extraiu '{req['spatial_constraints'].get('target_region')}'"))
    if regiao and not mencionadas:
        a.append(Achado("REVISAR", "target_region", f"regiao '{regiao}' sem aparecer no texto"))

    # 6. horario
    slot = _norm(req["temporal_constraints"].get("preferred_time_slot"))
    esperado = HORARIO_ESPERADO.get(restr.get("horario", ""))
    if esperado and re.search(r"manha|tarde|noite|domingo|22h|almoco", texto) and slot and slot != esperado:
        a.append(Achado("REVISAR", "preferred_time_slot", f"NLU '{slot}' vs dataset '{esperado}'"))

    # 7. higiene (RNF02)
    if req.get("raw_query") is not None:
        a.append(Achado("ERRO", "raw_query", "deveria ser nulo"))
    longos = [t for t in req["search_vector_focus"] if len(t) > 40]
    if longos or len(req["search_vector_focus"]) > 6:
        a.append(Achado("REVISAR", "search_vector_focus", "termos longos demais ou lista grande (copiou a frase?)"))
    if not req["search_vector_focus"]:
        a.append(Achado("REVISAR", "search_vector_focus", "vazio"))
    return a
