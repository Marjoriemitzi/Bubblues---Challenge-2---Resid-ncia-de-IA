"""Regioes: parse/normalizacao (sem banco) e resolucao de nome (schema temporario no Postgres)."""

import uuid
from pathlib import Path

import pytest

from regioes import buscar_regioes, elementos_para_linhas, normalizar_nome, resolver_regiao

ARQUIVO_SCHEMA = Path(__file__).parent.parent / "db" / "schema.sql"


def _el(tipo, id_, nome, lat=-15.8, lon=-47.9, center=False, **tags):
    el = {"type": tipo, "id": id_, "tags": {"name": nome, **tags}}
    el.update({"center": {"lat": lat, "lon": lon}} if center else {"lat": lat, "lon": lon})
    return el


def test_normalizar_nome():
    assert normalizar_nome("  Águas Claras (Norte) ") == "aguas claras norte"
    assert normalizar_nome('Setor "O"') == "setor o"
    assert normalizar_nome("Plano Piloto - Asa Norte") == "plano piloto asa norte"
    assert normalizar_nome("") == ""


def test_parse_classifica_e_descarta():
    elementos = [
        _el("node", 1, "Asa Sul", place="suburb"),
        _el("relation", 2, "Guará", center=True, boundary="administrative", admin_level="8"),
        _el("node", 3, "Sem classe", amenity="cafe"),
        _el("node", 4, "", place="suburb"),
        _el("node", 5, "Sem coord", place="suburb") | {"lat": None, "lon": None},
        _el("relation", 6, "Parque", center=True, boundary="administrative", admin_level="6"),
        _el("node", 1, "Asa Sul", place="suburb"),  # duplicado
    ]
    linhas = elementos_para_linhas(elementos)
    assert [(l["nome"], l["tipo"], l["prioridade"]) for l in linhas] == [
        ("Asa Sul", "place=suburb", 1),
        ("Guará", "admin_level=8", 4),
    ]
    assert linhas[0]["nome_normalizado"] == "asa sul"


@pytest.fixture
def conexao():
    from busca import conectar

    try:
        con = conectar()
    except Exception as erro:
        pytest.skip(f"Banco indisponivel: {erro}")
    schema = f"teste_{uuid.uuid4().hex}"
    con.execute(f"CREATE SCHEMA {schema}")
    con.execute(f"SET search_path TO {schema}, public")
    con.execute(ARQUIVO_SCHEMA.read_text(encoding="utf-8"))
    yield con
    con.execute(f"DROP SCHEMA {schema} CASCADE")
    con.close()


@pytest.fixture
def regioes(conexao):
    from load_regioes import carregar

    carregar(
        conexao,
        elementos_para_linhas(
            [
                _el("node", 1, "Asa Sul", -15.81, -47.90, place="suburb"),
                _el("node", 2, "Guará", -15.83, -47.98, place="quarter"),
                _el("relation", 3, "Guará", -15.80, -47.97, center=True, boundary="administrative", admin_level="8"),
                _el("node", 4, "Plano Piloto - Asa Norte", -15.76, -47.88, place="suburb"),
                _el("node", 5, "Águas Claras", -15.84, -48.03, place="city"),
            ]
        ),
    )
    return conexao


def test_exata_ignora_acento_e_caixa(regioes):
    assert resolver_regiao(regioes, "aguas claras") == (-15.84, -48.03, "Águas Claras")


def test_nome_repetido_usa_prioridade(regioes):
    # place=quarter (3) vence admin_level=8 (4)
    assert resolver_regiao(regioes, "Guará")[:2] == (-15.83, -47.98)


def test_nome_contido_no_da_regiao(regioes):
    assert resolver_regiao(regioes, "Asa Norte")[2] == "Plano Piloto - Asa Norte"


def test_regiao_contida_no_texto_pedido(regioes):
    assert resolver_regiao(regioes, "perto da Asa Sul em Brasília")[2] == "Asa Sul"


def test_desconhecida_ou_vazia_devolve_none(regioes):
    assert resolver_regiao(regioes, "Narnia") is None
    assert resolver_regiao(regioes, "   ") is None
    assert resolver_regiao(regioes, None) is None


def test_buscar_regioes_devolve_varios_sem_repetir(regioes):
    nomes = [(r["nome"], r["tipo"]) for r in buscar_regioes(regioes, "Guará")]
    assert nomes == [("Guará", "place=quarter"), ("Guará", "admin_level=8")]  # prioridade


def test_buscar_regioes_respeita_limite_e_ordem_de_especificidade(regioes):
    assert {r["nome"] for r in buscar_regioes(regioes, "asa")} == {"Asa Sul", "Plano Piloto - Asa Norte"}
    achados = buscar_regioes(regioes, "Asa Norte")
    assert achados[0]["nome"] == "Plano Piloto - Asa Norte"
    assert len(buscar_regioes(regioes, "Guará", limite=1)) == 1
    assert buscar_regioes(regioes, "Narnia") == [] and buscar_regioes(regioes, None) == []
