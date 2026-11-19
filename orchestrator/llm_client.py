"""Cliente LLM fino (DeepSeek via SDK `openai`): retry, tool calling, thinking, strict e contagem de tokens.

Compartilhado pelos agentes que usam LLM (NLU hoje; Retrieval na Fase D).

Configuracao (variaveis de ambiente; os .env da arvore sao carregados automaticamente):
  DEEPSEEK_API_KEY           obrigatoria
  DEEPSEEK_MODEL             padrao "deepseek-flash" (a chave atual enxerga "deepseek-flash" e "deepseek-v4-pro";
                             "deepseek-chat" e nome legado). Os nomes mudam: confirme com `scripts/diagnostico_llm.py`
  DEEPSEEK_BASE_URL          padrao "https://api.deepseek.com"
  DEEPSEEK_REASONING_EFFORT  none | low | high | max. Padrao `none` (thinking desligado). Com thinking, o dobro de
                             tokens de saida e mais latencia (ver docs/diagnostico_llm_deepseek.md)
  DEEPSEEK_STRICT            1 = usa o endpoint /beta (strict function calling: o modelo segue o JSON Schema)

Erros transitorios (429, 5xx, rede, resposta JSON vazia, `aborted`) sao repetidos com espera crescente.
Erros definitivos (400, 401, 402, 422, resposta truncada...) falham na hora. A chave nunca entra em mensagens
de erro. `prazo` (relogio monotonico) limita o tempo total de uma chamada, retries incluidos: cada requisicao recebe
o timeout `min(timeout, tempo restante)`, entao uma resposta lenta nao passa do prazo.

Thinking + tools: a API EXIGE devolver o `reasoning_content` em todas as requisicoes seguintes (senao 400).
`mensagem_para_dict` preserva esse campo; use-a para montar o historico.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

RETRYAVEL = {408, 409, 429, 500, 502, 503, 504}
FINISH_TRANSITORIO = {"insufficient_system_resource", "aborted"}
MODELO_PADRAO = "deepseek-flash"
ESFORCO_PADRAO = "none"  # thinking desligado: mais rapido e barato (nos modelos novos ele vem LIGADO por padrao)
BASE_URL_PADRAO = "https://api.deepseek.com"
ESFORCOS = {"none", "low", "high", "max"}


class LLMError(Exception):
    """Falha ao obter resposta do LLM (sem dados do usuario na mensagem)."""


@dataclass
class Uso:
    """Tokens acumulados de um cliente (para custo e para o Langfuse)."""

    chamadas: int = 0  # requisicoes feitas (inclui retries)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    reasoning_tokens: int = 0

    def somar(self, usage: Any) -> None:
        if usage is None:
            return
        g = lambda o, k: int(getattr(o, k, 0) or 0)  # noqa: E731
        self.prompt_tokens += g(usage, "prompt_tokens")
        self.completion_tokens += g(usage, "completion_tokens")
        self.cache_hit_tokens += g(usage, "prompt_cache_hit_tokens")
        self.cache_miss_tokens += g(usage, "prompt_cache_miss_tokens")
        det = getattr(usage, "completion_tokens_details", None)
        self.reasoning_tokens += g(det, "reasoning_tokens") if det is not None else 0

    def como_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: str  # JSON em texto, como veio do modelo (pode estar invalido: quem executa trata)


# --------------------------------------------------------------------------
# Historico de mensagens com tool calling
# --------------------------------------------------------------------------
def extrair_chamadas(msg: Any) -> List[ChamadaFerramenta]:
    """Chamadas de ferramenta pedidas pelo modelo nesta mensagem (lista vazia se nao houver)."""
    out = []
    for c in getattr(msg, "tool_calls", None) or []:
        f = c.function
        out.append(ChamadaFerramenta(id=c.id, nome=f.name, argumentos=f.arguments or ""))
    return out


def mensagem_para_dict(msg: Any) -> Dict[str, Any]:
    """Mensagem do assistente em formato de historico. Preserva tool_calls e `reasoning_content`
    (obrigatorio devolver no modo thinking com tools)."""
    d: Dict[str, Any] = {"role": "assistant", "content": getattr(msg, "content", None)}
    chamadas = extrair_chamadas(msg)
    if chamadas:
        d["tool_calls"] = [
            {"id": c.id, "type": "function", "function": {"name": c.nome, "arguments": c.argumentos}} for c in chamadas
        ]
    raciocinio = getattr(msg, "reasoning_content", None)
    if raciocinio is not None:
        d["reasoning_content"] = raciocinio
    return d


def mensagem_de_ferramenta(chamada_id: str, resultado: Any) -> Dict[str, Any]:
    """Resposta de uma tool ao modelo (o conteudo precisa ser texto)."""
    conteudo = resultado if isinstance(resultado, str) else json.dumps(resultado, ensure_ascii=False)
    return {"role": "tool", "tool_call_id": chamada_id, "content": conteudo}


def _status(exc: BaseException) -> Optional[int]:
    return getattr(exc, "status_code", None)


def _de_rede(exc: BaseException) -> bool:
    return type(exc).__name__ in {"APIConnectionError", "APITimeoutError", "TimeoutError", "ConnectionError"}


def _base_url(base: str, strict: bool) -> str:
    base = base.rstrip("/")
    if strict and not base.endswith("/beta"):
        return base + "/beta"
    return base


class LLMClient:
    def __init__(
        self,
        client: Any = None,
        model: Optional[str] = None,
        max_tentativas: int = 4,
        timeout: float = 90.0,
        espera_base: float = 1.5,
        sleep: Callable[[float], None] = time.sleep,
        reasoning_effort: Optional[str] = None,
        strict: Optional[bool] = None,
        relogio: Callable[[], float] = time.monotonic,
    ):
        if client is None:
            try:
                from dotenv import find_dotenv, load_dotenv  # noqa: PLC0415

                load_dotenv(find_dotenv(usecwd=True))
                load_dotenv(find_dotenv())
            except ImportError:
                pass
            chave = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
            if not chave:
                raise LLMError("DEEPSEEK_API_KEY nao definida (coloque no .env da raiz do projeto).")
            if strict is None:
                strict = os.getenv("DEEPSEEK_STRICT", "").strip().lower() in {"1", "true", "sim"}
            from openai import OpenAI  # noqa: PLC0415

            client = OpenAI(
                api_key=chave,
                base_url=_base_url(os.getenv("DEEPSEEK_BASE_URL", BASE_URL_PADRAO), bool(strict)),
                timeout=timeout,
                max_retries=0,  # o retry e nosso
            )
        if reasoning_effort is None:
            reasoning_effort = (os.getenv("DEEPSEEK_REASONING_EFFORT") or "").strip().lower() or ESFORCO_PADRAO
        if reasoning_effort is not None and reasoning_effort not in ESFORCOS:
            raise LLMError(f"reasoning_effort invalido: {reasoning_effort!r}; use {sorted(ESFORCOS)}")
        self._client = client
        self.timeout = timeout
        self.model = model or os.getenv("DEEPSEEK_MODEL", MODELO_PADRAO)
        self.reasoning_effort = reasoning_effort
        self.max_tentativas = max_tentativas
        self.espera_base = espera_base
        self._sleep = sleep
        self._relogio = relogio
        self.uso = Uso()

    @property
    def chamadas(self) -> int:
        return self.uso.chamadas

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        json_mode: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Any = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        prazo: Optional[float] = None,
    ):
        """Devolve a mensagem do assistente (`.content`, `.tool_calls`, `.reasoning_content`). Levanta LLMError.

        `prazo`: instante limite no relogio monotonico (`time.monotonic() + segundos`), retries incluidos.
        """
        esforco = reasoning_effort if reasoning_effort is not None else self.reasoning_effort
        if esforco is not None and esforco not in ESFORCOS:
            raise LLMError(f"reasoning_effort invalido: {esforco!r}; use {sorted(ESFORCOS)}")
        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if esforco is not None:
            kwargs["reasoning_effort"] = esforco

        ultimo = "sem tentativas"
        for tentativa in range(1, self.max_tentativas + 1):
            if prazo is not None and self._relogio() >= prazo:
                raise LLMError(f"tempo total excedido antes da tentativa {tentativa}: {ultimo}")
            self.uso.chamadas += 1
            if prazo is not None:  # uma requisicao lenta tambem nao pode estourar o prazo total
                kwargs["timeout"] = max(1.0, min(self.timeout, prazo - self._relogio()))
            try:
                resp = self._client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 (classificamos abaixo)
                status = _status(exc)
                if status in RETRYAVEL or (status is None and _de_rede(exc)):
                    ultimo = f"erro transitorio ({status or type(exc).__name__})"
                else:
                    raise LLMError(f"erro do provedor ({status or type(exc).__name__}); sem retry") from None
            else:
                self.uso.somar(getattr(resp, "usage", None))
                escolha = resp.choices[0]
                motivo = getattr(escolha, "finish_reason", None) or "stop"
                msg = escolha.message
                if motivo == "length":
                    raise LLMError("resposta truncada por limite de tokens (finish_reason=length); aumente max_tokens")
                if motivo == "content_filter":
                    raise LLMError("resposta bloqueada pelo filtro de conteudo do provedor")
                if motivo in FINISH_TRANSITORIO:
                    ultimo = f"geracao interrompida ({motivo})"
                elif json_mode and not (msg.content or "").strip():
                    # DeepSeek devolve so espacos quando nao consegue produzir JSON valido.
                    ultimo = "resposta JSON vazia"
                else:
                    return msg
            if tentativa < self.max_tentativas:
                espera = self.espera_base * 2 ** (tentativa - 1)
                if prazo is not None:
                    espera = max(0.0, min(espera, prazo - self._relogio()))
                self._sleep(espera)
        raise LLMError(f"LLM indisponivel apos {self.max_tentativas} tentativas: {ultimo}")

    def listar_modelos(self) -> List[str]:
        """Modelos que a chave enxerga (diagnostico)."""
        try:
            return [m.id for m in self._client.models.list().data]
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"nao foi possivel listar modelos ({_status(exc) or type(exc).__name__})") from None
