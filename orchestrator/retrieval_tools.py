"""Tools de busca do Retrieval: o que um agente LLM pode chamar (e so isso).

Quatro tools, todas deterministicas e sem LLM:
  resolver_regiao(nome)       -> candidatos da tabela `regioes`
  listar_categorias()         -> valores reais de places.categoria
  buscar_lugares(...)         -> top-k real (busca.buscar), com filtros obrigatorios
  validar_candidatos(busca_id)-> audita uma busca ja feita (EvidenceValidator): RNF01, restricoes, matematica

GARANTIAS (nao dependem do prompt nem do que o LLM mandar):
  - Filtros obrigatorios (wheelchair, tolerancia de ruido, hard_filters do validador, lugares ja
    rejeitados) sao aplicados DENTRO de `buscar_lugares`. Nao ha argumento para desliga-los.
  - Argumentos fora do schema, categorias inexistentes, raio acima do limite e k absurdo sao
    recusados ou limitados, e o resultado diz o que foi ajustado.
  - Toda busca recebe um `busca_id` e fica no `RunLog`. Um place_id so e valido se aparecer num
    resultado desta execucao.
  - Resultados voltam como dicts JSON puros (sem vetores, sem texto do usuario).

Erros de USO (argumento invalido, limite de buscas) voltam como {"erro": ...} para o LLM corrigir.
Falhas de INFRA (banco fora do ar) sobem como excecao: o chamador decide (fallback/abstencao).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .contracts import SearchItem, SearchResponse, StructuredRequest, ValidationFeedback
from .retrieval_common import K_PADRAO, _pipeline, montar_parametros, registro_para_search_response
from .validation_tool import EvidenceValidator

MAX_BUSCAS = 4
K_MAXIMO = 10
FATOR_RAIO_MAXIMO = 2.0  # raio final maximo = 2x o pedido (a ampliacao automatica da busca dobra o raio)
MAX_TEXTO = 300
MAX_REGIOES = 5
# Tags do OSM que valem mostrar ao LLM para ele julgar o resultado.
TAGS_VISIVEIS = ("wheelchair", "noise_level", "opening_hours", "cuisine", "outdoor_seating", "internet_access")


_MODELO = None  # sentence-transformers, carregado na primeira busca real


def aquecer_modelo() -> None:
    """Carrega o modelo de embeddings padrao agora (ex.: antes de cronometrar um experimento)."""
    global _MODELO
    emb = _pipeline()[1]
    if _MODELO is None:
        _MODELO = emb.carregar_modelo()
    emb.gerar_embedding_consulta("aquecimento", _MODELO)


class ErroDeUso(Exception):
    """O LLM chamou a tool de forma invalida; a mensagem volta para ele corrigir."""


# --------------------------------------------------------------------------
# Filtros obrigatorios
# --------------------------------------------------------------------------
@dataclass
class ContextoBusca:
    """Tudo que o LLM NAO pode alterar numa busca, derivado do pedido e do feedback do validador."""

    etiquetas: Dict[str, str]  # ex.: {"wheelchair": "yes"}
    tolerancia_sensorial: str  # baixo | moderado | indiferente
    tipos_do_pedido: List[str]
    raio_pedido_km: float
    k_final: int = K_PADRAO
    rejeitados: Set[str] = field(default_factory=set)

    @classmethod
    def de_pedido(
        cls,
        req: StructuredRequest,
        feedback: Optional[ValidationFeedback] = None,
        k: int = K_PADRAO,
    ) -> "ContextoBusca":
        p = montar_parametros(req, feedback, k)
        return cls(
            etiquetas=dict(p["etiquetas_desejadas"]),
            tolerancia_sensorial=p["tolerancia_sensorial"],
            tipos_do_pedido=list(p["tipos"] or []),
            raio_pedido_km=req.spatial_constraints.max_radius_km,
            k_final=k,
            rejeitados={str(r) for r in p["rejeitados"]},
        )

    def aplicar_feedback(self, feedback: ValidationFeedback) -> None:
        """Endurece o contexto com o que o validador reprovou. So acumula, nunca afrouxa."""
        self.rejeitados |= {str(r) for r in feedback.rejected_place_ids}
        if feedback.hard_filters.get("wheelchair") == "yes":
            self.etiquetas["wheelchair"] = "yes"
        pedido = feedback.hard_filters.get("noise_level")
        if pedido in ("baixo", "moderado") and (
            self.tolerancia_sensorial == "indiferente" or pedido == "baixo"
        ):
            self.tolerancia_sensorial = pedido


# --------------------------------------------------------------------------
# Registro das buscas da execucao
# --------------------------------------------------------------------------
@dataclass
class BuscaRegistrada:
    busca_id: str
    consulta_id: Optional[str]
    search_response: Dict[str, Any]  # dict do Contrato 3, montado em codigo a partir do banco


class BuscaDesconhecida(KeyError):
    pass


class RunLog:
    """Memoria das buscas desta execucao: a unica fonte de candidatos validos."""

    def __init__(self):
        self._buscas: Dict[str, BuscaRegistrada] = {}

    def registrar(self, consulta_id: Optional[str], search_response: Dict[str, Any]) -> BuscaRegistrada:
        busca = BuscaRegistrada(f"B{len(self._buscas) + 1}", consulta_id, search_response)
        self._buscas[busca.busca_id] = busca
        return busca

    def obter(self, busca_id: str) -> BuscaRegistrada:
        try:
            return self._buscas[busca_id]
        except KeyError:
            raise BuscaDesconhecida(busca_id) from None

    @property
    def total(self) -> int:
        return len(self._buscas)

    def place_ids(self) -> Set[str]:
        return {i["place_id"] for b in self._buscas.values() for i in b.search_response["items"]}

    def contem_lugar(self, place_id: str, busca_id: Optional[str] = None) -> bool:
        buscas = [self.obter(busca_id)] if busca_id else self._buscas.values()
        return any(i["place_id"] == str(place_id) for b in buscas for i in b.search_response["items"])


# --------------------------------------------------------------------------
# Schemas (formato OpenAI/DeepSeek). Compativeis com `strict`: todas as propriedades obrigatorias
# e additionalProperties=false.
# --------------------------------------------------------------------------
def _tool(nome: str, descricao: str, propriedades: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": propriedades,
                "required": list(propriedades),
                "additionalProperties": False,
            },
        },
    }


SCHEMAS: List[Dict[str, Any]] = [
    _tool(
        "resolver_regiao",
        "Procura regioes do Distrito Federal (RA, bairro, quadra) pelo nome e devolve ate 5 candidatos com "
        "coordenadas, do mais especifico ao menos. Use antes de buscar_lugares quando o pedido cita uma regiao.",
        {"nome": {"type": "string", "description": "Nome da regiao, ex.: 'Asa Sul'."}},
    ),
    _tool(
        "listar_categorias",
        "Lista as categorias de lugar existentes na base (valor exato a usar em `categorias`) com a quantidade.",
        {},
    ),
    _tool(
        "buscar_lugares",
        "Busca lugares reais da base por similaridade semantica e distancia. Os filtros de acessibilidade e "
        "ruido do pedido sao aplicados automaticamente e nao podem ser alterados. Devolve um busca_id.",
        {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "raio_km": {"type": "number", "description": "Raio em km (no maximo o do pedido; a busca amplia sozinha ate 2x se faltar resultado)."},
            "categorias": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Categorias exatas de listar_categorias. Vazio = as do pedido.",
            },
            "texto_consulta": {
                "type": "string",
                "description": "Frase curta descrevendo o lugar ideal; vira o embedding da busca.",
            },
            "k": {"type": "integer", "description": f"Quantos resultados (1 a {K_MAXIMO})."},
        },
    ),
    _tool(
        "validar_candidatos",
        "Audita os candidatos de uma busca ja feita (busca_id de buscar_lugares): existencia no OpenStreetMap, "
        "restricoes do pedido (acessibilidade, ruido, horario) e integridade do score. Os lugares reprovados e "
        "os filtros sugeridos passam a valer AUTOMATICAMENTE nas proximas buscas. So audita o que veio do banco.",
        {"busca_id": {"type": "string", "description": "Id devolvido por buscar_lugares, ex.: 'B1'."}},
    ),
]


# --------------------------------------------------------------------------
# As tools
# --------------------------------------------------------------------------
class RetrievalTools:
    """Executa as tools de busca para UMA execucao do agente (contexto + RunLog proprios).

    Colaboradores injetaveis (testes sem banco):
      conexao_factory: () -> context manager de conexao (padrao: busca.conectar)
      embedder:        (texto) -> list[float] de 768 dims (padrao: gerar_embedding_consulta)
      buscar_fn:       busca.buscar
      regioes_fn:      regioes.buscar_regioes
    """

    def __init__(
        self,
        contexto: ContextoBusca,
        request_id: str,
        runlog: Optional[RunLog] = None,
        conexao_factory: Optional[Callable[[], Any]] = None,
        embedder: Optional[Callable[[str], List[float]]] = None,
        buscar_fn: Optional[Callable[..., dict]] = None,
        regioes_fn: Optional[Callable[..., list]] = None,
        max_buscas: int = MAX_BUSCAS,
        req: Optional[StructuredRequest] = None,
        validator: Optional[EvidenceValidator] = None,
    ):
        self.contexto = contexto
        self.request_id = request_id
        self.req = req
        self.validator = validator
        self.runlog = runlog or RunLog()
        self.max_buscas = max_buscas
        self._conexao_factory = conexao_factory
        self._embedder = embedder
        self._buscar_fn = buscar_fn
        self._regioes_fn = regioes_fn
        self._categorias: Optional[List[Dict[str, Any]]] = None

    # -- colaboradores padrao, carregados so quando precisam -----------------------------
    def _conexao(self):
        if self._conexao_factory is None:
            self._conexao_factory = _pipeline()[0].conectar
        return self._conexao_factory()

    def _embed(self, texto: str) -> List[float]:
        if self._embedder is None:
            emb = _pipeline()[1]

            def embedder(t: str) -> List[float]:
                global _MODELO
                if _MODELO is None:  # um so modelo por processo, compartilhado entre execucoes
                    _MODELO = emb.carregar_modelo()
                return emb.gerar_embedding_consulta(t, _MODELO)

            self._embedder = embedder
        return self._embedder(texto)

    # -- despacho ------------------------------------------------------------------------
    def schemas(self) -> List[Dict[str, Any]]:
        """Schemas das tools disponiveis nesta execucao (validar_candidatos exige req e validator)."""
        if self.validator is not None and self.req is not None:
            return SCHEMAS
        return [s for s in SCHEMAS if s["function"]["name"] != "validar_candidatos"]

    def executar(self, nome: str, argumentos: Any) -> Dict[str, Any]:
        """Executa uma tool. Erros de uso viram {"erro": ...}; falha de infra sobe."""
        try:
            if nome not in self._TOOLS:
                raise ErroDeUso(f"tool desconhecida: '{nome}'. Disponiveis: {sorted(self._TOOLS)}")
            if argumentos is None:
                argumentos = {}
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos) if argumentos.strip() else {}
                except json.JSONDecodeError:
                    raise ErroDeUso("argumentos nao sao um JSON valido") from None
            if not isinstance(argumentos, dict):
                raise ErroDeUso("argumentos devem ser um objeto JSON")
            return getattr(self, self._TOOLS[nome])(**self._validar_chaves(nome, argumentos))
        except ErroDeUso as erro:
            return {"erro": str(erro)}

    _TOOLS = {
        "resolver_regiao": "resolver_regiao",
        "listar_categorias": "listar_categorias",
        "buscar_lugares": "buscar_lugares",
        "validar_candidatos": "validar_candidatos",
    }

    @staticmethod
    def _validar_chaves(nome: str, argumentos: Dict[str, Any]) -> Dict[str, Any]:
        esquema = next(s for s in SCHEMAS if s["function"]["name"] == nome)["function"]["parameters"]
        permitidas = set(esquema["properties"])
        extras = sorted(set(argumentos) - permitidas)
        if extras:
            raise ErroDeUso(
                f"argumentos nao permitidos: {extras}. Esta tool aceita apenas {sorted(permitidas)}; "
                "filtros de acessibilidade e ruido sao aplicados automaticamente."
            )
        faltando = sorted(permitidas - set(argumentos))
        if faltando:
            raise ErroDeUso(f"argumentos obrigatorios ausentes: {faltando}")
        return argumentos

    # -- tool 1 --------------------------------------------------------------------------
    def resolver_regiao(self, nome: str) -> Dict[str, Any]:
        if not isinstance(nome, str) or not nome.strip():
            raise ErroDeUso("`nome` deve ser um texto nao vazio")
        if self._regioes_fn is None:
            self._regioes_fn = _pipeline()[2].buscar_regioes
        with self._conexao() as conexao:
            regioes = self._regioes_fn(conexao, nome[:MAX_TEXTO], MAX_REGIOES)
        return {
            "regioes": [
                {"nome": r["nome"], "tipo": r["tipo"], "latitude": r["latitude"], "longitude": r["longitude"]}
                for r in regioes[:MAX_REGIOES]
            ]
        }

    # -- tool 2 --------------------------------------------------------------------------
    def _categorias_da_base(self) -> List[Dict[str, Any]]:
        if self._categorias is None:
            with self._conexao() as conexao:
                linhas = conexao.execute(
                    "SELECT categoria, count(*) FROM places WHERE categoria IS NOT NULL "
                    "GROUP BY categoria ORDER BY count(*) DESC, categoria"
                ).fetchall()
            self._categorias = [{"categoria": c, "quantidade": int(n)} for c, n in linhas]
        return self._categorias

    def listar_categorias(self) -> Dict[str, Any]:
        return {"categorias": self._categorias_da_base()}

    # -- tool 3 --------------------------------------------------------------------------
    def buscar_lugares(
        self,
        latitude: float,
        longitude: float,
        raio_km: float,
        categorias: List[str],
        texto_consulta: str,
        k: int,
    ) -> Dict[str, Any]:
        ctx = self.contexto
        if self.runlog.total >= self.max_buscas:
            raise ErroDeUso(f"limite de {self.max_buscas} buscas por pedido atingido; decida com o que ja tem")

        ajustes: List[str] = []
        for nome, valor in (("latitude", latitude), ("longitude", longitude), ("raio_km", raio_km)):
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ErroDeUso(f"`{nome}` deve ser um numero")
        if isinstance(k, bool) or not isinstance(k, int):
            raise ErroDeUso("`k` deve ser um inteiro")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ErroDeUso("latitude/longitude fora do intervalo valido")
        if raio_km <= 0:
            raise ErroDeUso("`raio_km` deve ser maior que zero")
        if not isinstance(texto_consulta, str) or not texto_consulta.strip():
            raise ErroDeUso("`texto_consulta` deve ser um texto nao vazio")
        if len(texto_consulta) > MAX_TEXTO:
            raise ErroDeUso(f"`texto_consulta` passa de {MAX_TEXTO} caracteres")
        if not isinstance(categorias, list) or not all(isinstance(c, str) for c in categorias):
            raise ErroDeUso("`categorias` deve ser uma lista de textos")

        # busca.buscar dobra o raio sozinho quando faltam resultados. Para o raio FINAL nunca passar de
        # 2x o pedido, o raio pedido aqui vale no maximo o do pedido.
        if raio_km > ctx.raio_pedido_km:
            ajustes.append(
                f"raio_km limitado a {ctx.raio_pedido_km:g} (raio do pedido); a busca amplia sozinha ate "
                f"{ctx.raio_pedido_km * FATOR_RAIO_MAXIMO:g} se faltar resultado"
            )
            raio_km = ctx.raio_pedido_km
        if not 1 <= k <= K_MAXIMO:
            ajustes.append(f"k ajustado para o intervalo 1..{K_MAXIMO}")
            k = max(1, min(K_MAXIMO, k))

        validas = {c["categoria"] for c in self._categorias_da_base()}
        pedidas = [c.strip().lower() for c in categorias if c.strip()]
        desconhecidas = [c for c in pedidas if c not in validas]
        tipos = [c for c in pedidas if c in validas]
        if desconhecidas:
            ajustes.append(f"categorias inexistentes ignoradas: {desconhecidas}")
        if pedidas and not tipos:
            raise ErroDeUso(f"nenhuma categoria valida. Use listar_categorias. Recebido: {desconhecidas}")
        if not pedidas:
            tipos = [c for c in ctx.tipos_do_pedido if c in validas]
            if tipos:
                ajustes.append(f"categorias do pedido usadas: {tipos}")

        embedding = self._embed(texto_consulta.strip())
        if self._buscar_fn is None:
            self._buscar_fn = _pipeline()[0].buscar
        rejeitados = sorted(ctx.rejeitados)
        with self._conexao() as conexao:
            registro = self._buscar_fn(
                conexao,
                latitude,
                longitude,
                embedding,
                raio_m=raio_km * 1000,
                tipos=tipos or None,
                k=k + len(rejeitados),  # repoe os ja reprovados, que sao descartados abaixo
                # ---- obrigatorios: nao vem do LLM ----
                etiquetas_desejadas=dict(ctx.etiquetas),
                tolerancia_sensorial=ctx.tolerancia_sensorial,
            )

        resposta = registro_para_search_response(registro, self.request_id, tipos or None, rejeitados, k)
        SearchResponse.model_validate(resposta)  # falha cedo se o adaptador divergir do Contrato 3
        busca = self.runlog.registrar(registro.get("consulta_id"), resposta)
        return self._para_llm(busca, ajustes)

    # -- tool 4 --------------------------------------------------------------------------
    def validar_candidatos(self, busca_id: str) -> Dict[str, Any]:
        """Auditoria CONSULTIVA de uma busca do RunLog (nao grava nada; o gate grava o que e entregue).

        Reprovados e hard_filters sugeridos viram filtros obrigatorios das proximas buscas.
        """
        if self.validator is None or self.req is None:
            raise ErroDeUso("validar_candidatos indisponivel nesta execucao")
        try:
            busca = self.runlog.obter(busca_id if isinstance(busca_id, str) else "")
        except BuscaDesconhecida:
            raise ErroDeUso(f"busca_id desconhecido: {busca_id!r}. Use um id devolvido por buscar_lugares") from None
        itens = [SearchItem.model_validate(i) for i in busca.search_response["items"]]
        if not itens:
            raise ErroDeUso(f"a busca {busca.busca_id} nao tem candidatos para validar")
        lote = self.validator.auditar_lote(self.req, itens)
        reprovados = [
            {"place_id": r["place_id"], "nome": r["candidate_name"], "motivos": r["rejection_reasons"]}
            for r in lote["reprovados"]
        ]
        if reprovados:
            self.contexto.aplicar_feedback(
                ValidationFeedback(
                    approved=False,
                    rejected_place_ids=[r["place_id"] for r in reprovados],
                    hard_filters=lote["hard_filters"],
                    diagnostics=lote["diagnostics"],
                )
            )
        return {
            "busca_id": busca.busca_id,
            "todos_aprovados": not reprovados,
            "aprovados": [{"place_id": a["place_id"], "nome": a["candidate_name"]} for a in lote["aprovados"]],
            "reprovados": reprovados,
            "filtros_adicionados_as_proximas_buscas": lote["hard_filters"],
        }

    @staticmethod
    def _para_llm(busca: BuscaRegistrada, ajustes: List[str]) -> Dict[str, Any]:
        r = busca.search_response
        itens = []
        for i in r["items"]:
            itens.append(
                {
                    "place_id": i["place_id"],
                    "nome": i["name"],
                    "categoria": i["amenity"],
                    "distancia_km": round(i["distance_km"], 2),
                    "score": round(i["final_score"], 3),
                    "osm": f"{i['osm_type']}/{i['osm_id']}",
                    "tags": {k: v for k, v in i["osm_tags"].items() if k in TAGS_VISIVEIS},
                }
            )
        return {
            "busca_id": busca.busca_id,
            "status": r["status"],
            "raio_aplicado_km": r["applied_filters"]["radius_km"],
            "raio_ampliado": r["applied_filters"]["expanded_once"],
            "total": r["results_count"],
            "itens": itens,
            "ajustes": ajustes,
        }
