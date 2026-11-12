"""Tracing opcional com Langfuse.

Sem o pacote `langfuse` ou sem LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY, tudo aqui vira
no-op: testes e execucoes locais nao mudam. Com credenciais, cada busca gera um trace
(`place-search`) com observacoes aninhadas e tipadas (embedding, chain, retriever, span).

Convencoes (https://langfuse.com/docs/observability/best-practices):
  - nomes estaveis, verbo primeiro, sem valores dinamicos (valores vao em metadata);
  - input/output explicitos e legiveis (nunca o vetor de 768 floats nem a conexao);
  - coordenadas do usuario arredondadas antes de ir para o trace.
"""

import os
from contextlib import contextmanager, nullcontext

from dotenv import load_dotenv

_cliente = None
_inicializado = False


def cliente():
    """Devolve o cliente Langfuse, ou None se o tracing estiver desligado."""
    global _cliente, _inicializado
    if _inicializado:
        return _cliente
    _inicializado = True
    # Langfuse so pode ser instanciado depois de carregar o .env.
    load_dotenv()
    if os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower() == "false":
        return None
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import get_client
    except ImportError:
        return None
    _cliente = get_client()
    return _cliente


@contextmanager
def observacao(nome, tipo="span", **campos):
    """Abre uma observacao aninhada na atual; entrega o objeto (ou None se desligado).

    Excecoes marcam a observacao como ERROR e sao relancadas.
    """
    lf = cliente()
    if lf is None:
        yield None
        return
    with lf.start_as_current_observation(name=nome, as_type=tipo, **campos) as obs:
        try:
            yield obs
        except Exception as erro:
            obs.update(level="ERROR", status_message=f"{type(erro).__name__}: {erro}")
            raise


def atualizar(obs, **campos):
    if obs is not None:
        obs.update(**campos)


def atributos(**campos):
    """Propaga trace_name/tags/metadata/... para todas as observacoes filhas."""
    if cliente() is None:
        return nullcontext()
    from langfuse import propagate_attributes

    return propagate_attributes(**campos)


def finalizar():
    """Envia os eventos pendentes. Obrigatorio em scripts curtos (CLI) antes de sair."""
    if _cliente is not None:
        _cliente.flush()


def coordenada_anonima(valor):
    """~110 m de precisao: suficiente para depurar, sem expor a localizacao exata."""
    return None if valor is None else round(float(valor), 3)
