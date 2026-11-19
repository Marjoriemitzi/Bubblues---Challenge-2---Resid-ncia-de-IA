"""Retrieval_Agent: adaptacao Contrato 2 -> busca.buscar -> Contrato 3, sem banco.

`buscar` e trocada por um fake que devolve o MESMO formato do busca.py real
(score calculado por data-pipeline/score.py), entao o adaptador e a auditoria
rodam de verdade.
"""

from contextlib import contextmanager

import pytest

from orchestrator.contracts import SearchResponse, StructuredRequest, ValidationFeedback
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, build_graph, run
from orchestrator.retrieval_common import (
    montar_parametros,
    registro_para_search_response,
    texto_do_embedding,
)
from orchestrator.retrieval_pipeline import RetrievalPipeline
from orchestrator.stubs import _request, stub_communication, stub_nlu
from orchestrator.evidence_store import MemoryEvidenceStore
from orchestrator.validation_tool import EvidenceValidator


def _score():
    from orchestrator.retrieval_common import _pipeline

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


class _Con:
    """Conexao falsa: so sabe listar as categorias da base."""

    def execute(self, sql, params=()):
        return self

    def fetchall(self):
        return [("cafe", 174), ("park", 442), ("restaurant", 1246)]


@contextmanager
def _conexao():
    yield _Con()


def _agente(fake, **kw):
    kw.setdefault("validator", EvidenceValidator(store=MemoryEvidenceStore()))
    kw.setdefault("regioes_fn", lambda con, nome, limite: [])
    return RetrievalPipeline(conexao_factory=_conexao, embedder=lambda t: [0.1] * 768, buscar_fn=fake, **kw)


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


# ------------------------------------------------------------ pipeline: busca -> gate -> reconsulta
def _bom(pid, nome, osm):
    return _linha(pid, nome, osm, CAFE_OK)


def _ruim(pid, nome, osm):
    return _linha(pid, nome, osm, {"amenity": "cafe", "wheelchair": "no"})


def test_pipeline_busca_com_filtros_obrigatorios_e_entrega_evidencias(req):
    fake = FakeBusca(_registro([_bom(1, "A", 111), _bom(2, "B", 222)]))
    out = _agente(fake)(_estado(req))
    c = fake.chamadas[0]
    assert (c["lat"], c["lon"]) == (-15.7939, -47.8828)  # sem regiao: centro de Brasilia
    assert c["k"] == 3 and c["raio_m"] == 3000.0 and c["tipos"] == ["cafe"]
    assert c["etiquetas_desejadas"] == {"wheelchair": "yes"} and c["tolerancia_sensorial"] == "baixo"
    assert "texto_consulta" not in c  # RNF02
    assert out["validation_feedback"].approved and out["retry_count"] == 0
    assert [e.place_id for e in out["evidence_records"]] == ["1", "2"]
    assert out["search_response"].consulta_id == "c-1"


def test_regiao_resolvida_pela_tabela_de_regioes():
    r = StructuredRequest.model_validate(_request("r1"))  # target_region = "Asa Sul"
    vistos = []

    def regioes(con, nome, limite):
        vistos.append((nome, limite))
        return [{"nome": "Asa Sul", "tipo": "place=suburb", "latitude": -15.8169, "longitude": -47.9000}]

    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    _agente(fake, regioes_fn=regioes)(_estado(r))
    assert vistos == [("Asa Sul", 5)]
    assert (fake.chamadas[0]["lat"], fake.chamadas[0]["lon"]) == (-15.8169, -47.9000)


def test_regiao_desconhecida_pede_esclarecimento_sem_buscar_nem_gerar_embedding():
    def embedder(texto):
        raise AssertionError("nao deveria gerar embedding")

    r = StructuredRequest.model_validate(_request("r1", spatial_constraints={"target_region": "Narnia", "max_radius_km": 3.0}))
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    p = RetrievalPipeline(conexao_factory=_conexao, embedder=embedder, buscar_fn=fake, regioes_fn=lambda c, n, l: [],
                          validator=EvidenceValidator(store=MemoryEvidenceStore()))
    out = p(_estado(r))
    assert fake.chamadas == []
    assert out["search_response"]["status"] == "NO_RESULTS"
    assert "Narnia" in out["structured_request"].clarification_needed
    assert "evidence_records" not in out


def test_estado_sem_request_falha_alto():
    with pytest.raises(ValueError):
        _agente(FakeBusca(_registro([])))({"request_id": "r1"})


def test_reconsulta_aplica_os_filtros_do_gate_e_aprova():
    fake = FakeBusca(_registro([_ruim(1, "Sem rampa", 111), _bom(2, "Com rampa", 222)]), _registro([_bom(2, "Com rampa", 222)]))
    store = MemoryEvidenceStore()
    r = StructuredRequest.model_validate(_request("r1", spatial_constraints={"target_region": None, "max_radius_km": 3.0}))
    out = _agente(fake, validator=EvidenceValidator(store=store))(_estado(r))
    assert out["retry_count"] == 1 and [e.place_id for e in out["evidence_records"]] == ["2"]
    assert len(fake.chamadas) == 2 and fake.chamadas[1]["k"] == 4  # k + 1 rejeitado
    # auditoria: a 1a rodada gravou so o reprovado; a 2a gravou o aprovado
    assert [(l["place_id"], l["approved"]) for l in store.linhas] == [("1", False), ("2", True)]


def _sem_regiao():
    return StructuredRequest.model_validate(_request("r1", spatial_constraints={"target_region": None, "max_radius_km": 3.0}))


def test_trava_de_reconsultas_e_abstencao():
    # a cada rodada aparece outro candidato ruim: 1 busca + 2 reconsultas, e para
    fake = FakeBusca(_registro([_ruim(1, "R1", 111)]), _registro([_ruim(2, "R2", 222)]), _registro([_ruim(3, "R3", 333)]))
    out = _agente(fake, max_retries=2)(_estado(_sem_regiao()))
    assert len(fake.chamadas) == 3
    assert out["retry_count"] == 2 and "evidence_records" not in out
    assert out["validation_feedback"].approved is False
    assert out["validation_feedback"].hard_filters == {"wheelchair": "yes"}


def test_reprovado_e_sem_candidato_novo_para_repor_mantem_o_feedback():
    # a reconsulta so devolve o lugar ja reprovado (que e excluido): nao sobra nada, mas houve reprovacao
    fake = FakeBusca(_registro([_ruim(1, "Sem rampa", 111)]))
    out = _agente(fake, max_retries=2)(_estado(_sem_regiao()))
    assert len(fake.chamadas) == 2
    assert out["retry_count"] == 1 and out["validation_feedback"].approved is False
    assert out["validation_feedback"].rejected_place_ids == ["1"] and out["search_response"]["status"] == "NO_RESULTS"
    assert "sem novos candidatos" in out["note"]


def test_busca_sem_candidatos_nao_aciona_o_gate():
    store = MemoryEvidenceStore()
    out = _agente(FakeBusca(_registro([])), validator=EvidenceValidator(store=store))(_estado(StructuredRequest.model_validate(
        _request("r1", spatial_constraints={"target_region": None, "max_radius_km": 3.0}))))
    assert out["search_response"]["status"] == "NO_RESULTS" and "validation_feedback" not in out
    assert store.linhas == [] and out["retry_count"] == 0


def test_categoria_que_a_base_nao_tem_vira_sem_resultado_e_nao_erro():
    r = StructuredRequest.model_validate(_request("r1", target_amenities=["xyz"],
                                                  spatial_constraints={"target_region": None, "max_radius_km": 3.0}))
    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    out = _agente(fake)(_estado(r))
    assert fake.chamadas == [] and out["search_response"]["status"] == "NO_RESULTS"
    assert "nao atendivel" in out["note"]


def test_falha_de_infra_sobe_a_excecao():
    def quebrada(*a, **k):
        raise ConnectionError("db fora")

    r = StructuredRequest.model_validate(_request("r1", spatial_constraints={"target_region": None, "max_radius_km": 3.0}))
    with pytest.raises(ConnectionError):
        _agente(quebrada)(_estado(r))


# ------------------------------------------------------------ grafo completo (nlu -> retrieval -> communication)
def _grafo(fake, nlu_over=None, **kw):
    over = {"spatial_constraints": {"target_region": None, "max_radius_km": 3.0}, **(nlu_over or {})}
    return build_graph(stub_nlu(**over), _agente(fake, **kw), stub_communication)


def _trilha(s):
    return [t.agent for t in s["agent_trace"]]


def test_grafo_aprova_direto():
    s = run(_grafo(FakeBusca(_registro([_bom(1, "A", 111)]))), "q", "r-ok")
    assert _trilha(s) == [NLU, RETRIEVAL, COMMUNICATION]
    assert s["validation_feedback"].approved and s["retry_count"] == 0
    assert s["evidence_records"][0].osm_reference.osm_link == "https://www.openstreetmap.org/node/111"
    assert s["final_response"] == "top-3 auditado"


def test_grafo_reconsulta_e_o_trace_continua_linear():
    fake = FakeBusca(_registro([_ruim(1, "Sem rampa", 111)]), _registro([_bom(2, "Com rampa", 222)]))
    s = run(_grafo(fake), "q", "r-retry")
    assert _trilha(s) == [NLU, RETRIEVAL, COMMUNICATION]  # o laco e interno ao Retrieval
    assert s["retry_count"] == 1 and s["evidence_records"][0].place_id == "2"
    assert "reconsultas=1" in s["agent_trace"][1].note


def test_grafo_gate_reprovado_apos_reconsultas_abstem():
    fake = FakeBusca(_registro([_ruim(1, "R1", 111)]), _registro([_ruim(2, "R2", 222)]), _registro([_ruim(3, "R3", 333)]))
    s = run(_grafo(fake), "q", "r-trava")
    assert s["final_response"] == "abstencao" and s["retry_count"] == 2
    assert "reprovado pelo gate" in s["agent_trace"][1].justification


def test_grafo_reprovado_sem_candidato_novo_tambem_e_reprovado_pelo_gate():
    s = run(_grafo(FakeBusca(_registro([_ruim(1, "Sem rampa", 111)]))), "q", "r-esgotou")
    assert s["final_response"] == "abstencao" and s["retry_count"] == 1
    assert "reprovado pelo gate" in s["agent_trace"][1].justification  # nao "busca sem candidatos"


def test_grafo_sem_resultados_abstem():
    s = run(_grafo(FakeBusca(_registro([]))), "q", "r-vazio")
    assert _trilha(s) == [NLU, RETRIEVAL, COMMUNICATION] and s["final_response"] == "abstencao"


def test_grafo_regiao_desconhecida_pergunta_ao_usuario():
    s = run(_grafo(FakeBusca(_registro([_bom(1, "A", 111)])), nlu_over={"spatial_constraints": {"target_region": "Narnia", "max_radius_km": 3.0}}), "q", "r-narnia")
    assert "Narnia" in s["final_response"]
    assert "clarification_needed" in s["agent_trace"][1].justification


def test_grafo_erro_do_banco_vira_abstencao_segura():
    def quebrada(*a, **k):
        raise ConnectionError("db fora")

    s = run(_grafo(quebrada), "q", "r-erro")
    assert s["error"] == "retrieval: ConnectionError" and s["final_response"] == "abstencao"


def test_grafo_falha_ao_gravar_auditoria_nao_entrega_nada():
    """Fail-closed: sem rastro de auditoria o resultado nao pode ser entregue."""

    class Quebrada:
        def salvar(self, auditorias, consulta_id=None):
            raise ConnectionError("db fora")

    fake = FakeBusca(_registro([_bom(1, "A", 111)]))
    s = run(_grafo(fake, validator=EvidenceValidator(store=Quebrada())), "q", "r-store")
    assert s["error"] == "retrieval: ConnectionError" and s["final_response"] == "abstencao"
    assert not s.get("evidence_records")
