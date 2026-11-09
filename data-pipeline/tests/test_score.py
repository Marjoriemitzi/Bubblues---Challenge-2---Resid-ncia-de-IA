"""Integridade do score e da evidencia. Nao precisa de banco."""

import copy
import itertools
import math

import pytest

from score import (
    PESOS,
    SEM_DADO,
    VALOR_NEUTRO,
    calcular_score,
    chave_ordenacao,
    etiquetas_usadas,
    fator_compatibilidade,
    fator_distancia,
    fator_reputacao,
    link_osm,
    validar_evidencia,
)


def registro_valido():
    fatores, total = calcular_score(0.8, 500.0, 4.0, 5.0, {"wheelchair": "yes"}, {"wheelchair": "yes"})
    return {
        "consulta_id": "abc",
        "criada_em": "2026-11-09T12:00:00+00:00",
        "consulta": {"texto": "cafe calmo"},
        "raio": {"solicitado_m": 1000, "final_m": 1000, "ampliado": False},
        "status": "completo",
        "pesos": PESOS,
        "resultados": [
            {
                "posicao": 1,
                "local": {
                    "place_id": 1,
                    "nome": "Cafe",
                    "categoria": "cafe",
                    "latitude": -15.79,
                    "longitude": -47.88,
                    "distancia_m": 500.0,
                },
                "osm_url": link_osm("node", 123),
                "etiquetas_usadas": {"amenity": "cafe", "wheelchair": "yes"},
                "fatores": fatores,
                "score_total": total,
            }
        ],
    }


def test_pesos_somam_um():
    assert math.isclose(math.fsum(PESOS.values()), 1.0, abs_tol=1e-12)


def test_contribuicoes_somam_o_total_e_valores_ficam_entre_0_e_1():
    similaridades = [-1.0, -0.2, 0.0, 0.37, 1.0, 1.0000000002, float("nan")]
    distancias = [0.0, 1.0, 999.5, 5000.0, 1e7]
    notas = [None, 0, 3.3, 5]
    etiquetas = [{}, {"wheelchair": "yes"}, {"wheelchair": "yes", "cuisine": "sushi"}]
    tags = {"wheelchair": "no", "cuisine": "sushi;japanese"}

    for sim, dist, google, app, desejadas in itertools.product(
        similaridades, distancias, notas, notas, etiquetas
    ):
        fatores, total = calcular_score(sim, dist, google, app, tags, desejadas)
        assert [f["nome"] for f in fatores] == list(PESOS)
        assert math.isclose(math.fsum(f["contribuicao"] for f in fatores), total, abs_tol=1e-9)
        assert 0.0 <= total <= 1.0
        for fator in fatores:
            assert 0.0 <= fator["valor"] <= 1.0
            assert 0.0 <= fator["contribuicao"] <= 1.0
            assert math.isclose(fator["contribuicao"], fator["valor"] * fator["peso"], abs_tol=1e-12)


def test_similaridade_negativa_e_nan_viram_zero():
    assert calcular_score(-0.5, 0, None, None, {}, {})[0][0]["valor"] == 0.0
    assert calcular_score(float("nan"), 0, None, None, {}, {})[0][0]["valor"] == 0.0


def test_distancia_usa_a_curva_do_benchmark():
    assert fator_distancia(0) == 1.0
    assert math.isclose(fator_distancia(5000), 0.5)
    assert fator_distancia(1000) > fator_distancia(2000)


def test_reputacao_combina_google_e_app():
    valor, origem = fator_reputacao(4.0, 5.0)
    assert math.isclose(valor, (0.4 * 4 + 0.6 * 5) / 5)
    assert origem == "nota_google_e_app"


def test_reputacao_com_uma_so_nota():
    assert fator_reputacao(4.0, None) == (0.8, "nota_google")
    assert fator_reputacao(None, 2.5) == (0.5, "nota_app")


def test_reputacao_sem_nota_fica_neutra_e_marcada():
    assert fator_reputacao(None, None) == (VALOR_NEUTRO, SEM_DADO)


def test_compatibilidade_atende_e_contraria():
    tags = {"wheelchair": "yes", "internet_access": "wlan"}
    assert fator_compatibilidade(tags, {"wheelchair": "yes"}) == (1.0, "etiquetas_osm")
    assert fator_compatibilidade(tags, {"wheelchair": "no"}) == (0.0, "etiquetas_osm")


def test_compatibilidade_aceita_valor_em_lista_osm():
    assert fator_compatibilidade({"cuisine": "sushi;Japanese"}, {"cuisine": "japanese"})[0] == 1.0


def test_compatibilidade_etiqueta_ausente_conta_como_neutra():
    valor, origem = fator_compatibilidade({"wheelchair": "yes"}, {"wheelchair": "yes", "cuisine": "x"})
    assert valor == (1.0 + VALOR_NEUTRO) / 2
    assert origem == "etiquetas_osm"


def test_compatibilidade_sem_dado():
    assert fator_compatibilidade({"wheelchair": "yes"}, {}) == (VALOR_NEUTRO, SEM_DADO)
    assert fator_compatibilidade({}, {"wheelchair": "yes"}) == (VALOR_NEUTRO, SEM_DADO)


def test_desempate_score_depois_distancia_depois_id_osm():
    itens = [
        (0.7, 100.0, "way", 1),
        (0.7, 100.0, "node", 9),
        (0.7, 100.0, "node", 2),
        (0.7, 50.0, "way", 5),
        (0.9, 900.0, "way", 7),
    ]
    esperado = [
        (0.9, 900.0, "way", 7),
        (0.7, 50.0, "way", 5),
        (0.7, 100.0, "node", 2),
        (0.7, 100.0, "node", 9),
        (0.7, 100.0, "way", 1),
    ]
    for permutacao in itertools.permutations(itens):
        assert sorted(permutacao, key=lambda i: chave_ordenacao(*i)) == esperado


def test_ruido_de_ponto_flutuante_nao_decide_empate():
    assert chave_ordenacao(0.3, 1.0, "node", 1)[0] == chave_ordenacao(0.1 + 0.2, 1.0, "node", 1)[0]


def test_link_osm():
    assert link_osm("way", 42) == "https://www.openstreetmap.org/way/42"


def test_etiquetas_usadas_tem_tipo_e_pedidas_existentes():
    usadas = etiquetas_usadas(
        "amenity", "cafe", {"wheelchair": "yes", "phone": "1"}, {"wheelchair": "yes", "cuisine": "x"}
    )
    assert usadas == {"amenity": "cafe", "wheelchair": "yes"}


def test_registro_valido_passa():
    validar_evidencia(registro_valido())


def test_registro_sem_resultados_e_valido():
    registro = registro_valido()
    registro["resultados"] = []
    validar_evidencia(registro)


def corromper_total(r):
    r["resultados"][0]["score_total"] += 0.01


def corromper_contribuicao(r):
    r["resultados"][0]["fatores"][0]["contribuicao"] += 0.01


def corromper_valor(r):
    r["resultados"][0]["fatores"][1]["valor"] = 1.5


def corromper_peso(r):
    r["resultados"][0]["fatores"][2]["peso"] = 0.9


def remover_fator(r):
    r["resultados"][0]["fatores"].pop()


def remover_link(r):
    del r["resultados"][0]["osm_url"]


def link_invalido(r):
    r["resultados"][0]["osm_url"] = "https://exemplo.com/node/1"


def remover_etiquetas(r):
    r["resultados"][0]["etiquetas_usadas"] = {}


def remover_nome_do_local(r):
    r["resultados"][0]["local"]["nome"] = None


def remover_origem_do_fator(r):
    del r["resultados"][0]["fatores"][0]["origem"]


def posicao_errada(r):
    r["resultados"][0]["posicao"] = 2


def remover_raio_final(r):
    del r["raio"]["final_m"]


CORRUPCOES = [
    corromper_total,
    corromper_contribuicao,
    corromper_valor,
    corromper_peso,
    remover_fator,
    remover_link,
    link_invalido,
    remover_etiquetas,
    remover_nome_do_local,
    remover_origem_do_fator,
    posicao_errada,
    remover_raio_final,
]


def test_validacao_rejeita_registro_corrompido():
    for corromper in CORRUPCOES:
        registro = copy.deepcopy(registro_valido())
        corromper(registro)
        with pytest.raises(ValueError):
            validar_evidencia(registro)
