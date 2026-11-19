"""Retrieval_Agent: adaptacao Contrato 2 -> busca.buscar -> Contrato 3, sem banco.

`buscar` e trocada por um fake que devolve o MESMO formato do busca.py real
(score calculado por data-pipeline/score.py), entao o adaptador e a auditoria
rodam de verdade.
"""

from contextlib import nullcontext

import pytest

from orchestrator.contracts import SearchResponse, StructuredRequest, ValidationFeedback
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, VALIDATION, build_graph, run
from orchestrator.retrieval_agent import (
    RetrievalAgent,
    montar_parametros,
    registro_para_search_response,
    texto_do_embedding,
)
from orchestrator.stubs import _request, stub_communication, stub_nlu
from orchestrator.validation_agent import ValidationAgent


def _score():
    from orchestrator.retrieval_agent import _pipeline

    busca = _pipeline()[0]
    return busca.calcular_score, busca.link_osm


def _linha(place_id, nome, osm_id, tags, distancia_m=800.0, similaridade=0.9):
    calcular_score, link_osm = _score()
    fatores, total = calcular_score(similaridade, distancia_m, 4.0, 4.5, tags, {"wheelchair": "yes"})
    return {
        "posicao": 0,
        "local": {
            "place_id": place_id, "nome": nome, "categoria": "cafe",
            "latitude": -15.79, "longitude": -47.88, "distancia_m": distancia_m,
        },
        "osm_url": link_osm("node", osm_id),
        "osm": {"osm_id": osm_id, "osm_type": "node", "tags": tags},
        "etiquetas_usadas": {"amenity": "cafe"},
        "fatores": fatores,
        "score_total": total,
    }


def _registro(linhas, ampliado=False, raio_final=3000.0):
    for i, r in enumerate(linhas, start=1):
        r["posicao"] = i
    return {
        "consulta_id": "c-1",
        "raio": {"solicitado_m": 3000.0, "final_m": raio_final, "ampliado": ampliado},
        "status": "completo" if linhas else "sem_resultado",
        "resultados": linhas,
    }


CAFE_OK = {"amenity": "cafe", "wheelchair": "yes", "noise_level": "baixo"}


class FakeBusca:
    """Registra as chamadas e devolve linhas fixas."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, conexao, lat, lon, embedding, **kw):
        self.chamadas.append({"lat": lat, "lon": lon, "emb": embedding, **kw})
        return self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]


def _agente(fake, **kw):
    return RetrievalAgent(
        conexao_factory=nullcontext, embedder=lambda t: [0.1] * 768, buscar_fn=fake, **kw
    )


@pytest.fixture
def req():
    return StructuredRequest.model_validate(
        _request("r1", search_vector_focus=["leitura"], noise_tolerance="baixo",
                 spatial_constraints={"target_region": None, "max_radius_km": 3.0})
    )


def _estado(req, **extra):
    return {"request_id": "r1", "structured_request": req, **extra}


# ------------------------------------------------------------ Contrato 2 -> parametros
def test_parametros_basicos(req):
    p = montar_parametros(req, None)
    assert p["raio_m"] == 3000.0
    assert p["tipos"] == ["cafe"]
    assert p["etiquetas_desejadas"] == {"wheelchair": "yes"}  # _request exige cadeira de rodas
    assert p["tolerancia_sensorial"] == "baixo"
    assert p["rejeitados"] == []


def test_embedding_usa_so_campos_estruturados(req):
    t = texto_do_embedding(req)
    assert "leitura" in t and "tranquilo" in t and "conversa" in t
    assert req.raw_query is None


def test_feedback_vira_hard_filters_e_exclusao(req):
    fb = ValidationFeedback(
        approved=False, rejected_place_ids=["7"],
        hard_filters={"wheelchair": "yes", "noise_level": "baixo"},
    )
    p = montar_parametros(req, fb)
    assert p["rejeitados"] == ["7"]
    assert p["etiquetas_desejadas"]["wheelchair"] == "yes"


def test_feedback_nao_afrouxa_tolerancia_do_usuario(req):
    fb = ValidationFeedback(approved=False, hard_filters={"noise_level": "moderado"})
    assert montar_parametros(req, fb)["tolerancia_sensorial"] == "baixo"


def test_feedback_endurece_tolerancia_indiferente():
    r = StructuredRequest.model_validate(_request("r1", noise_tolerance="moderado"))
    fb = ValidationFeedback(approved=False, hard_filters={"noise_level": "baixo"})
    assert montar_parametros(r, fb)["tolerancia_sensorial"] == "baixo"


# ------------------------------------------------------------ resultado -> Contrato 3
def test_conversao_gera_search_response_valido_com_osm():
    reg = _registro([_linha(1, "Cafe A", 111, CAFE_OK), _linha(2, "Cafe B", 222, CAFE_OK)])
    resp = SearchResponse.model_validate(registro_para_search_response(reg, "r1", ["cafe"]))
    assert resp.status == "SUCCESS" and resp.results_count == 2
    it = resp.items[0]
    assert (it.osm_id, it.osm_type, it.is_public_verified) == (111, "node", True)
    assert it.osm_tags["wheelchair"] == "yes"
    assert it.distance_km == pytest.approx(0.8)
    assert it.score_decomposition.sum_check == pytest.approx(it.final_score)


def test_status_expanded_e_no_results():
    r1 = registro_para_search_response(_registro([_linha(1, "A", 1, CAFE_OK)], True, 6000.0), "r", ["cafe"])
    assert r1["status"] == "EXPANDED_RADIUS" and r1["applied_filters"]["radius_km"] == 6.0
    r0 = registro_para_search_response(_registro([]), "r", None)
    assert r0["status"] == "NO_RESULTS" and r0["items"] == []


def test_rejeitados_sao_excluidos_e_ranks_renumerados():
    reg = _registro([_linha(1, "A", 1, CAFE_OK), _linha(2, "B", 2, CAFE_OK), _linha(3, "C", 3, CAFE_OK)])
    d = registro_para_search_response(reg, "r", ["cafe"], rejeitados=["1"], k=3)
    assert [i["place_id"] for i in d["items"]] == ["2", "3"]
    assert [i["rank"] for i in d["items"]] == [1, 2]


def test_local_sem_osm_nao_e_marcado_verificado():
    linha = _linha(1, "A", 1, CAFE_OK)
    linha["osm"] = {"osm_id": None, "osm_type": None, "tags": {}}
    d = registro_para_search_response(_registro([linha]), "r", None)
    assert d["items"][0]["is_public_verified"] is False


# ------------------------------------------------------------ agente
def test_agente_chama_busca_com_parametros_e_pede_k_extra_na_reconsulta(req):
    fake = FakeBusca(_registro([_linha(2, "B", 2, CAFE_OK)]))
    fb = ValidationFeedback(approved=False, rejected_place_ids=["1"], hard_filters={"wheelchair": "yes"})
    out = _agente(fake)(_estado(req, validation_feedback=fb))
    c = fake.chamadas[0]
    assert (c["lat"], c["lon"]) == (-15.7939, -47.8828)
    assert c["k"] == 4 and c["raio_m"] == 3000.0 and c["tipos"] == ["cafe"]
    assert c["etiquetas_desejadas"] == {"wheelchair": "yes"}
    assert "texto_consulta" not in c  # RNF02: nada de texto do usuario no registro de evidencia
    assert out["search_response"]["items"][0]["place_id"] == "2"


def test_regiao_resolvida_pelo_resolver_injetado():
    fake = FakeBusca(_registro([_linha(1, "A", 1, CAFE_OK)]))
    r = StructuredRequest.model_validate(_request("r1"))  # target_region = "Asa Sul"
    vistos = []

    def resolver(regiao, conexao):
        vistos.append(regiao)
        return (-15.8169, -47.9000)

    _agente(fake, resolver_local=resolver)(_estado(r))
    assert vistos == ["Asa Sul"]
    assert (fake.chamadas[0]["lat"], fake.chamadas[0]["lon"]) == (-15.8169, -47.9000)


def test_regiao_desconhecida_pede_esclarecimento_sem_buscar():
    fake = FakeBusca(_registro([_linha(1, "A", 1, CAFE_OK)]))
    r = StructuredRequest.model_validate(_request("r1", spatial_constraints={"target_region": "Narnia", "max_radius_km": 3.0}))
    out = _agente(fake, resolver_local=lambda regiao, con: None)(_estado(r))
    assert fake.chamadas == []  # nao chutou lugar nenhum
    assert out["search_response"]["status"] == "NO_RESULTS"
    assert "Narnia" in out["structured_request"].clarification_needed


def test_estado_sem_request_falha_alto():
    with pytest.raises(ValueError):
        _agente(FakeBusca(_registro([])))({"request_id": "r1"})


# ------------------------------------------------------------ grafo completo (agentes reais)
def _grafo(fake, req_overrides=None):
    return build_graph(
        nlu=stub_nlu(spatial_constraints={"target_region": None, "max_radius_km": 3.0}, **(req_overrides or {})),
        retrieval=_agente(fake),
        validation=ValidationAgent(),
        communication=stub_communication,
    )


def test_grafo_aprova_direto():
    fake = FakeBusca(_registro([_linha(1, "A", 111, CAFE_OK)]))
    s = run(_grafo(fake), "q", "r-ok")
    assert [t.agent for t in s["agent_trace"]] == [NLU, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert s["validation_feedback"].approved is True
    ev = s["evidence_records"][0]
    assert ev.osm_reference.osm_link == "https://www.openstreetmap.org/node/111"
    assert s["final_response"] == "top-3 auditado"


def test_grafo_reconsulta_apos_reprovacao_e_aprova():
    ruim = _linha(1, "Sem rampa", 111, {"amenity": "cafe", "wheelchair": "no"})
    bom = _linha(2, "Com rampa", 222, CAFE_OK)
    fake = FakeBusca(_registro([ruim]), _registro([bom]))
    s = run(_grafo(fake), "q", "r-retry")
    assert [t.agent for t in s["agent_trace"]] == [NLU, RETRIEVAL, VALIDATION, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert s["retry_count"] == 1
    assert fake.chamadas[1]["k"] == 4  # k + 1 rejeitado
    assert s["evidence_records"][0].place_id == "2"


def test_grafo_sem_resultados_abstem():
    s = run(_grafo(FakeBusca(_registro([]))), "q", "r-vazio")
    assert [t.agent for t in s["agent_trace"]] == [NLU, RETRIEVAL, COMMUNICATION]
    assert s["final_response"] == "abstencao"


def test_grafo_regiao_desconhecida_pergunta_ao_usuario():
    fake = FakeBusca(_registro([_linha(1, "A", 111, CAFE_OK)]))
    g = build_graph(
        nlu=stub_nlu(spatial_constraints={"target_region": "Narnia", "max_radius_km": 3.0}),
        retrieval=_agente(fake, resolver_local=lambda regiao, con: None),
        validation=ValidationAgent(),
        communication=stub_communication,
    )
    s = run(g, "q", "r-narnia")
    assert [t.agent for t in s["agent_trace"]] == [NLU, RETRIEVAL, COMMUNICATION]
    assert fake.chamadas == []
    assert "Narnia" in s["final_response"]  # modo esclarecimento


def test_grafo_erro_do_banco_vira_abstencao_segura():
    def quebrada(*a, **k):
        raise ConnectionError("db fora")

    s = run(_grafo(quebrada), "q", "r-erro")
    assert s["error"] == "retrieval_agent: ConnectionError"
    assert s["final_response"] == "abstencao"
