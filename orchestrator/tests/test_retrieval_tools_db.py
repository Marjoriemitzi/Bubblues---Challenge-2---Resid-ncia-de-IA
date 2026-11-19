"""Tools de busca contra um Postgres real (schema temporario). Pulado sem banco."""

from contextlib import nullcontext

import pytest

from orchestrator.contracts import StructuredRequest, ValidationFeedback
from orchestrator.retrieval_tools import ContextoBusca, RetrievalTools
from orchestrator.stubs import _request
from orchestrator.tests.test_integracao_grafo_real import LAT, LON, _lugar, _vetor, conexao  # noqa: F401


def _tools(con, **req_over):
    req = StructuredRequest.model_validate(
        _request("req-db", spatial_constraints={"target_region": "Asa Sul", "max_radius_km": 2.0}, **req_over)
    )
    return RetrievalTools(
        ContextoBusca.de_pedido(req), "req-db",
        conexao_factory=lambda: nullcontext(con), embedder=lambda t: _vetor(),
    )


def _args(**over):
    base = dict(latitude=LAT, longitude=LON, raio_km=2.0, categorias=["cafe"], texto_consulta="cafe", k=5)
    base.update(over)
    return base


def test_listar_categorias_reais(conexao):
    _lugar(conexao, "A", 1, wheelchair="yes")
    _lugar(conexao, "B", 2, wheelchair="yes")
    _lugar(conexao, "P", 3, categoria="park", wheelchair="yes")
    cats = _tools(conexao).executar("listar_categorias", {})["categorias"]
    assert cats == [{"categoria": "cafe", "quantidade": 2}, {"categoria": "park", "quantidade": 1}]


def test_resolver_regiao_real(conexao):
    r = _tools(conexao).executar("resolver_regiao", {"nome": "asa sul"})
    assert [x["nome"] for x in r["regioes"]] == ["Asa Sul"]
    assert _tools(conexao).executar("resolver_regiao", {"nome": "Narnia"}) == {"regioes": []}


def test_wheelchair_obrigatorio_vale_no_sql(conexao):
    _lugar(conexao, "Com rampa", 11, 100, wheelchair="yes")
    _lugar(conexao, "Sem rampa", 12, 50, wheelchair="no")
    _lugar(conexao, "Sem tag", 13, 60)
    r = _tools(conexao).executar("buscar_lugares", _args())
    assert [i["nome"] for i in r["itens"]] == ["Com rampa"]
    assert r["itens"][0]["tags"]["wheelchair"] == "yes"


def test_sem_exigencia_de_acessibilidade_nao_filtra(conexao):
    _lugar(conexao, "Com rampa", 21, 100, wheelchair="yes")
    _lugar(conexao, "Sem tag", 22, 60)
    t = _tools(conexao, accessibility_requirements={"wheelchair_required": False})
    assert {i["nome"] for i in t.executar("buscar_lugares", _args())["itens"]} == {"Com rampa", "Sem tag"}


def test_rejeitado_do_validador_nao_volta(conexao):
    _lugar(conexao, "Bom", 31, 100, wheelchair="yes")
    _lugar(conexao, "Ruim", 32, 50, wheelchair="yes")
    t = _tools(conexao)
    primeira = t.executar("buscar_lugares", _args())
    ruim = next(i["place_id"] for i in primeira["itens"] if i["nome"] == "Ruim")
    t.contexto.aplicar_feedback(ValidationFeedback(approved=False, rejected_place_ids=[ruim]))
    segunda = t.executar("buscar_lugares", _args())
    assert [i["nome"] for i in segunda["itens"]] == ["Bom"]


def test_busca_grava_evidencia_e_registra_consulta_id(conexao):
    _lugar(conexao, "A", 41, 100, wheelchair="yes")
    t = _tools(conexao)
    r = t.executar("buscar_lugares", _args())
    consulta = t.runlog.obter(r["busca_id"]).consulta_id
    assert conexao.execute("SELECT count(*) FROM evidencias_busca WHERE consulta_id = %s", (consulta,)).fetchone()[0] == 1
    assert t.runlog.obter(r["busca_id"]).search_response["items"][0]["is_public_verified"] is True


def test_raio_final_nunca_passa_de_2x_o_pedido_mesmo_com_ampliacao(conexao):
    _lugar(conexao, "Perto", 51, 100, wheelchair="yes")  # so 1 candidato: a busca vai ampliar o raio
    r = _tools(conexao).executar("buscar_lugares", _args(raio_km=500.0, k=5))  # pedido = 2 km
    assert r["raio_ampliado"] is True and r["raio_aplicado_km"] <= 4.0
