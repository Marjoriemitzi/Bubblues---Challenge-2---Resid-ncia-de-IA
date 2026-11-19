"""Testes TDD nos seams publicos definidos pelos ADRs 0002 e 0003 e GLOSSARY.md.

Compativel tanto com `python3 -m unittest` quanto com `pytest`.
"""

import unittest
from unittest.mock import MagicMock

from busca import DIMENSAO_EMBEDDING, buscar
from encontro import (
    alocar_em_slot,
    apurar_presenca,
    avaliar_checkin_final,
    recomendar_zero_turn,
)
from score import atende_barreiras


def _vetor_unitario():
    v = [0.0] * DIMENSAO_EMBEDDING
    v[0] = 1.0
    return v


class Seam1BarreirasTest(unittest.TestCase):
    """Seam 1 (ADR-0002): Hard Filters de Acessibilidade Fisica e Tolerancia Sensorial."""

    def test_bloqueia_local_com_wheelchair_no_quando_acessibilidade_exigida(self):
        self.assertFalse(
            atende_barreiras(
                tags={"wheelchair": "no", "cuisine": "coffee"},
                etiquetas_desejadas={"wheelchair": "yes"},
            )
        )

    def test_aceita_local_so_com_wheelchair_yes_explicito(self):
        self.assertTrue(
            atende_barreiras(
                tags={"wheelchair": "yes"},
                etiquetas_desejadas={"wheelchair": "yes"},
            )
        )

    def test_bloqueia_wheelchair_ausente_ou_limitado_quando_exigido(self):
        for tags in ({"cuisine": "coffee"}, {"wheelchair": "limited"}, {"wheelchair": ""}):
            with self.subTest(tags=tags):
                self.assertFalse(
                    atende_barreiras(tags=tags, etiquetas_desejadas={"wheelchair": "yes"})
                )

    def test_wheelchair_ausente_passa_quando_acessibilidade_nao_e_exigida(self):
        self.assertTrue(atende_barreiras(tags={"cuisine": "coffee"}, etiquetas_desejadas={}))

    def test_bloqueia_local_com_ruido_alto_quando_tolerancia_sensorial_baixa_ou_moderada(self):
        self.assertFalse(
            atende_barreiras(
                tags={"noise_level": "alto"},
                etiquetas_desejadas={},
                tolerancia_ruido="baixo",
            )
        )
        self.assertFalse(
            atende_barreiras(
                tags={"nivel_ruido": "Alto"},
                etiquetas_desejadas={},
                tolerancia_sensorial="moderado",
            )
        )
        self.assertTrue(
            atende_barreiras(
                tags={"noise_level": "moderado"},
                etiquetas_desejadas={},
                tolerancia_ruido="baixo",
            )
        )

    def test_busca_exclui_candidatos_que_violam_barreiras_e_registra_tolerancia(self):
        candidatos_banco = [
            {
                "place_id": 1,
                "nome": "Cafe Escadaria Barulhento",
                "categoria": "cafe",
                "tipo_categoria": "amenity",
                "latitude": -15.79,
                "longitude": -47.88,
                "osm_id": 101,
                "osm_type": "node",
                "tags": {"wheelchair": "no", "noise_level": "alto"},
                "nota_google": 4.9,
                "nota_app": 5.0,
                "distancia_m": 50.0,
                "similaridade": 0.99,
            },
            {
                "place_id": 2,
                "nome": "Cafe Plano Silencioso",
                "categoria": "cafe",
                "tipo_categoria": "amenity",
                "latitude": -15.80,
                "longitude": -47.89,
                "osm_id": 102,
                "osm_type": "node",
                "tags": {"wheelchair": "yes", "noise_level": "baixo"},
                "nota_google": 4.6,
                "nota_app": 4.8,
                "distancia_m": 400.0,
                "similaridade": 0.85,
            },
        ]
        cursor_mock = MagicMock()
        cursor_mock.fetchall.return_value = candidatos_banco
        conexao_mock = MagicMock()
        conexao_mock.cursor.return_value.__enter__.return_value = cursor_mock

        registro = buscar(
            conexao_mock,
            latitude=-15.79,
            longitude=-47.88,
            embedding_consulta=_vetor_unitario(),
            raio_m=1000,
            k=1,
            etiquetas_desejadas={"wheelchair": "yes"},
            tolerancia_ruido="baixo",
        )

        nomes_retornados = [r["local"]["nome"] for r in registro["resultados"]]
        self.assertEqual(nomes_retornados, ["Cafe Plano Silencioso"])
        self.assertEqual(registro["consulta"]["tolerancia_sensorial"], "baixo")
        _, params_sql = cursor_mock.execute.call_args[0]
        self.assertTrue(params_sql["exigir_acessibilidade"])
        self.assertTrue(params_sql["bloquear_ruido_alto"])


class Seam2QuorumEPautaTest(unittest.TestCase):
    """Seam 2 (ADR-0003): Slot de Pareamento (3 a 8 Membros), Quorum Minimo >= 3 e Pauta Quebra-Gelo."""

    def test_aloca_membros_ate_limite_de_8_e_abre_novo_slot_quando_cheio(self):
        slots = []
        for i in range(1, 10):
            alocar_em_slot(
                slots,
                membro={"id": f"M{i}", "afinidades": ["livros", "cafe"]},
                local_id="LOC-01",
                turno="tarde",
            )
        # Re-alocar um membro ja presente no slot cheio nao deve duplicar para o segundo slot.
        slot_repetido = alocar_em_slot(
            slots,
            membro={"id": "M1", "afinidades": ["livros", "cafe"]},
            local_id="LOC-01",
            turno="tarde",
        )
        self.assertEqual(slot_repetido["slot_id"], slots[0]["slot_id"])
        self.assertEqual(len(slots), 2)
        self.assertEqual(len(slots[0]["membros"]), 8)
        self.assertEqual(slots[0]["status"], "completo")
        self.assertEqual(len(slots[1]["membros"]), 1)
        self.assertEqual(slots[1]["status"], "em_formacao")

    def test_aloca_membro_por_afinidade_compativel_e_integra_com_checkin_final(self):
        slots = []
        alocar_em_slot(slots, {"id": "M1", "afinidades": ["xadrez"]}, "LOC-02", "manha")
        alocar_em_slot(slots, {"id": "M2", "afinidades": ["ceramica"]}, "LOC-02", "manha")
        alocar_em_slot(slots, {"id": "M3", "afinidades": ["xadrez"]}, "LOC-02", "manha")
        alocar_em_slot(slots, {"id": "M4", "afinidades": ["xadrez"]}, "LOC-02", "manha")
        self.assertEqual(len(slots), 2)
        self.assertEqual(len(slots[0]["membros"]), 3)

        resultado = avaliar_checkin_final(
            membros_alocados=slots[0]["membros"],
            confirmados_checkin=slots[0]["membros"],
        )
        self.assertTrue(resultado["encontro_confirmado"])
        self.assertEqual(len(resultado["pauta_quebra_gelo"]), 3)
        self.assertTrue(any("xadrez" in t for t in resultado["pauta_quebra_gelo"]))

    def test_checkin_final_cancela_preventivamente_se_menos_de_3_confirmados(self):
        resultado = avaliar_checkin_final(
            membros_alocados=["M1", "M2", "M3"],
            confirmados_checkin=["M1", "M2"],
            afinidades_grupo=["literatura", "cafes especiais", "cinema"],
        )
        self.assertFalse(resultado["encontro_confirmado"])
        self.assertEqual(resultado["status"], "cancelado_quorum_insuficiente")
        self.assertEqual(resultado["quorum_minimo"], 3)
        self.assertEqual(resultado["pauta_quebra_gelo"], [])

    def test_checkin_final_confirma_e_gera_3_topicos_quebra_gelo_quando_atinge_quorum(self):
        resultado_insuficiente = avaliar_checkin_final(
            membros_alocados=["M1", "M2", "M3", "M4", "M5", "M6"],
            confirmados_checkin=["M1", "M2", "M3"],
            afinidades_grupo=["livros", "musica", "viagens"],
        )
        self.assertFalse(resultado_insuficiente["encontro_confirmado"])
        self.assertEqual(resultado_insuficiente["quorum_minimo"], 4)

        resultado_ok = avaliar_checkin_final(
            membros_alocados=["M1", "M2", "M3", "M4", "M5", "M6"],
            confirmados_checkin=["M1", "M2", "M3", "M4"],
            afinidades_grupo=["ficcao cientifica", "cafes tranquilos", "fotografia"],
        )
        self.assertTrue(resultado_ok["encontro_confirmado"])
        self.assertEqual(resultado_ok["status"], "confirmado")
        self.assertEqual(len(resultado_ok["pauta_quebra_gelo"]), 3)
        self.assertTrue(any("ficcao cientifica" in t for t in resultado_ok["pauta_quebra_gelo"]))


class Seam3DesistenciaENoShowTest(unittest.TestCase):
    """Seam 3 (ADR-0003): Isencao em Desistencia Previa vs Penalidade em No-Show pos Check-in Final."""

    def test_distingue_desistencia_previa_isenta_de_no_show_penalizado(self):
        # M5 desistiu antes da janela; M6 confirmou e cancelou ainda dentro da janela (tambem isento).
        apuracao = apurar_presenca(
            confirmados_checkin=["M1", "M2", "M3", "M4", "M6"],
            desistencias_previas=["M5", "M6"],
            presentes=["M1", "M2", "M3"],
        )
        self.assertEqual(apuracao["presentes"], ["M1", "M2", "M3"])
        self.assertEqual(apuracao["desistencias_previas_isentas"], ["M5", "M6"])
        self.assertEqual(apuracao["no_shows_penalizados"], ["M4"])
        self.assertEqual(apuracao["delta_compromisso"]["M5"], 0)
        self.assertEqual(apuracao["delta_compromisso"]["M6"], 0)
        self.assertLess(apuracao["delta_compromisso"]["M4"], 0)
        self.assertGreater(apuracao["delta_compromisso"]["M1"], 0)


class Seam4ZeroTurnFallbackTest(unittest.TestCase):
    """Seam 4 (ADR-0003): Recomendacao Proativa Zero-Turn diversificada respeitando barreiras do Perfil Base."""

    def test_retorna_3_locais_verificados_de_categorias_distintas_respeitando_barreiras(self):
        perfil_dona_helena = {
            "acessibilidade_fisica": True,
            "tolerancia_sensorial": "baixo",
            "interesses": ["leitura", "natureza", "cultura"],
        }
        catalogo = [
            {
                "place_id": "LOC-NAO-VERIFICADO",
                "nome": "Local Nao Verificado",
                "categoria": "livraria",
                "tags": {"wheelchair": "yes", "noise_level": "baixo"},
                "nota_google": 5.0,
                "nota_app": 5.0,
                "distancia_m": 50.0,
            },
            {
                "place_id": "LOC-INACESSIVEL",
                "nome": "Cafe Sem Rampa",
                "categoria": "cafe",
                "is_public_verified": True,
                "tags": {"wheelchair": "no", "noise_level": "baixo"},
                "nota_google": 5.0,
                "nota_app": 5.0,
                "distancia_m": 100.0,
            },
            {
                "place_id": "LOC-BARULHENTO",
                "nome": "Bar Rock Alto",
                "categoria": "bar",
                "is_public_verified": True,
                "tags": {"wheelchair": "yes", "noise_level": "alto"},
                "nota_google": 5.0,
                "nota_app": 5.0,
                "distancia_m": 100.0,
            },
            {
                "place_id": "LOC-CAFE-1",
                "nome": "Ernesto Cafes Especiais",
                "categoria": "cafe",
                "is_public_verified": True,
                "tags": {"wheelchair": "yes", "noise_level": "baixo"},
                "etiquetas": ["leitura"],
                "nota_google": 4.7,
                "nota_app": 4.8,
                "distancia_m": 500.0,
            },
            {
                "place_id": "LOC-CAFE-2",
                "nome": "Sephinah Casa de Cha",
                "categoria": "cafe",
                "is_public_verified": True,
                "tags": {"wheelchair": "yes", "noise_level": "baixo"},
                "nota_google": 4.6,
                "nota_app": 4.9,
                "distancia_m": 400.0,
            },
            {
                "place_id": "LOC-PARQUE",
                "nome": "Parque da Cidade",
                "categoria": "park",
                "is_public_verified": True,
                "tags": {"wheelchair": "yes", "noise_level": "moderado"},
                "etiquetas": ["natureza"],
                "nota_google": 4.8,
                "nota_app": 4.7,
                "distancia_m": 800.0,
            },
            {
                "place_id": "LOC-CULTURA",
                "nome": "CCBB Brasilia",
                "categoria": "cultural_center",
                "is_public_verified": True,
                "tags": {"wheelchair": "yes", "noise_level": "baixo"},
                "etiquetas": ["cultura"],
                "nota_google": 4.9,
                "nota_app": 4.8,
                "distancia_m": 1200.0,
            },
        ]

        cards = recomendar_zero_turn(perfil_dona_helena, catalogo, k=3)
        self.assertEqual(len(cards), 3)
        ids = [c["place_id"] for c in cards]
        self.assertNotIn("LOC-NAO-VERIFICADO", ids)
        self.assertNotIn("LOC-INACESSIVEL", ids)
        self.assertNotIn("LOC-BARULHENTO", ids)
        self.assertIn("LOC-CAFE-1", ids)
        categorias = {c["categoria"] for c in cards}
        self.assertEqual(len(categorias), 3)


if __name__ == "__main__":
    unittest.main()
