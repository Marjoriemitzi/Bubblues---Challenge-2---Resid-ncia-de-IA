"""Tools de busca: filtros obrigatorios inescapaveis, limites, RunLog. Sem banco e sem LLM."""

import json
from contextlib import contextmanager

import pytest

from orchestrator.contracts import SearchResponse, StructuredRequest, ValidationFeedback
from orchestrator.retrieval_tools import (
    K_MAXIMO,
    MAX_BUSCAS,
    SCHEMAS,
    BuscaDesconhecida,
    ContextoBusca,
    RetrievalTools,
    RunLog,
)
from orchestrator.evidence_store import MemoryEvidenceStore
from orchestrator.stubs import _request
from orchestrator.validation_tool import EvidenceValidator
from orchestrator.tests.test_retrieval_pipeline import CAFE_OK, FakeBusca, _linha, _registro

CATEGORIAS = [("cafe", 174), ("park", 442), ("restaurant", 1246)]


class FakeConexao:
    def __init__(self):
        self.consultas = 0

    def execute(self, sql, params=()):
        self.consultas += 1
        return self

    def fetchall(self):
        return CATEGORIAS


@contextmanager
def _conexao():
    yield FakeConexao()


def _req(**over):
    return StructuredRequest.model_validate(
        _request("r1", spatial_constraints={"target_region": "Asa Sul", "max_radius_km": 2.0}, **over)
    )


def _tools(fake=None, req=None, feedback=None, regioes=None, **kw):
    fake = fake or FakeBusca(_registro([_linha(1, "A", 111, CAFE_OK), _linha(2, "B", 222, CAFE_OK)]))
    ctx = ContextoBusca.de_pedido(req or _req(), feedback)
    t = RetrievalTools(
        ctx, "r1", conexao_factory=_conexao, embedder=lambda txt: [0.1] * 768, buscar_fn=fake,
        regioes_fn=regioes or (lambda con, nome, limite: []), **kw,
    )
    return t, fake


def _buscar(t, **over):
    args = dict(latitude=-15.81, longitude=-47.90, raio_km=2.0, categorias=["cafe"],
                texto_consulta="cafe calmo para ler", k=3)
    args.update(over)
    return t.executar("buscar_lugares", args)


# ------------------------------------------------------------------ schemas
def test_schemas_sao_estritos_e_completos():
    nomes = [s["function"]["name"] for s in SCHEMAS]
    assert nomes == ["resolver_regiao", "listar_categorias", "buscar_lugares", "validar_candidatos"]
    for s in SCHEMAS:
        p = s["function"]["parameters"]
        assert s["function"]["strict"] is True and p["additionalProperties"] is False
        assert set(p["required"]) == set(p["properties"])  # nada opcional: compativel com strict
    json.dumps(SCHEMAS)


def test_nao_existe_argumento_para_desligar_filtros():
    props = next(s for s in SCHEMAS if s["function"]["name"] == "buscar_lugares")["function"]["parameters"]["properties"]
    assert not {"etiquetas", "wheelchair", "tolerancia", "tolerancia_sensorial", "excluir"} & set(props)


# ------------------------------------------------------------------ filtros obrigatorios
def test_filtros_obrigatorios_chegam_a_busca_mesmo_que_o_llm_nao_os_mencione():
    t, fake = _tools()
    _buscar(t)
    c = fake.chamadas[0]
    assert c["etiquetas_desejadas"] == {"wheelchair": "yes"}
    assert c["tolerancia_sensorial"] == "baixo"


def test_llm_tentando_desligar_filtro_e_recusado_e_nada_e_buscado():
    t, fake = _tools()
    for extra in ({"wheelchair": "no"}, {"exigir_acessibilidade": False}, {"etiquetas": {}}):
        r = t.executar("buscar_lugares", {
            "latitude": -15.8, "longitude": -47.9, "raio_km": 2, "categorias": ["cafe"],
            "texto_consulta": "x", "k": 3, **extra,
        })
        assert "argumentos nao permitidos" in r["erro"]
    assert fake.chamadas == []


def test_hard_filters_do_validador_endurecem_a_proxima_busca():
    r = StructuredRequest.model_validate(
        _request("r1", noise_tolerance="moderado", accessibility_requirements={"wheelchair_required": False},
                 spatial_constraints={"target_region": None, "max_radius_km": 2.0})
    )
    fb = ValidationFeedback(approved=False, rejected_place_ids=["7"],
                            hard_filters={"wheelchair": "yes", "noise_level": "baixo"})
    t, fake = _tools(req=r, feedback=fb)
    _buscar(t)
    c = fake.chamadas[0]
    assert c["etiquetas_desejadas"] == {"wheelchair": "yes"} and c["tolerancia_sensorial"] == "baixo"


def test_contexto_so_acumula_nunca_afrouxa():
    ctx = ContextoBusca.de_pedido(_req())
    ctx.aplicar_feedback(ValidationFeedback(approved=False, rejected_place_ids=["1"], hard_filters={"noise_level": "moderado"}))
    ctx.aplicar_feedback(ValidationFeedback(approved=False, rejected_place_ids=["2"], hard_filters={}))
    assert ctx.rejeitados == {"1", "2"}
    assert ctx.tolerancia_sensorial == "baixo" and ctx.etiquetas == {"wheelchair": "yes"}


def test_rejeitados_sao_excluidos_e_k_repoe():
    fb = ValidationFeedback(approved=False, rejected_place_ids=["1"])
    reg = _registro([_linha(1, "A", 111, CAFE_OK), _linha(2, "B", 222, CAFE_OK), _linha(3, "C", 333, CAFE_OK)])
    t, fake = _tools(FakeBusca(reg), feedback=fb)
    r = _buscar(t, k=2)
    assert fake.chamadas[0]["k"] == 3  # 2 + 1 rejeitado
    assert [i["place_id"] for i in r["itens"]] == ["2", "3"]


# ------------------------------------------------------------------ limites
def test_raio_pedido_pelo_llm_nao_passa_do_raio_do_pedido():
    # A busca dobra o raio sozinha se faltar resultado; por isso o teto aqui e 1x (final <= 2x).
    t, fake = _tools()
    r = _buscar(t, raio_km=50)
    assert fake.chamadas[0]["raio_m"] == 2000.0  # pedido = 2 km
    assert any("raio_km limitado" in a and "ate 4" in a for a in r["ajustes"])


def test_llm_pode_reduzir_o_raio():
    t, fake = _tools()
    r = _buscar(t, raio_km=0.5)
    assert fake.chamadas[0]["raio_m"] == 500.0 and not any("raio" in a for a in r["ajustes"])


def test_k_fora_do_intervalo_e_ajustado():
    t, fake = _tools()
    r = _buscar(t, k=999)
    assert fake.chamadas[0]["k"] == K_MAXIMO and any("k ajustado" in a for a in r["ajustes"])
    assert _buscar(t, k=0)["ajustes"]


def test_categorias_inexistentes_sao_ignoradas_ou_recusadas():
    t, fake = _tools()
    r = _buscar(t, categorias=["cafe", "padaria_inventada"])
    assert fake.chamadas[0]["tipos"] == ["cafe"]
    assert any("padaria_inventada" in a for a in r["ajustes"])
    assert "nenhuma categoria valida" in _buscar(t, categorias=["xyz"])["erro"]


def test_categorias_vazias_usam_as_do_pedido():
    t, fake = _tools()
    r = _buscar(t, categorias=[])
    assert fake.chamadas[0]["tipos"] == ["cafe"]
    assert any("categorias do pedido" in a for a in r["ajustes"])


def test_limite_de_buscas_por_pedido():
    t, fake = _tools()
    for _ in range(MAX_BUSCAS):
        assert "erro" not in _buscar(t)
    assert "limite" in _buscar(t)["erro"]
    assert len(fake.chamadas) == MAX_BUSCAS


@pytest.mark.parametrize("over,trecho", [
    ({"latitude": 91.0}, "fora do intervalo"),
    ({"raio_km": 0}, "maior que zero"),
    ({"raio_km": "3"}, "numero"),
    ({"texto_consulta": "  "}, "nao vazio"),
    ({"texto_consulta": "x" * 301}, "caracteres"),
    ({"categorias": "cafe"}, "lista"),
    ({"k": 2.5}, "inteiro"),
])
def test_argumentos_invalidos_voltam_como_erro_sem_buscar(over, trecho):
    t, fake = _tools()
    assert trecho in _buscar(t, **over)["erro"]
    assert fake.chamadas == []


# ------------------------------------------------------------------ RunLog e saida
def test_busca_fica_no_runlog_com_contrato_3_valido():
    t, _ = _tools()
    r = _buscar(t)
    busca = t.runlog.obter(r["busca_id"])
    resp = SearchResponse.model_validate(busca.search_response)
    assert resp.query_id == "r1" and resp.results_count == 2
    assert busca.consulta_id == "c-1"
    assert t.runlog.contem_lugar("1") and t.runlog.contem_lugar("2", r["busca_id"])
    assert not t.runlog.contem_lugar("999")
    with pytest.raises(BuscaDesconhecida):
        t.runlog.obter("B99")


def test_saida_e_json_puro_sem_vetores_e_com_tags_uteis():
    t, _ = _tools()
    r = _buscar(t)
    texto = json.dumps(r)
    assert "embedding" not in texto and "0.1, 0.1" not in texto
    assert r["itens"][0]["tags"]["wheelchair"] == "yes"
    assert r["itens"][0]["osm"] == "node/111" and r["status"] == "SUCCESS"


def test_runlog_isolado_por_execucao():
    a, b = RunLog(), RunLog()
    a.registrar(None, {"items": []})
    assert a.total == 1 and b.total == 0


# ------------------------------------------------------------------ outras tools
def test_resolver_regiao_devolve_candidatos_limitados():
    vistos = {}

    def regioes(con, nome, limite):
        vistos.update(nome=nome, limite=limite)
        return [{"nome": "Guará", "tipo": "place=quarter", "latitude": -15.83, "longitude": -47.98,
                 "osm_type": "node", "osm_id": 1}] * 9

    t, _ = _tools(regioes=regioes)
    r = t.executar("resolver_regiao", {"nome": "Guará"})
    assert vistos == {"nome": "Guará", "limite": 5} and len(r["regioes"]) == 5
    assert set(r["regioes"][0]) == {"nome", "tipo", "latitude", "longitude"}
    assert "nao vazio" in t.executar("resolver_regiao", {"nome": " "})["erro"]


def test_listar_categorias_consulta_o_banco_uma_vez():
    conexoes = []

    @contextmanager
    def conectar():
        c = FakeConexao()
        conexoes.append(c)
        yield c

    ctx = ContextoBusca.de_pedido(_req())
    t = RetrievalTools(ctx, "r1", conexao_factory=conectar, embedder=lambda x: [0.1] * 768,
                       buscar_fn=FakeBusca(_registro([])))
    a = t.executar("listar_categorias", None)
    b = t.executar("listar_categorias", "{}")
    assert a == b and a["categorias"][0] == {"categoria": "cafe", "quantidade": 174}
    assert sum(c.consultas for c in conexoes) == 1


def test_tool_desconhecida_e_json_invalido_voltam_como_erro():
    t, _ = _tools()
    assert "desconhecida" in t.executar("apagar_banco", {})["erro"]
    assert "JSON" in t.executar("buscar_lugares", "{nao e json")["erro"]
    assert "objeto" in t.executar("buscar_lugares", [1])["erro"]
    assert "obrigatorios ausentes" in t.executar("buscar_lugares", {})["erro"]


def test_falha_de_infraestrutura_sobe_a_excecao():
    def quebrada(*a, **k):
        raise ConnectionError("db fora")

    t, _ = _tools(FakeBusca(_registro([])))
    t._buscar_fn = quebrada
    with pytest.raises(ConnectionError):
        _buscar(t)



# ------------------------------------------------------------------ tool 4: validar_candidatos
def _com_validador(fake=None, req=None, feedback=None, store=None):
    req = req or _req()
    fake = fake or FakeBusca(_registro([_linha(1, "A", 111, CAFE_OK), _linha(2, "B", 222, CAFE_OK)]))
    t = RetrievalTools(
        ContextoBusca.de_pedido(req, feedback), "r1", conexao_factory=_conexao, embedder=lambda x: [0.1] * 768,
        buscar_fn=fake, regioes_fn=lambda c, n, l: [], req=req, validator=EvidenceValidator(store=store),
    )
    return t, fake


def test_schemas_so_inclui_validar_quando_ha_validador():
    sem, _ = _tools()
    com, _ = _com_validador()
    assert [s["function"]["name"] for s in sem.schemas()] == ["resolver_regiao", "listar_categorias", "buscar_lugares"]
    assert "validar_candidatos" in [s["function"]["name"] for s in com.schemas()]
    assert "indisponivel" in sem.executar("validar_candidatos", {"busca_id": "B1"})["erro"]


def test_validar_aprova_busca_conforme_e_nao_muda_o_contexto():
    t, _ = _com_validador()
    b = _buscar(t)["busca_id"]
    r = t.executar("validar_candidatos", {"busca_id": b})
    assert r["todos_aprovados"] is True and [x["place_id"] for x in r["aprovados"]] == ["1", "2"]
    assert r["reprovados"] == [] and t.contexto.rejeitados == set()


def test_validar_reprovados_viram_filtros_obrigatorios_das_proximas_buscas():
    ruim = _linha(1, "Sem rampa", 111, {"amenity": "cafe", "wheelchair": "no"})
    bom = _linha(2, "Com rampa", 222, CAFE_OK)
    fake = FakeBusca(_registro([ruim, bom]), _registro([bom]))
    t, fake = _com_validador(fake)
    b = _buscar(t)["busca_id"]
    r = t.executar("validar_candidatos", {"busca_id": b})
    assert r["todos_aprovados"] is False
    assert [x["place_id"] for x in r["reprovados"]] == ["1"] and r["reprovados"][0]["motivos"]
    assert r["filtros_adicionados_as_proximas_buscas"] == {"wheelchair": "yes"}
    assert t.contexto.rejeitados == {"1"}
    _buscar(t)  # a proxima busca ja sai com o rejeitado excluido (k repoe)
    assert fake.chamadas[1]["k"] == 4 and fake.chamadas[1]["etiquetas_desejadas"] == {"wheelchair": "yes"}


def test_validar_nao_grava_nada_no_store():
    store = MemoryEvidenceStore()
    t, _ = _com_validador(store=store)
    t.executar("validar_candidatos", {"busca_id": _buscar(t)["busca_id"]})
    assert store.linhas == []  # consultivo: quem grava e o gate


def test_validar_so_aceita_busca_do_runlog():
    t, _ = _com_validador()
    assert "desconhecido" in t.executar("validar_candidatos", {"busca_id": "B99"})["erro"]
    assert "desconhecido" in t.executar("validar_candidatos", {"busca_id": 7})["erro"]


def test_validar_busca_vazia_e_erro_de_uso():
    t, _ = _com_validador(FakeBusca(_registro([])))
    b = _buscar(t)["busca_id"]
    assert "nao tem candidatos" in t.executar("validar_candidatos", {"busca_id": b})["erro"]
