"""Escolha do Retrieval por configuracao: RETRIEVAL_MODE=deterministic|llm (padrao deterministic).

    retrieval = criar_retrieval()                       # le RETRIEVAL_MODE
    retrieval = criar_retrieval("llm", prompt="v2")      # explicito
    grafo = montar_grafo(nlu)                            # Retrieval do RETRIEVAL_MODE + Communication Agent LLM

`deterministic` = RetrievalPipeline (sem LLM). `llm` = RetrievalAgent (DeepSeek) COM fallback para o pipeline,
que e o que se quer em producao; a avaliacao usa `fallback=None` para medir o agente cru.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional

from .graph import build_graph
from .retrieval_agent import _AUTO, RetrievalAgent
from .retrieval_pipeline import RetrievalPipeline

MODOS = ("deterministic", "llm")
MODO_PADRAO = "deterministic"


def modo_atual(modo: Optional[str] = None) -> str:
    m = (modo or os.getenv("RETRIEVAL_MODE") or MODO_PADRAO).strip().lower()
    if m not in MODOS:
        raise ValueError(f"RETRIEVAL_MODE invalido: {m!r}; use {' ou '.join(MODOS)}")
    return m


def criar_retrieval(modo: Optional[str] = None, *, fallback: Any = _AUTO, prompt: str = "v1", llm: Any = None, **colaboradores: Any) -> Callable:
    """`colaboradores`: validator, conexao_factory, embedder, buscar_fn, regioes_fn (iguais nos dois modos)."""
    if modo_atual(modo) == "llm":
        return RetrievalAgent(llm=llm, fallback=fallback, prompt=prompt, **colaboradores)
    return RetrievalPipeline(**colaboradores)


def montar_grafo(nlu: Callable, comunicacao: Optional[Callable] = None, modo: Optional[str] = None, **kw: Any):
    """Grafo padrao: `build_graph` com o Retrieval do modo escolhido (ver criar_retrieval) e, se `comunicacao` nao for
    dada, o Communication Agent LLM (`criar_comunicacao`: COMMUNICATION_MODE, padrao llm)."""
    if comunicacao is None:
        from .communication_agent import criar_comunicacao  # noqa: PLC0415

        comunicacao = criar_comunicacao()
    return build_graph(nlu, criar_retrieval(modo, **kw), comunicacao)
