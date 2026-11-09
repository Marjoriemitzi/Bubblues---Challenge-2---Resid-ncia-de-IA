"""Busca contra um Postgres real. Cada teste usa um schema temporario proprio.

Precisa do banco no ar (docker compose up -d) e de um .env com DB_PASSWORD.
Sem banco, os testes sao pulados.
"""

import json
import math
import uuid
from pathlib import Path

import psycopg
import pytest

from busca import DIMENSAO_EMBEDDING, FATOR_AMPLIACAO_RAIO, buscar, conectar, vetor_para_texto
from score import PESOS, SEM_DADO, validar_evidencia

ARQUIVO_SCHEMA = Path(__file__).parent.parent / "db" / "schema.sql"

LAT = -15.7942
LON = -47.8825
METROS_POR_GRAU_LAT = 110_600


def eixo(indice, sinal=1.0):
    vetor = [0.0] * DIMENSAO_EMBEDDING
    vetor[indice] = sinal
    return vetor


@pytest.fixture
def conexao():
    try:
        con = conectar()
    except (psycopg.OperationalError, RuntimeError) as erro:
        pytest.skip(f"Banco indisponivel: {erro}")

    schema = f"teste_{uuid.uuid4().hex}"
    con.execute(f"CREATE SCHEMA {schema}")
    con.execute(f"SET search_path TO {schema}, public")
    con.execute(ARQUIVO_SCHEMA.read_text(encoding="utf-8"))
    yield con
    con.execute(f"DROP SCHEMA {schema} CASCADE")
    con.close()


def inserir(
    con,
    nome,
    metros=0.0,
    categoria="cafe",
    tipo_categoria="amenity",
    embedding=None,
    tags=None,
    osm_type="node",
    osm_id=None,
    nota_google=None,
    nota_app=None,
):
    latitude = LAT + metros / METROS_POR_GRAU_LAT
    osm_id = osm_id if osm_id is not None else abs(hash(nome)) % 10**9
    vetor = vetor_para_texto(eixo(0) if embedding is None else embedding) if embedding != "nulo" else None
    con.execute(
        """
        INSERT INTO places (
            nome, categoria, tipo_categoria, cidade, latitude, longitude, geom,
            osm_id, osm_type, osm_ids_origem, quantidade_origens,
            tags, embedding, nota_google, nota_app
        )
        VALUES (
            %s, %s, %s, 'Brasília', %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
            %s, %s, '[]'::jsonb, 1, %s::jsonb, %s::vector, %s, %s
        )
        """,
        (
            nome, categoria, tipo_categoria, latitude, LON, LON, latitude,
            osm_id, osm_type, json.dumps(tags or {}), vetor, nota_google, nota_app,
        ),
    )


def executar(con, **opcoes):
    opcoes.setdefault("embedding_consulta", eixo(0))
    return buscar(con, LAT, LON, **opcoes)


def nomes(registro):
    return [r["local"]["nome"] for r in registro["resultados"]]


def fator(resultado, nome):
    return next(f for f in resultado["fatores"] if f["nome"] == nome)


def test_devolve_top_k_ordenado_com_decomposicao(conexao):
    for indice, metros in enumerate([100, 200, 300, 400]):
        inserir(conexao, f"L{indice}", metros=metros)

    registro = executar(conexao, k=3)

    assert nomes(registro) == ["L0", "L1", "L2"]
    assert registro["status"] == "completo"
    totais = [r["score_total"] for r in registro["resultados"]]
    assert totais == sorted(totais, reverse=True)
    for resultado in registro["resultados"]:
        assert [f["nome"] for f in resultado["fatores"]] == list(PESOS)
        soma = math.fsum(f["contribuicao"] for f in resultado["fatores"])
        assert math.isclose(soma, resultado["score_total"], abs_tol=1e-9)
        assert 0.0 <= resultado["score_total"] <= 1.0
        assert all(0.0 <= f["valor"] <= 1.0 for f in resultado["fatores"])


def test_filtro_por_raio(conexao):
    inserir(conexao, "dentro", metros=500)
    inserir(conexao, "fora", metros=1500)

    registro = executar(conexao, raio_m=1000, k=1)

    assert nomes(registro) == ["dentro"]
    assert registro["raio"]["ampliado"] is False


def test_filtro_por_tipo(conexao):
    inserir(conexao, "cafe", metros=100, categoria="cafe")
    inserir(conexao, "parque", metros=100, categoria="park", tipo_categoria="leisure")
    inserir(conexao, "museu", metros=100, categoria="museum", tipo_categoria="tourism")

    assert nomes(executar(conexao, tipos=["park"], k=1)) == ["parque"]
    assert set(nomes(executar(conexao, tipos=[" Park ", "museum"], k=2))) == {"parque", "museu"}


def test_cosseno_vai_de_identico_a_oposto(conexao):
    inserir(conexao, "identico", metros=100, embedding=eixo(0))
    inserir(conexao, "ortogonal", metros=100, embedding=eixo(1))
    inserir(conexao, "oposto", metros=100, embedding=eixo(0, -1.0))

    registro = executar(conexao, k=3)
    valores = {
        r["local"]["nome"]: fator(r, "similaridade")["valor"] for r in registro["resultados"]
    }

    assert nomes(registro)[0] == "identico"
    assert math.isclose(valores["identico"], 1.0, abs_tol=1e-6)
    assert math.isclose(valores["ortogonal"], 0.0, abs_tol=1e-6)
    assert valores["oposto"] == 0.0


def test_similaridade_pesa_mais_que_pequena_diferenca_de_distancia(conexao):
    inserir(conexao, "perto_sem_afinidade", metros=50, embedding=eixo(1))
    inserir(conexao, "longe_com_afinidade", metros=800, embedding=eixo(0))

    assert nomes(executar(conexao, k=2))[0] == "longe_com_afinidade"


def test_lugar_sem_embedding_nao_e_candidato(conexao):
    inserir(conexao, "com", metros=100)
    inserir(conexao, "sem", metros=100, embedding="nulo")

    assert nomes(executar(conexao, k=2)) == ["com"]


def test_desempate_deterministico_pelo_id_osm(conexao):
    inserir(conexao, "way1", metros=100, osm_type="way", osm_id=1)
    inserir(conexao, "node9", metros=100, osm_type="node", osm_id=9)
    inserir(conexao, "node2", metros=100, osm_type="node", osm_id=2)

    primeira = executar(conexao, k=3)
    segunda = executar(conexao, k=3)

    assert nomes(primeira) == ["node2", "node9", "way1"]
    assert primeira["resultados"] == segunda["resultados"]


def test_amplia_o_raio_uma_unica_vez(conexao):
    inserir(conexao, "A", metros=100)
    inserir(conexao, "B", metros=1500)
    inserir(conexao, "alem_da_ampliacao", metros=2500)

    registro = executar(conexao, raio_m=1000, k=5)

    assert nomes(registro) == ["A", "B"]
    assert registro["raio"] == {
        "solicitado_m": 1000,
        "final_m": 1000 * FATOR_AMPLIACAO_RAIO,
        "ampliado": True,
    }
    assert registro["status"] == "parcial"


def test_nao_amplia_quando_ja_ha_k_resultados(conexao):
    inserir(conexao, "A", metros=100)
    inserir(conexao, "B", metros=200)
    inserir(conexao, "C", metros=1500)

    registro = executar(conexao, raio_m=1000, k=2)

    assert registro["raio"]["ampliado"] is False
    assert registro["raio"]["final_m"] == 1000
    assert "C" not in nomes(registro)


def test_sem_resultado_mesmo_ampliando(conexao):
    inserir(conexao, "muito_longe", metros=9000)

    registro = executar(conexao, raio_m=1000, k=3)

    assert registro["resultados"] == []
    assert registro["status"] == "sem_resultado"
    assert registro["raio"]["ampliado"] is True


def test_evidencia_gravada_e_completa(conexao):
    inserir(
        conexao,
        "Cafe Acessivel",
        metros=300,
        osm_type="way",
        osm_id=777,
        tags={"amenity": "cafe", "wheelchair": "yes", "phone": "123"},
        nota_google=4.0,
        nota_app=5.0,
    )

    registro = executar(
        conexao, k=1, etiquetas_desejadas={"wheelchair": "yes"}, texto_consulta="cafe acessivel"
    )

    linha = conexao.execute(
        "SELECT registro FROM evidencias_busca WHERE consulta_id = %s", (registro["consulta_id"],)
    ).fetchone()
    assert linha is not None
    gravado = linha[0]
    assert gravado == json.loads(json.dumps(registro))
    validar_evidencia(gravado)

    assert gravado["consulta"]["texto"] == "cafe acessivel"
    resultado = gravado["resultados"][0]
    assert resultado["local"]["nome"] == "Cafe Acessivel"
    assert math.isclose(resultado["local"]["distancia_m"], 300, abs_tol=5)
    assert resultado["osm_url"] == "https://www.openstreetmap.org/way/777"
    assert resultado["etiquetas_usadas"] == {"amenity": "cafe", "wheelchair": "yes"}
    assert fator(resultado, "compatibilidade") == {
        "nome": "compatibilidade",
        "valor": 1.0,
        "peso": PESOS["compatibilidade"],
        "contribuicao": PESOS["compatibilidade"],
        "origem": "etiquetas_osm",
    }
    assert fator(resultado, "reputacao")["origem"] == "nota_google_e_app"


def test_fatores_sem_dado_ficam_marcados(conexao):
    inserir(conexao, "sem_notas", metros=100)

    resultado = executar(conexao, k=1)["resultados"][0]

    assert fator(resultado, "reputacao")["origem"] == SEM_DADO
    assert fator(resultado, "compatibilidade")["origem"] == SEM_DADO


def test_consulta_sem_resultado_tambem_gera_evidencia(conexao):
    registro = executar(conexao, k=1)

    total = conexao.execute(
        "SELECT count(*) FROM evidencias_busca WHERE consulta_id = %s", (registro["consulta_id"],)
    ).fetchone()[0]
    assert total == 1


@pytest.mark.parametrize(
    "ajuste",
    [
        {"embedding_consulta": [1.0, 0.0]},
        {"embedding_consulta": [0.0] * DIMENSAO_EMBEDDING},
        {"embedding_consulta": [float("nan")] * DIMENSAO_EMBEDDING},
        {"raio_m": 0},
        {"k": 0},
    ],
)
def test_parametros_invalidos_sao_recusados(conexao, ajuste):
    with pytest.raises(ValueError):
        executar(conexao, **ajuste)
