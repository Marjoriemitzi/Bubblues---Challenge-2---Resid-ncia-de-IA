"""Horario: parser do opening_hours do OSM, extracao do que o pedido exige e a avaliacao (so rejeita com evidencia)."""

import pytest

from orchestrator.horario import avaliar_horario, extrair_exigencias, parse_opening_hours

H = lambda h, m=0: h * 60 + m  # noqa: E731


# ------------------------------------------------------------------ parser do OSM
def test_24_7_e_faixa_simples_valem_todos_os_dias():
    assert parse_opening_hours("24/7") == {d: [(0, 1440)] for d in range(7)}
    ag = parse_opening_hours("09:00-17:00")
    assert all(ag[d] == [(H(9), H(17))] for d in range(7))
    assert parse_opening_hours("09:00 - 17:00")[0] == [(H(9), H(17))]


def test_dias_e_intervalos_de_dias():
    ag = parse_opening_hours("Mo-Fr 08:15-17:30")
    assert ag[0] == ag[4] == [(H(8, 15), H(17, 30))] and ag[5] == ag[6] == []
    ag = parse_opening_hours("Mo,We 09:00-12:00; Sa-Su 10:00-14:00")
    assert ag[0] and not ag[1] and ag[2] and ag[5] and ag[6]


def test_varias_regras_o_dia_seguinte_sobrescreve():
    ag = parse_opening_hours("Mo-Su 09:00-19:00; Su 10:00-14:00")
    assert ag[0] == [(H(9), H(19))] and ag[6] == [(H(10), H(14))]


def test_varias_faixas_no_mesmo_dia():
    ag = parse_opening_hours("Mo-Fr 08:00-12:00,14:00-18:00")
    assert ag[1] == [(H(8), H(12)), (H(14), H(18))]
    assert parse_opening_hours("Mo-Fr 08:00-12:00, 14:00-18:00")[1] == [(H(8), H(12)), (H(14), H(18))]


def test_virada_de_meia_noite_passa_para_o_dia_seguinte():
    ag = parse_opening_hours("Fr-Sa 18:00-01:00")
    assert ag[4] == [(H(18), 1440)] and ag[5] == [(0, H(1)), (H(18), 1440)] and ag[6] == [(0, H(1))]
    assert parse_opening_hours("Mo 12:00-24:00")[0] == [(H(12), 1440)]


def test_virgula_separando_regras_nao_so_faixas_nem_dias():
    ag = parse_opening_hours("Mo-Fr 11:00-21:00, Sa 09:00-21:00")
    assert ag[0] == [(H(11), H(21))] and ag[5] == [(H(9), H(21))] and ag[6] == []
    ag = parse_opening_hours("Mo-Fr 12:00-15:00, Mo-Fr 18:00-23:00, Sa 12:00-23:00, Su 12:00-16:00")
    assert ag[2] == [(H(12), H(15)), (H(18), H(23))]  # virgula e ADITIVA: abre nos dois turnos
    assert ag[5] == [(H(12), H(23))] and ag[6] == [(H(12), H(16))]
    # ';' sobrescreve, ',' soma
    assert parse_opening_hours("Mo-Fr 09:00-12:00; Mo-Fr 14:00-18:00")[0] == [(H(14), H(18))]
    assert parse_opening_hours("Mo-Fr 09:00-12:00, Mo-Fr 14:00-18:00")[0] == [(H(9), H(12)), (H(14), H(18))]
    assert parse_opening_hours("Sa,Su 10:00-14:00")[6] == [(H(10), H(14))]  # virgula entre dias continua valendo


def test_feriados_sao_ignorados_e_off_fecha_o_dia():
    ag = parse_opening_hours("Mo-Fr 09:00-18:00; PH 10:00-12:00")
    assert ag[0] == [(H(9), H(18))]
    assert parse_opening_hours("PH,Tu-Su 08:00-16:30")[1] == [(H(8), H(16, 30))]
    ag = parse_opening_hours("Mo-Su 09:00-18:00; Su off")
    assert ag[5] and ag[6] == []
    assert parse_opening_hours("Mo-Th 16:00-22:00; PH off")[0] == [(H(16), H(22))]


@pytest.mark.parametrize("txt", [None, "", "  ", "restricted", "unknown", "aberto", "May-Sep Th-Fr 18:00-00:00", "Fr[3] 18:00-22:00",
                                 "sunrise-sunset", "Mo-Fr 08:00+", "Segunda a sabado, das 14h as 18h", "Seg-Sab 11h-18h",
                                 "Mo-Fr 25:00-26:00", "Xx 09:00-10:00", "Mo-Fr 9am-5pm"])
def test_fora_do_subconjunto_e_none(txt):
    assert parse_opening_hours(txt) is None


# ------------------------------------------------------------------ o que o pedido exige
def test_extrai_ate_em_e_faixa():
    _, e = extrair_exigencias(None, "ate 22h")
    assert [(x.tipo, x.inicio) for x in e] == [("ate", H(22))]
    _, e = extrair_exigencias(None, "até às 22h30")
    assert [(x.tipo, x.inicio) for x in e] == [("ate", H(22, 30))]
    _, e = extrair_exigencias("madrugada", "03:30")
    assert ("em", H(3, 30)) in [(x.tipo, x.inicio) for x in e]
    _, e = extrair_exigencias("tarde", "14:00 - 18:00")
    assert ("janela", H(14), H(18)) in [(x.tipo, x.inicio, x.fim) for x in e]
    _, e = extrair_exigencias(None, "das 14h às 18h")
    assert ("janela", H(14), H(18)) in [(x.tipo, x.inicio, x.fim) for x in e]
    _, e = extrair_exigencias(None, "a partir das 8h")
    assert [(x.tipo, x.inicio) for x in e] == [("em", H(8))]


def test_extrai_dias_e_turnos():
    dias, e = extrair_exigencias(None, "sábado à noite")
    assert dias == {5} and e[0].tipo == "turnos" and e[0].descricao == "noite"
    dias, e = extrair_exigencias("manha", "manhã de domingo")
    assert dias == {6} and e[0].descricao == "manha"
    assert extrair_exigencias(None, "fim de semana")[0] == {5, 6}
    assert extrair_exigencias(None, "dias úteis")[0] == {0, 1, 2, 3, 4}
    dias, e = extrair_exigencias(None, "domingo")  # so o dia
    assert dias == {6} and e[0].tipo == "janela"


def test_sem_exigencia_de_horario():
    assert extrair_exigencias(None, None) == (None, [])
    assert extrair_exigencias("indefinido", "2 pessoas") == (None, [])  # numero solto nao e horario


# ------------------------------------------------------------------ avaliacao: os casos reais do dataset
@pytest.mark.parametrize("horas,slot,texto,status", [
    # TC-15 "aberto ate as 22h": os dois lugares que o agente entregou fecham antes
    ("09:00-17:00", None, "até 22h", "incompativel"),                  # Entre Eixos
    ("Mo-Fr 08:15-17:30", None, "até 22h", "incompativel"),            # Melbourne
    ("Mo-Su 06:00-22:00", None, "até 22h", "compativel"),
    ("Mo-Su 07:30-21:00", None, "até 22h", "incompativel"),            # fecha 21h
    ("Mo-Sa 11:00-22:00; Su 12:00-22:00", None, "até 22h", "compativel"),
    # TC-06 "sabado a noite": Bloco Q/R so abrem Ter-Qui de dia
    ("Tu-Th 09:00-17:00", None, "sábado à noite", "incompativel"),
    ("Tu-Th 18:00-24:00; Fr-Sa 18:00-01:00", None, "sábado à noite", "compativel"),
    # TC-14 "manha de domingo": JBB abre Ter-Dom 9-17
    ("Tu-Su 09:00-17:00", "manha", "manhã de domingo", "compativel"),
    ("Mo-Sa 09:00-17:00", "manha", "manhã de domingo", "incompativel"),
    # TC-02 "final de tarde": o pub abre as 18h e a tolerancia de fronteira o mantem
    ("Tu-Th 18:00-24:00; Fr-Sa 18:00-01:00", "tarde", None, "compativel"),
    ("Mo-Fr 08:15-17:30", "tarde", None, "compativel"),
    ("Mo-Fr 08:15-17:30", "noite", None, "incompativel"),
    # TC-17 madrugada
    ("07:00-20:00", "madrugada", "03:30", "incompativel"),
    ("24/7", "madrugada", "03:30", "compativel"),
    ("Mo-Su 18:00-04:00", "madrugada", "03:30", "compativel"),         # vira a noite
    # faixa explicita
    ("07:00-20:00", "tarde", "14:00 - 18:00", "compativel"),
    ("Mo-Fr 07:00-12:00", None, "14:00 - 18:00", "incompativel"),
    # tem que abrir em algum dia que atenda; o dia pedido manda
    ("Mo-Fr 09:00-18:00", None, "domingo", "incompativel"),
    ("Mo-Fr 09:00-18:00; Su 10:00-14:00", None, "domingo", "compativel"),
])
def test_avaliar_casos_reais(horas, slot, texto, status):
    st, motivo = avaliar_horario(horas, slot, texto)
    assert st == status
    assert (motivo is not None) == (status == "incompativel")


@pytest.mark.parametrize("horas", [None, "", "restricted", "unknown", "aberto", "Segunda a sabado, das 14h as 18h", "May-Sep Th-Fr 18:00-00:00"])
def test_sem_evidencia_nunca_reprova(horas):
    assert avaliar_horario(horas, "noite", "até 22h")[0] == "nao_confirmado"


def test_pedido_sem_horario_nunca_reprova_nem_le_o_opening_hours():
    assert avaliar_horario("09:00-17:00", None, None)[0] == "sem_restricao"
    assert avaliar_horario("lixo", "indefinida", "tanto faz")[0] == "sem_restricao"


def test_motivo_cita_o_horario_do_osm_e_o_pedido():
    _, motivo = avaliar_horario("Mo-Fr 08:15-17:30", None, "até 22h")
    assert "Mo-Fr 08:15-17:30" in motivo and "ate 22h" in motivo
