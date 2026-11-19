"""Tracing opcional no Langfuse (SDK v4/v5: observacoes aninhadas via OpenTelemetry).

Regras:
  - OPT-IN por chave: so liga se houver LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY (e LANGFUSE_TRACING_ENABLED != false).
    Sem chave, sem o pacote `langfuse`, ou sob pytest, tudo aqui e no-op.
  - NUNCA derruba o sistema: qualquer falha do tracing e engolida; excecoes do codigo observado seguem normalmente.
  - RNF02: o NLU manda o TEXTO LIVRE do usuario ao LLM, entao por padrao NAO se grava conteudo de mensagens (so numero de
    mensagens, papeis, nomes de tools, tokens). `LANGFUSE_LOG_CONTENT=1` liga o conteudo (so para depuracao local).
    Mensagens de excecao tambem nao vao para o trace (podem conter dados); so o nome da classe.
  - Observacoes aninhadas: dentro de um experimento do Langfuse elas viram filhas do trace do item automaticamente.

Uso:
    with observar("tool.buscar_lugares", "tool", input=args) as obs:
        ...
        obs.update(output={"total": 3})
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

_cliente: Any = None
_inicializado = False
LIMITE = 1500


def _verdadeiro(nome: str, padrao: str = "") -> bool:
    return os.getenv(nome, padrao).strip().lower() in {"1", "true", "sim", "yes"}


def logar_conteudo() -> bool:
    return _verdadeiro("LANGFUSE_LOG_CONTENT")


def configurar(cliente: Any) -> None:
    """Injeta um cliente (ou None para desligar). Usado nos testes e em integracoes."""
    global _cliente, _inicializado
    _cliente, _inicializado = cliente, True


def cliente() -> Any:
    """O cliente Langfuse, ou None se o tracing estiver desligado."""
    global _cliente, _inicializado
    if _inicializado:
        return _cliente
    _inicializado = True
    if "PYTEST_CURRENT_TEST" in os.environ or os.getenv("LANGFUSE_TRACING_ENABLED", "true").strip().lower() == "false":
        return None
    try:
        from dotenv import find_dotenv, load_dotenv  # noqa: PLC0415

        load_dotenv(find_dotenv(usecwd=True))
        load_dotenv(find_dotenv())
    except ImportError:
        pass
    os.environ.setdefault("LANGFUSE_HOST", os.getenv("LANGFUSE_BASE_URL", ""))
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import get_client  # noqa: PLC0415

        _cliente = get_client()
    except Exception:  # noqa: BLE001  (pacote ausente ou configuracao invalida: sem tracing)
        _cliente = None
    return _cliente


def cortar(valor: Any, limite: int = LIMITE) -> Any:
    """Mantem o valor se for pequeno; senao devolve um texto truncado (o trace nao carrega payloads enormes)."""
    if valor is None:
        return None
    try:
        texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        texto = str(valor)
    if len(texto) <= limite:
        return valor if not isinstance(valor, str) else texto
    return texto[:limite] + f"...(+{len(texto) - limite} caracteres)"


class _Nulo:
    def update(self, **_: Any) -> None:
        pass


class _Seguro:
    """Embrulha a observacao do Langfuse: update() nunca levanta."""

    def __init__(self, obs: Any):
        self._obs = obs

    def update(self, **kw: Any) -> None:
        try:
            for k in ("input", "output"):
                if k in kw:
                    kw[k] = cortar(kw[k])
            self._obs.update(**kw)
        except Exception:  # noqa: BLE001
            pass


@contextmanager
def observar(nome: str, tipo: str = "span", *, input: Any = None, metadata: Optional[Dict[str, Any]] = None, **extra: Any) -> Iterator[Any]:
    cli = cliente()
    if cli is None:
        yield _Nulo()
        return
    try:
        cm = cli.start_as_current_observation(name=nome, as_type=tipo, input=cortar(input), metadata=metadata, **extra)
        obs = cm.__enter__()
    except Exception:  # noqa: BLE001
        yield _Nulo()
        return
    try:
        yield _Seguro(obs)
    except BaseException as exc:
        try:
            obs.update(level="ERROR", status_message=type(exc).__name__)  # so a classe: a mensagem pode ter dados
        except Exception:  # noqa: BLE001
            pass
        try:
            cm.__exit__(type(exc), exc, exc.__traceback__)
        except Exception:  # noqa: BLE001
            pass
        raise
    else:
        try:
            cm.__exit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass


def resumo_mensagens(mensagens: Any) -> Dict[str, Any]:
    """O que vai para o trace sobre uma conversa com o LLM: formato, nao conteudo (RNF02)."""
    papeis = [m.get("role") for m in mensagens]
    return {"n_mensagens": len(papeis), "papeis": papeis}


def descarregar() -> None:
    """Envia o que estiver pendente (chamar no fim de scripts de curta duracao)."""
    cli = cliente()
    if cli is not None:
        try:
            cli.flush()
        except Exception:  # noqa: BLE001
            pass
