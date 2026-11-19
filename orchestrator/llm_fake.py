"""LLM de mentira com roteiro, para testar agentes sem rede nem chave.

    llm = LLMFalso(
        chamar(("resolver_regiao", {"nome": "Asa Sul"})),     # 1a resposta: o modelo pede uma tool
        texto('{"busca_escolhida": "B1"}'),                   # 2a resposta: texto final
    )

Implementa a mesma interface de `LLMClient.chat` e guarda o que recebeu (`mensagens_recebidas`).
Um item do roteiro que seja uma excecao e levantado (ex.: `LLMError("...")`).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from .llm_client import Uso


def texto(conteudo: str, raciocinio: Optional[str] = None):
    """Resposta final do modelo (sem tools)."""
    return SimpleNamespace(role="assistant", content=conteudo, tool_calls=None, reasoning_content=raciocinio)


def chamar(*chamadas: Tuple[str, Any], conteudo: Optional[str] = None, raciocinio: Optional[str] = None):
    """Resposta em que o modelo pede ferramentas. Cada chamada e (nome, argumentos); argumentos pode ser um
    dict (vira JSON) ou um texto cru (para simular JSON invalido)."""
    cs = []
    for i, (nome, args) in enumerate(chamadas, start=1):
        bruto = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
        cs.append(SimpleNamespace(id=f"call_{i}", type="function", function=SimpleNamespace(name=nome, arguments=bruto)))
    return SimpleNamespace(role="assistant", content=conteudo, tool_calls=cs, reasoning_content=raciocinio)


class LLMFalso:
    model = "llm-falso"

    def __init__(self, *roteiro: Any):
        self.roteiro: List[Any] = list(roteiro)
        self.mensagens_recebidas: List[List[Dict[str, Any]]] = []
        self.parametros: List[Dict[str, Any]] = []
        self.uso = Uso()

    @property
    def chamadas(self) -> int:
        return self.uso.chamadas

    def chat(self, messages, *, json_mode=False, tools=None, tool_choice=None, temperature=0.0,
             max_tokens=None, reasoning_effort=None, prazo=None):
        self.uso.chamadas += 1
        self.mensagens_recebidas.append([dict(m) for m in messages])
        self.parametros.append({"json_mode": json_mode, "tools": tools, "tool_choice": tool_choice,
                                "reasoning_effort": reasoning_effort, "prazo": prazo})
        if not self.roteiro:
            raise AssertionError("LLMFalso: o roteiro acabou, mas o agente pediu outra resposta")
        passo = self.roteiro.pop(0)
        if isinstance(passo, BaseException):
            raise passo
        return passo
