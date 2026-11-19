"""PostgresEvidenceStore contra um Postgres real (schema temporario). Pulado sem banco."""

import sys
import uuid
from contextlib import nullcontext
from pathlib import Path

import pytest

from orchestrator.catalogo_exemplo import BASE_POIS_CATALOG
from orchestrator.contracts import AppliedFilters, SearchResponse
from orchestrator.evidence_store import PostgresEvidenceStore
from orchestrator.tests.test_validation_tool import _search_item, base_request  # noqa: F401 (fixture)
from orchestrator.validation_tool import EvidenceValidator

RAIZ = Path(__file__).resolve().parents[2]
SCHEMA = RAIZ / "data-pipeline" / "db" / "schema.sql"


@pytest.fixture
def conexao():
    sys.path.insert(0, str(RAIZ / "data-pipeline"))
    try:
        import busca

        con = busca.conectar()
    except Exception as erro:  # sem psycopg, sem .env ou banco fora do ar
        pytest.skip(f"Banco indisponivel: {erro}")
    schema = f"teste_{uuid.uuid4().hex}"
    con.execute(f"CREATE SCHEMA {schema}")
    con.execute(f"SET search_path TO {schema}, public")
    con.execute(SCHEMA.read_text(encoding="utf-8"))
    yield con
    con.execute(f"DROP SCHEMA {schema} CASCADE")
    con.close()


def _agente(conexao):
    store = PostgresEvidenceStore(conexao_factory=lambda: nullcontext(conexao))
    return EvidenceValidator(store=store, metadata_catalog=BASE_POIS_CATALOG)


def _resposta(req, items, consulta_id):
    return SearchResponse(
        query_id=req.request_id, consulta_id=consulta_id, status="SUCCESS",
        applied_filters=AppliedFilters(radius_km=3.0, expanded_once=False, amenities=["cafe"]),
        results_count=len(items), items=items,
    )


def test_grava_evidencias_aprovadas_com_osm_e_json(conexao, base_request):
    cid = str(uuid.uuid4())
    sr = _resposta(base_request, [_search_item("POI-01", rank=1), _search_item("POI-02", rank=2)], cid)
    fb, records = _agente(conexao).auditar_search_response(base_request, sr)
    assert fb.approved and len(records) == 2

    linhas = conexao.execute(
        "SELECT query_id, consulta_id::text, osm_id, osm_type, aprovado, evidence->>'evidence_id', "
        "evidence->'integrity_test'->>'passed' FROM evidencias_auditoria ORDER BY place_id"
    ).fetchall()
    assert len(linhas) == 2
    for query_id, consulta, osm_id, osm_type, aprovado, ev_id, passou in linhas:
        assert (query_id, consulta, aprovado, passou) == (base_request.request_id, cid, True, "true")
        assert osm_id > 0 and osm_type in ("node", "way")
        assert ev_id.startswith("EV-")


def test_reprovado_grava_motivos_e_osm_nulo(conexao, base_request):
    sr = _resposta(base_request, [_search_item("POI-FANTASMA", name="Lugar Inexistente", rank=1)], None)
    fb, records = _agente(conexao).auditar_search_response(base_request, sr)
    assert not fb.approved and records == []
    aprovado, osm_id, motivos, consulta = conexao.execute(
        "SELECT aprovado, osm_id, motivos_rejeicao, consulta_id FROM evidencias_auditoria"
    ).fetchone()
    assert aprovado is False and osm_id is None and consulta is None
    assert any("RNF01" in m for m in motivos)


def test_regravar_a_mesma_auditoria_nao_duplica(conexao, base_request):
    store = PostgresEvidenceStore(conexao_factory=lambda: nullcontext(conexao))
    ag = EvidenceValidator(metadata_catalog=BASE_POIS_CATALOG)
    auditoria = ag.auditar_candidato(base_request, _search_item("POI-01"))
    store.salvar([auditoria], None)
    store.salvar([auditoria], None)
    assert conexao.execute("SELECT count(*) FROM evidencias_auditoria").fetchone()[0] == 1
