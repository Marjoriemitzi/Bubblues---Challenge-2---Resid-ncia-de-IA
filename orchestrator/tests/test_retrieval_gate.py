"""RetrievalGate: a auditoria obrigatoria da selecao final."""

import pytest

from orchestrator.contracts import StructuredRequest
from orchestrator.evidence_store import MemoryEvidenceStore
from orchestrator.retrieval_gate import RetrievalGate, SelecaoInvalida
from orchestrator.retrieval_tools import ContextoBusca, RetrievalTools
from orchestrator.stubs import _request
from orchestrator.tests.test_retrieval_pipeline import CAFE_OK, FakeBusca, _linha, _registro
from orchestrator.tests.test_retrieval_tools import _conexao
from orchestrator.validation_tool import EvidenceValidator

CID = "56c6f629-21e8-4014-80fe-e8c0a1b2c3d4"


def _req():
    return StructuredRequest.model_validate(
        _request("r1", spatial_constraints={"target_region": "Asa Sul", "max_radius_km": 2.0})
    )


def _busca(linhas):
    req = _req()
    reg = _registro(linhas)
    reg["consulta_id"] = CID
    t = RetrievalTools(
        ContextoBusca.de_pedido(req), "r1", conexao_factory=_conexao, embedder=lambda x: [0.1] * 768,
        buscar_fn=FakeBusca(reg), regioes_fn=lambda c, n, l: [],
    )
    b = t.executar("buscar_lugares", dict(latitude=-15.8, longitude=-47.9, raio_km=2.0, categorias=["cafe"],
                                          texto_consulta="cafe", k=3))["busca_id"]
    return req, t.runlog.obter(b)


def _gate():
    store = MemoryEvidenceStore()
    return RetrievalGate(EvidenceValidator(store=store)), store


def test_aprova_busca_conforme_e_grava_a_auditoria():
    req, busca = _busca([_linha(1, "A", 111, CAFE_OK), _linha(2, "B", 222, CAFE_OK)])
    gate, store = _gate()
    r = gate.auditar(req, busca)
    assert r.aprovado and [e.place_id for e in r.evidence_records] == ["1", "2"]
    assert len(store.linhas) == 2 and {l["consulta_id"] for l in store.linhas} == {CID}


def test_reprovacao_devolve_feedback_com_hard_filters_e_grava_so_reprovados():
    req, busca = _busca([_linha(1, "Sem rampa", 111, {"amenity": "cafe", "wheelchair": "no"}), _linha(2, "B", 222, CAFE_OK)])
    gate, store = _gate()
    r = gate.auditar(req, busca)
    assert not r.aprovado and r.evidence_records == []
    assert r.feedback.rejected_place_ids == ["1"] and r.feedback.hard_filters == {"wheelchair": "yes"}
    assert [l["place_id"] for l in store.linhas] == ["1"]


def test_selecao_subconjunto_reordena_e_renumera():
    req, busca = _busca([_linha(1, "A", 111, CAFE_OK), _linha(2, "B", 222, CAFE_OK), _linha(3, "C", 333, CAFE_OK)])
    gate, _ = _gate()
    r = gate.auditar(req, busca, place_ids=["3", "1"])
    assert [e.place_id for e in r.evidence_records] == ["3", "1"]
    assert [(i.rank, i.place_id) for i in r.search_response.items] == [(1, "3"), (2, "1")]
    assert r.search_response.results_count == 2


def test_selecao_com_lugar_fora_da_busca_e_recusada_e_nada_e_gravado():
    req, busca = _busca([_linha(1, "A", 111, CAFE_OK)])
    gate, store = _gate()
    with pytest.raises(SelecaoInvalida, match="fora da busca"):
        gate.auditar(req, busca, place_ids=["1", "999"])
    assert store.linhas == []


@pytest.mark.parametrize("ids", [[], ["1", "1"]])
def test_selecao_vazia_ou_repetida_e_recusada(ids):
    req, busca = _busca([_linha(1, "A", 111, CAFE_OK)])
    with pytest.raises(SelecaoInvalida):
        _gate()[0].auditar(req, busca, place_ids=ids)


def test_busca_sem_candidatos_nao_e_aprovada():
    req, busca = _busca([])
    r = _gate()[0].auditar(req, busca)
    assert not r.aprovado and r.evidence_records == [] and r.feedback.diagnostics


def test_o_gate_audita_mesmo_que_o_llm_nunca_tenha_chamado_a_tool():
    """O gate nao depende de `validar_candidatos` ter sido chamada: ele roda o validador sozinho."""
    req, busca = _busca([_linha(1, "Sem rampa", 111, {"amenity": "cafe", "wheelchair": "no"})])
    assert not _gate()[0].auditar(req, busca).aprovado


def test_candidato_sem_osm_e_reprovado_pelo_rnf01():
    linha = _linha(1, "Fantasma", 111, CAFE_OK)
    linha["osm"] = {"osm_id": None, "osm_type": None, "tags": {}}
    req, busca = _busca([linha])
    r = _gate()[0].auditar(req, busca)
    assert not r.aprovado and any("RNF01" in d for d in r.feedback.diagnostics)
