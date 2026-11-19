"""RetrievalAgent: o agente LLM (DeepSeek) do Retrieval.

O LLM decide a ESTRATEGIA de busca por tool use (regiao, categorias, reformulacao da consulta, o que fazer
com o feedback). O codigo garante o resto:

  - filtros obrigatorios (acessibilidade, ruido, hard_filters, rejeitados) vivem DENTRO das tools;
  - o LLM nunca escreve resultado: `search_response` e `evidence_records` saem do banco e do gate;
  - NADA sai sem o gate (RetrievalGate): se o modelo nunca chamar `validar_candidatos`, o gate audita igual;
  - a decisao final so pode citar lugares de buscas desta execucao (senao o gate recusa);
  - limites: passos de LLM, buscas, reconsultas e tempo total;
  - FALLBACK: qualquer falha (LLM fora do ar, decisao invalida, passos esgotados, gate reprovando ate o fim)
    roda o RetrievalPipeline determinístico, para o agente nunca ficar pior que ele. `fallback=None`
    desliga isso (para medir o agente cru na avaliacao).

Saida (estado) igual a do RetrievalPipeline: search_response, evidence_records, validation_feedback,
retry_count e note (sem texto do usuario). O modelo so ve o `structured_request` (RNF02).
"""

from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from .contracts import StructuredRequest
from .graph import MAX_RETRIES
from .llm_client import LLMClient, extrair_chamadas, mensagem_de_ferramenta, mensagem_para_dict
from .retrieval_common import K_PADRAO
from .retrieval_gate import RetrievalGate, SelecaoInvalida
from .retrieval_pipeline import RetrievalPipeline, _resposta_vazia
from .retrieval_tools import BuscaDesconhecida, ContextoBusca, RetrievalTools
from .state import AgentState
from .validation_tool import EvidenceValidator

_AUTO = object()

SISTEMA = """Voce e o Retrieval do Bubbles. Seu trabalho: achar LUGARES PUBLICOS REAIS do Distrito Federal para um pedido
ja estruturado (JSON abaixo), usando SO as ferramentas. A base e o OpenStreetMap; tudo que voce disser sobre um lugar
tem que vir do que as ferramentas devolveram. Nunca invente lugares, ids, enderecos ou atributos.

FERRAMENTAS
- resolver_regiao(nome): coordenadas de uma regiao/bairro. Use as coordenadas devolvidas (nunca invente coordenadas).
- listar_categorias(): categorias validas da base. O pedido ja traz as categorias; use esta so se precisar de outra.
- buscar_lugares(...): busca por similaridade semantica e distancia. Os filtros de acessibilidade e ruido do pedido sao
  aplicados AUTOMATICAMENTE; nao tente passa-los nem desliga-los (argumentos extras sao recusados).
- validar_candidatos(busca_id): audita uma busca (existencia no OSM, restricoes, integridade). Lugares reprovados e filtros
  sugeridos passam a valer automaticamente nas buscas seguintes.

COMO TRABALHAR
1. Se o pedido tem regiao, chame resolver_regiao. Varios candidatos: escolha o mais plausivel (place=suburb/neighbourhood
   antes de admin_level). Nenhum candidato: nao busque; encerre com busca_escolhida null.
2. Chame buscar_lugares com: as coordenadas da regiao (ou do centro de Brasilia se nao houver regiao), raio_km = o raio do
   pedido, categorias = as do pedido, k = 3 e um texto_consulta curto e concreto (atividade + clima + atributos desejados).
3. Olhe o resultado: se `raio_ampliado` for true, a busca ampliou o raio sozinha (ate 2x) e parte dos resultados esta
   alem do raio pedido; prefira escolher so os que estao dentro do raio ou diga isso no motivo. Se os resultados forem
   fracos para o que foi pedido, reformule o texto_consulta ou ajuste as categorias (so categorias validas) e busque de
   novo. Voce tem poucas buscas: nao repita a mesma.
4. Chame validar_candidatos na busca que pretende escolher. Se houver reprovados, busque de novo.
5. Encerre com UMA mensagem so de JSON (sem texto fora dele):
   {"busca_escolhida": "B2", "place_ids": ["123", "456", "789"], "motivo": "frase curta"}
   - "place_ids" (opcional) escolhe um subconjunto ORDENADO (no maximo 3) da busca, so ids que voce viu.
   - Sem resultado bom: {"busca_escolhida": null, "motivo": "frase curta"}.

REGRAS
- Voce nao decide se um lugar pode ser entregue: o gate de auditoria decide depois da sua escolha.
- Nao copie nem peca dados pessoais. Responda em portugues."""

# v2: manda conferir os campos que a tool devolve ANTES de escolher. Escrito depois de ver as falhas do v1 nos casos
# de avaliacao (TC-13: cozinha errada; TC-15: horario), entao os resultados dele no mesmo dataset sao otimistas.
CONFERENCIA_V2 = """
CONFERENCIA ANTES DE ESCOLHER (obrigatoria)
- Para cada candidato, confira o que a ferramenta devolveu: `tags.opening_hours` contra o horario e o dia pedidos;
  `tags.cuisine` e o `nome` contra a culinaria ou o tipo de lugar pedido (ex.: pedido de sushi nao aceita cozinha indiana);
  `distancia_km` contra o raio do pedido.
- Descarte quem contradiz o pedido COM EVIDENCIA nesses campos. Campo ausente NAO e motivo para descartar.
- Prefira entregar menos lugares (use place_ids) a entregar um que contradiz o pedido."""

PROMPTS = {"v1": SISTEMA, "v2": SISTEMA + CONFERENCIA_V2}

FORMATO_FINAL = (
    'Responda agora SO com o JSON final: {"busca_escolhida": "B1" ou null, "place_ids": ["..."] (opcional), "motivo": "..."}.'
)


class AgenteSemDecisao(Exception):
    """O agente nao chegou a uma decisao valida (passos esgotados, resposta final invalida...)."""


class GateReprovouTudo(Exception):
    """O gate reprovou as escolhas do agente ate esgotar as reconsultas."""

    def __init__(self, saida: Dict[str, Any]):
        super().__init__("gate reprovou ate esgotar as reconsultas")
        self.saida = saida


def _ler_decisao(texto: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extrai o JSON da decisao final. Tolera texto em volta; None se nao houver JSON utilizavel."""
    if not texto or "{" not in texto:
        return None
    try:
        d = json.loads(texto[texto.index("{"): texto.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(d, dict) or "busca_escolhida" not in d:
        return None
    b = d["busca_escolhida"]
    if b is not None and not isinstance(b, str):
        return None
    ids = d.get("place_ids")
    if ids is not None and not (isinstance(ids, list) and all(isinstance(i, (str, int)) for i in ids)):
        return None
    return d


class RetrievalAgent:
    """Callable `AgentState -> dict`, injetavel em `build_graph`."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        conexao_factory: Optional[Callable[[], Any]] = None,
        embedder: Optional[Callable[[str], List[float]]] = None,
        buscar_fn: Optional[Callable[..., dict]] = None,
        regioes_fn: Optional[Callable[..., list]] = None,
        validator: Optional[EvidenceValidator] = None,
        fallback: Any = _AUTO,
        k: int = K_PADRAO,
        max_passos: int = 6,
        max_buscas: int = 4,
        max_retries: int = MAX_RETRIES,
        timeout_s: float = 60.0,
        max_tokens: int = 1500,
        prompt: str = "v1",
        relogio: Callable[[], float] = time.monotonic,
    ):
        if prompt not in PROMPTS:
            raise ValueError(f"prompt desconhecido: {prompt!r}; use {sorted(PROMPTS)}")
        self.prompt = prompt
        self._llm = llm
        self._colab = dict(conexao_factory=conexao_factory, embedder=embedder, buscar_fn=buscar_fn, regioes_fn=regioes_fn)
        self._validator = validator
        self.k, self.max_passos, self.max_buscas = k, max_passos, max_buscas
        self.max_retries, self.timeout_s, self.max_tokens, self._relogio = max_retries, timeout_s, max_tokens, relogio
        if fallback is _AUTO:  # padrao: o pipeline determinístico com os mesmos colaboradores
            fallback = RetrievalPipeline(validator=validator, k=k, max_retries=max_retries, **self._colab)
        self.fallback = fallback

    # ------------------------------------------------------------------ entrada
    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _validador(self) -> EvidenceValidator:
        if self._validator is None:
            from .evidence_store import PostgresEvidenceStore  # noqa: PLC0415

            self._validator = EvidenceValidator(store=PostgresEvidenceStore(conexao_factory=self._colab["conexao_factory"]))
        return self._validator

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        req = state.get("structured_request")
        if req is None:
            raise ValueError("retrieval: structured_request ausente no estado")
        try:
            return self._agir(state, req)
        except GateReprovouTudo as e:
            if self.fallback is None:
                return e.saida
            motivo = "gate reprovou ate esgotar as reconsultas"
        except Exception as e:  # noqa: BLE001  (qualquer falha do caminho LLM cai no pipeline)
            if self.fallback is None:
                raise
            motivo = type(e).__name__
        saida = self.fallback(state)
        saida["note"] = f"FALLBACK para o pipeline ({motivo}); " + saida.get("note", "")
        return saida

    # ------------------------------------------------------------------ o loop do agente
    def _agir(self, state: AgentState, req: StructuredRequest) -> Dict[str, Any]:
        validator = self._validador()
        contexto = ContextoBusca.de_pedido(req, state.get("validation_feedback"), self.k)
        tools = RetrievalTools(contexto, state["request_id"], req=req, validator=validator, max_buscas=self.max_buscas, **self._colab)
        gate = RetrievalGate(validator)
        llm = self.llm
        uso0 = llm.uso.como_dict()
        prazo = self._relogio() + self.timeout_s

        pedido = req.model_dump(exclude={"raw_query"})
        mensagens: List[Dict[str, Any]] = [
            {"role": "system", "content": PROMPTS[self.prompt]},
            {"role": "user", "content": "Pedido estruturado (k final = %d): %s" % (self.k, json.dumps(pedido, ensure_ascii=False))},
        ]
        usadas: Counter = Counter()
        regiao_vazia, rejeicoes, invalidas = False, 0, 0

        for passo in range(1, self.max_passos + 1):
            msg = llm.chat(mensagens, tools=tools.schemas(), tool_choice="auto", max_tokens=self.max_tokens, prazo=prazo)
            mensagens.append(mensagem_para_dict(msg))
            chamadas = extrair_chamadas(msg)
            if chamadas:
                for c in chamadas:
                    res = tools.executar(c.nome, c.argumentos)
                    usadas[c.nome] += 1
                    if c.nome == "resolver_regiao" and res.get("regioes") == []:
                        regiao_vazia = True
                    mensagens.append(mensagem_de_ferramenta(c.id, res))
                continue

            decisao = _ler_decisao(msg.content)
            if decisao is None:
                invalidas += 1
                if invalidas > 1:
                    raise AgenteSemDecisao("resposta final sem JSON valido")
                mensagens.append({"role": "user", "content": FORMATO_FINAL})
                continue

            if decisao["busca_escolhida"] is None:
                return self._sem_escolha(state, req, regiao_vazia, usadas, passo, llm, uso0)

            try:
                busca = tools.runlog.obter(decisao["busca_escolhida"])
                resultado = gate.auditar(req, busca, decisao.get("place_ids"))
            except (BuscaDesconhecida, SelecaoInvalida) as e:
                invalidas += 1
                if invalidas > 2:
                    raise AgenteSemDecisao("decisao final recusada repetidamente") from None
                mensagens.append({"role": "user", "content": f"Decisao recusada ({type(e).__name__}: {e}). Escolha uma busca "
                                  "do seu historico e so lugares dela, ou use busca_escolhida null."})
                continue

            if resultado.aprovado:
                return {
                    "search_response": resultado.search_response,
                    "validation_feedback": resultado.feedback,
                    "evidence_records": resultado.evidence_records,
                    "retry_count": rejeicoes,
                    "note": self._nota(f"{len(resultado.evidence_records)} aprovado(s)", usadas, passo, rejeicoes, llm, uso0, busca.consulta_id),
                }

            rejeicoes += 1
            contexto.aplicar_feedback(resultado.feedback)  # rejeitados + hard_filters valem na proxima busca
            if rejeicoes > self.max_retries:
                raise GateReprovouTudo({
                    "search_response": busca.search_response,
                    "validation_feedback": resultado.feedback,
                    "retry_count": self.max_retries,
                    "note": self._nota("reprovado pelo gate; reconsultas esgotadas", usadas, passo, self.max_retries, llm, uso0, busca.consulta_id),
                })
            mensagens.append({"role": "user", "content": (
                "O GATE REPROVOU sua escolha. Diagnostico: " + "; ".join(resultado.feedback.diagnostics[:4])
                + f". Reprovados (nao voltam): {resultado.feedback.rejected_place_ids}. Filtros novos: "
                f"{resultado.feedback.hard_filters}. Faca nova busca e decida de novo (reconsulta {rejeicoes}/{self.max_retries}).")})

        raise AgenteSemDecisao("passos esgotados")

    # ------------------------------------------------------------------ desfechos
    def _sem_escolha(self, state, req, regiao_vazia, usadas, passo, llm, uso0) -> Dict[str, Any]:
        if regiao_vazia and req.spatial_constraints.target_region:
            return RetrievalPipeline._pedir_esclarecimento(state, req, req.spatial_constraints.target_region) | {
                "note": self._nota("regiao nao encontrada: pedindo esclarecimento", usadas, passo, 0, llm, uso0, None)}
        return {
            "search_response": _resposta_vazia(req, state["request_id"], list(req.target_amenities)),
            "retry_count": 0,
            "note": self._nota("o agente nao encontrou resultado adequado", usadas, passo, 0, llm, uso0, None),
        }

    @staticmethod
    def _nota(resumo: str, usadas: Counter, passo: int, reconsultas: int, llm: LLMClient, uso0: Dict[str, int], consulta_id) -> str:
        u = llm.uso.como_dict()
        d = {k: u[k] - uso0[k] for k in u}
        tools = ",".join(f"{n}x{c}" for n, c in sorted(usadas.items())) or "nenhuma"
        return (f"agente llm: {resumo}; passos={passo}; tools={tools}; reconsultas={reconsultas}; "
                f"tokens={d['prompt_tokens']}/{d['completion_tokens']}/{d['reasoning_tokens']}; consulta_id={consulta_id}")


_default_agent: Optional[RetrievalAgent] = None


def retrieval_agent(state: AgentState) -> Dict[str, Any]:
    """Funcao pronta para `build_graph` (DeepSeek do .env, PostgreSQL, fallback para o pipeline)."""
    global _default_agent
    if _default_agent is None:
        _default_agent = RetrievalAgent()
    return _default_agent(state)
