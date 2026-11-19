"""Grafo completo com os agentes REAIS (Retrieval + Validation) contra um Postgres de verdade.

Cada teste cria um schema temporario com lugares e regioes proprios, entao nao toca na base real.
NLU e Communication continuam stubs (os reais ainda nao estao plugados). Pulado sem banco.
"""

import json
import sys
import uuid
from contextlib import nullcontext
from pathlib import Path

import pytest

from orchestrator.evidence_store import PostgresEvidenceStore
from orchestrator.graph import COMMUNICATION, NLU, RETRIEVAL, VALIDATION, build_graph, run
from orchestrator.retrieval_agent import RetrievalAgent
from orchestrator.stubs import stub_communication, stub_nlu
from orchestrator.validation_agent import ValidationAgent

RAIZ = Path(__file__).resolve().parents[2]
DIM = 768
LAT, LON = -15.8169, -47.9000  # "Asa Sul" na tabela regioes de teste
METROS_POR_GRAU_LAT = 110_600


def _vetor():
    v = [0.0] * DIM
    v[0] = 1.0
    return v


@pytest.fixture
def conexao():
    sys.path.insert(0, str(RAIZ / "data-pipeline"))
    try:
        import busca

        con = busca.conectar()
    except Exception as erro:
        pytest.skip(f"Banco indisponivel: {erro}")
    schema = f"teste_{uuid.uuid4().hex}"
    con.execute(f"CREATE SCHEMA {schema}")
    con.execute(f"SET search_path TO {schema}, public")
    con.execute((RAIZ / "data-pipeline" / "db" / "schema.sql").read_text(encoding="utf-8"))
    con.execute(
        "INSERT INTO regioes (nome, nome_normalizado, tipo, prioridade, osm_id, osm_type, latitude, longitude)"
        " VALUES ('Asa Sul', 'asa sul', 'place=suburb', 1, 1, 'node', %s, %s)", (LAT, LON),
    )
    yield con
    con.execute(f"DROP SCHEMA {schema} CASCADE")
    con.close()


def _lugar(con, nome, osm_id, metros=100.0, categoria="cafe", **tags):
    from busca import vetor_para_texto

    lat = LAT + metros / METROS_POR_GRAU_LAT
    con.execute(
        """
        INSERT INTO places (nome, categoria, tipo_categoria, cidade, latitude, longitude, geom,
                            osm_id, osm_type, osm_ids_origem, quantidade_origens, tags, embedding)
        VALUES (%s, %s, 'amenity', 'Brasília', %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                %s, 'node', '[]'::jsonb, 1, %s::jsonb, %s::vector)
        """,
        (nome, categoria, lat, LON, LON, lat, osm_id, json.dumps(tags), vetor_para_texto(_vetor())),
    )


def _grafo(con, **nlu):
    factory = lambda: nullcontext(con)  # noqa: E731 (todos os agentes na mesma conexao/schema)
    nlu.setdefault("spatial_constraints", {"target_region": "Asa Sul", "max_radius_km": 2.0})
    return build_graph(
        nlu=stub_nlu(**nlu),
        retrieval=RetrievalAgent(conexao_factory=factory, embedder=lambda t: _vetor()),
        validation=ValidationAgent(store=PostgresEvidenceStore(conexao_factory=factory)),
        communication=stub_communication,
    )


def _trilha(s):
    return [t.agent for t in s["agent_trace"]]


def test_aprovacao_direta_persiste_busca_e_auditoria(conexao):
    _lugar(conexao, "Cafe A", 1001, 100, wheelchair="yes", amenity="cafe")
    _lugar(conexao, "Cafe B", 1002, 200, wheelchair="yes", amenity="cafe")
    _lugar(conexao, "Cafe sem rampa", 1003, 50, wheelchair="no", amenity="cafe")
    _lugar(conexao, "Cafe sem info", 1004, 60, amenity="cafe")  # Opcao A: tag ausente nao passa

    s = run(_grafo(conexao), "texto livre", "req-real-1")

    assert _trilha(s) == [NLU, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert s["raw_query"] is None
    nomes = {e.place_name for e in s["evidence_records"]}
    assert nomes == {"Cafe A", "Cafe B"}
    assert s["final_response"] == "top-3 auditado"
    # rastro: 1 busca + 2 auditorias ligadas pelo consulta_id
    assert conexao.execute("SELECT count(*) FROM evidencias_busca").fetchone()[0] == 1
    ligadas = conexao.execute(
        "SELECT count(*) FROM evidencias_auditoria a JOIN evidencias_busca b USING (consulta_id) WHERE a.aprovado"
    ).fetchone()[0]
    assert ligadas == 2


def test_reconsulta_real_exclui_rejeitado_e_aprova_o_seguinte(conexao):
    # Pedido de madrugada: o Retrieval nao filtra horario, o Validation reprova quem fecha cedo.
    _lugar(conexao, "Cafe diurno", 2001, 50, wheelchair="yes", opening_hours="07:00-20:00", amenity="cafe")
    _lugar(conexao, "Cafe 24h", 2002, 400, wheelchair="yes", opening_hours="24/7", amenity="cafe")

    s = run(
        _grafo(conexao, temporal_constraints={"preferred_time_slot": "madrugada"}), "q", "req-real-2"
    )

    assert _trilha(s) == [NLU, RETRIEVAL, VALIDATION, RETRIEVAL, VALIDATION, COMMUNICATION]
    assert s["retry_count"] == 1
    assert [e.place_name for e in s["evidence_records"]] == ["Cafe 24h"]
    reprovado = conexao.execute(
        "SELECT place_name, motivos_rejeicao FROM evidencias_auditoria WHERE NOT aprovado"
    ).fetchone()
    assert reprovado[0] == "Cafe diurno" and any("Horário" in m for m in reprovado[1])


def test_sem_candidato_acessivel_abstem(conexao):
    _lugar(conexao, "Cafe sem rampa", 3001, 50, wheelchair="no", amenity="cafe")
    s = run(_grafo(conexao), "q", "req-real-3")
    assert _trilha(s) == [NLU, RETRIEVAL, COMMUNICATION]
    assert s["final_response"] == "abstencao"
    assert conexao.execute("SELECT count(*) FROM evidencias_auditoria").fetchone()[0] == 0


def test_regiao_desconhecida_pergunta_e_nao_busca(conexao):
    _lugar(conexao, "Cafe A", 4001, 50, wheelchair="yes", amenity="cafe")
    g = _grafo(conexao, spatial_constraints={"target_region": "Narnia", "max_radius_km": 2.0})
    s = run(g, "q", "req-real-4")
    assert "Narnia" in s["final_response"]
    assert conexao.execute("SELECT count(*) FROM evidencias_busca").fetchone()[0] == 0


def test_banco_fora_do_ar_vira_abstencao_segura(conexao):
    def factory():
        raise ConnectionError("db fora")

    g = build_graph(
        nlu=stub_nlu(spatial_constraints={"target_region": None, "max_radius_km": 2.0}),
        retrieval=RetrievalAgent(conexao_factory=factory, embedder=lambda t: _vetor()),
        validation=ValidationAgent(),
        communication=stub_communication,
    )
    s = run(g, "q", "req-real-5")
    assert s["error"] == "retrieval_agent: ConnectionError"
    assert s["final_response"] == "abstencao"
