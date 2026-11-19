"""Cliente LLM fino (DeepSeek via SDK `openai`) com retry. Compartilhado pelos agentes que usam LLM.

Configuracao (variaveis de ambiente; o .env e carregado automaticamente):
  DEEPSEEK_API_KEY   obrigatoria
  DEEPSEEK_MODEL     padrao "deepseek-chat" (os nomes mudam; confirme no painel do provedor)
  DEEPSEEK_BASE_URL  padrao "https://api.deepseek.com"

Erros transitorios (429, 5xx, rede, resposta JSON vazia) sao repetidos com espera crescente.
Erros definitivos (400, 401, 402, 422...) falham na hora. A chave nunca entra em mensagens de erro.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional

RETRYAVEL = {408, 409, 429, 500, 502, 503, 504}
MODELO_PADRAO = "deepseek-chat"
BASE_URL_PADRAO = "https://api.deepseek.com"


class LLMError(Exception):
    """Falha ao obter resposta do LLM (sem dados do usuario na mensagem)."""


def _status(exc: BaseException) -> Optional[int]:
    return getattr(exc, "status_code", None)


def _de_rede(exc: BaseException) -> bool:
    return type(exc).__name__ in {"APIConnectionError", "APITimeoutError", "TimeoutError", "ConnectionError"}


class LLMClient:
    def __init__(
        self,
        client: Any = None,
        model: Optional[str] = None,
        max_tentativas: int = 4,
        timeout: float = 90.0,
        espera_base: float = 1.5,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if client is None:
            try:
                from dotenv import load_dotenv, find_dotenv  # noqa: PLC0415

                load_dotenv(find_dotenv(usecwd=True))
                load_dotenv(find_dotenv())
            except ImportError:
                pass
            chave = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
            if not chave:
                raise LLMError("DEEPSEEK_API_KEY nao definida (coloque no .env da raiz do projeto).")
            from openai import OpenAI  # noqa: PLC0415

            client = OpenAI(
                api_key=chave,
                base_url=os.getenv("DEEPSEEK_BASE_URL", BASE_URL_PADRAO),
                timeout=timeout,
                max_retries=0,  # o retry e nosso
            )
        self._client = client
        self.model = model or os.getenv("DEEPSEEK_MODEL", MODELO_PADRAO)
        self.max_tentativas = max_tentativas
        self.espera_base = espera_base
        self._sleep = sleep
        self.chamadas = 0  # quantas requisicoes foram feitas (inclui retries)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        json_mode: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ):
        """Devolve a mensagem do assistente (`.content`, `.tool_calls`). Levanta LLMError."""
        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        ultimo = "sem tentativas"
        for tentativa in range(1, self.max_tentativas + 1):
            self.chamadas += 1
            try:
                resp = self._client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 (classificamos abaixo)
                status = _status(exc)
                if status in RETRYAVEL or (status is None and _de_rede(exc)):
                    ultimo = f"erro transitorio ({status or type(exc).__name__})"
                else:
                    raise LLMError(f"erro do provedor ({status or type(exc).__name__}); sem retry") from None
            else:
                msg = resp.choices[0].message
                if json_mode and not (msg.content or "").strip():
                    # DeepSeek devolve so espacos quando nao consegue produzir JSON valido.
                    ultimo = "resposta JSON vazia"
                else:
                    return msg
            if tentativa < self.max_tentativas:
                self._sleep(self.espera_base * 2 ** (tentativa - 1))
        raise LLMError(f"LLM indisponivel apos {self.max_tentativas} tentativas: {ultimo}")
