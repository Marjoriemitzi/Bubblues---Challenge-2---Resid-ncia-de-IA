"""NLU_Agent (LLM): texto livre -> `structured_request` (Contrato 2) do orquestrador.

E um agente de verdade: o DeepSeek le o pedido e preenche o contrato. O codigo so garante:
  - o JSON valida no Pydantic (`StructuredRequest`, com as regras de consistencia das flags);
  - `target_amenities` usa SO categorias que existem em `places.categoria`;
  - `raw_query` sai sempre nulo (RNF02) e `request_id` vem do estado, nao do modelo.
Resposta invalida volta ao modelo com o motivo, ate `max_tentativas`.

Nada do texto do usuario vai para `note`, logs ou excecoes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from pydantic import ValidationError

from .contracts import StructuredRequest
from .llm_client import LLMClient
from .state import AgentState


class NLUFalhou(Exception):
    """O modelo nao devolveu um structured_request valido dentro do limite de tentativas."""


EXEMPLO = {
    "intent_valid": True,
    "out_of_scope": False,
    "out_of_scope_reason": None,
    "impossible_criteria": False,
    "impossible_criteria_reason": None,
    "activity": "lanchar com a familia",
    "target_amenities": ["cafe"],
    "vibe": "indefinida",
    "noise_tolerance": "indiferente",
    "spatial_constraints": {"target_region": "Lago Norte", "max_radius_km": 3.0},
    "temporal_constraints": {"preferred_time_slot": "tarde", "specific_hours": None},
    "accessibility_requirements": {"wheelchair_required": False, "elder_friendly": False, "pet_friendly": False},
    "search_vector_focus": ["familiar", "lanches"],
    "clarification_needed": None,
}


def montar_prompt(categorias: List[str]) -> str:
    return f"""Voce e o NLU do Bubbles, um sistema que recomenda ESPACOS PUBLICOS do Distrito Federal
(dados do OpenStreetMap) para convivencia e encontros. Converta o pedido do usuario em um JSON
(contrato abaixo). Responda SOMENTE com o JSON.

CAMPOS
- intent_valid: true se o pedido pode virar uma busca de lugar publico; false se for fora de escopo
  ou impossivel.
- out_of_scope: true se NAO e um pedido de lugar publico para convivencia (ex.: frete, mudanca,
  servico, compra). Exige out_of_scope_reason (curto, sem repetir o texto do usuario).
- impossible_criteria: true se o pedido exige algo que nao existe ou e contraditorio (ex.: pista de
  patinacao no gelo, silencio absoluto com show alto). Exige impossible_criteria_reason.
  Horario incomum (madrugada) NAO e impossivel: so informe o horario; outro componente verifica.
- Se out_of_scope ou impossible_criteria for true => intent_valid=false. Caso contrario intent_valid=true.
- activity: o que a pessoa quer fazer (texto curto). Em fora de escopo/impossivel, descreva em poucas palavras.
- target_amenities: de 1 a 3 valores EXATOS desta lista de categorias da base: {json.dumps(categorias, ensure_ascii=False)}.
  Inclua apenas categorias que correspondem ao TIPO DE LUGAR descrito. Nao acrescente categorias por
  associacao de clima ou bebida (ex.: nao inclua bar/pub se o usuario nao pediu bar). Lista vazia apenas
  se intent_valid=false.
- vibe: o clima que o USUARIO pediu, em poucas palavras. Se ele nao descreveu o clima, "indefinida".
  Nunca copie valores do exemplo.
- noise_tolerance: "baixo" SOMENTE se o usuario pedir silencio, calma, discricao ou pouco barulho;
  "moderado" SOMENTE se ele citar som/movimento moderado; em qualquer outro caso "indiferente".
- spatial_constraints.target_region: SOMENTE o nome de um bairro, regiao administrativa ou setor do DF
  citado pelo usuario (ex.: "Asa Sul", "Taguatinga"). Referencias relativas ("perto da universidade",
  "perto do metro", "no centro") NAO sao regiao: use null e ponha o termo em search_vector_focus.
  max_radius_km: a distancia que ele pedir; se nao pedir, 3.0.
- temporal_constraints.preferred_time_slot: "manha", "tarde", "noite", "madrugada" ou null.
  specific_hours: texto com o horario pedido (ex.: "ate 22h", "14:00-18:00") ou null.
- accessibility_requirements: wheelchair_required=true SO se citar cadeira de rodas, mobilidade reduzida,
  rampa ou "sem escadas"; elder_friendly=true se citar idosos/terceira idade; pet_friendly=true se
  citar cachorro/pet. Na duvida, false.
- search_vector_focus: de 2 a 5 termos curtos sobre atmosfera e atributos desejados (sem copiar a frase
  inteira e sem dados pessoais).
- clarification_needed: se o pedido for vago demais para buscar (ex.: "qualquer lugar legal") mantenha
  intent_valid=true e escreva UMA pergunta curta em portugues; senao null.
- NAO invente: o que o usuario nao disse fica null/false/"indiferente".
- NAO inclua request_id nem raw_query.

EXEMPLO de saida valida (json):
{json.dumps(EXEMPLO, ensure_ascii=False, indent=2)}
"""


class NLUAgent:
    def __init__(self, llm: LLMClient, categorias: List[str], max_tentativas: int = 3):
        self.llm = llm
        self.categorias = sorted(set(categorias))
        self.max_tentativas = max_tentativas
        self._prompt = montar_prompt(self.categorias)

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        texto = state.get("raw_query")
        if not texto or not texto.strip():
            raise NLUFalhou("raw_query ausente")
        mensagens: List[Dict[str, Any]] = [
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": texto},
        ]
        for tentativa in range(1, self.max_tentativas + 1):
            msg = self.llm.chat(mensagens, json_mode=True, temperature=0.0)
            problema = None
            try:
                dados = json.loads(msg.content)
                if not isinstance(dados, dict):
                    raise ValueError("a resposta deve ser um objeto JSON")
                dados["request_id"] = state["request_id"]
                dados["raw_query"] = None
                req = StructuredRequest.model_validate(dados)
                fora = [c for c in req.target_amenities if c not in self.categorias]
                if fora:
                    problema = f"target_amenities fora da lista de categorias: {fora}"
            except (json.JSONDecodeError, ValueError, ValidationError) as erro:
                problema = f"JSON invalido para o contrato: {str(erro)[:400]}"
            if problema is None:
                return {
                    "structured_request": req.model_dump(),
                    "note": f"nlu llm ({self.llm.model}); tentativas={tentativa}",
                }
            mensagens += [
                {"role": "assistant", "content": msg.content},
                {"role": "user", "content": f"{problema}. Corrija e devolva apenas o JSON completo."},
            ]
        raise NLUFalhou(f"sem structured_request valido em {self.max_tentativas} tentativas")
