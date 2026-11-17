"""Mediacao logistica passiva e dinamica do Encontro (ADR-0003 e GLOSSARY.md)."""

from collections import Counter

from score import atende_barreiras, calcular_score, chave_ordenacao

PISO_QUORUM_MINIMO = 3
LIMITE_MAXIMO_GRUPO = 8
BONUS_PRESENCA = 1
PENALIDADE_NO_SHOW = -2

_TOPICOS_PADRAO_QUEBRA_GELO = (
    "Descobrir o que trouxe cada Membro a este Local Verificado hoje",
    "Trocar recomendacoes de livros, filmes ou lugares tranquilos pela cidade",
    "Compartilhar um hobby ou atividade simples que ajuda a sair da rotina",
)


def _extrair_id_membro(membro):
    return membro["id"] if isinstance(membro, dict) else membro


def _normalizar_afinidades(membro):
    if not isinstance(membro, dict):
        return set()
    return {str(a).strip().casefold() for a in membro.get("afinidades") or [] if str(a).strip()}


def _slot_compativel_com_membro(slot, afinidades_membro):
    if not afinidades_membro or not slot["membros"]:
        return True
    afinidades_slot = set()
    for participante in slot["membros"]:
        afinidades_slot.update(_normalizar_afinidades(participante))
    return not afinidades_slot or bool(afinidades_slot & afinidades_membro)


def alocar_em_slot(slots_ativos, membro, local_id, turno):
    """Aloca um Membro em um Slot de Pareamento compativel (ate 8 Membros) para Local e turno."""
    membro_id = _extrair_id_membro(membro)
    for slot in slots_ativos:
        if slot["local_id"] == local_id and slot["turno"] == turno:
            if any(_extrair_id_membro(m) == membro_id for m in slot["membros"]):
                return slot

    afinidades_membro = _normalizar_afinidades(membro)
    slot_alvo = next(
        (
            slot
            for slot in slots_ativos
            if slot["local_id"] == local_id
            and slot["turno"] == turno
            and len(slot["membros"]) < LIMITE_MAXIMO_GRUPO
            and _slot_compativel_com_membro(slot, afinidades_membro)
        ),
        None,
    )

    if slot_alvo is None:
        slot_alvo = {
            "slot_id": f"{local_id}:{turno}:{len(slots_ativos) + 1}",
            "local_id": local_id,
            "turno": turno,
            "membros": [],
            "status": "em_formacao",
        }
        slots_ativos.append(slot_alvo)

    slot_alvo["membros"].append(membro)
    slot_alvo["status"] = (
        "completo" if len(slot_alvo["membros"]) >= LIMITE_MAXIMO_GRUPO else "em_formacao"
    )
    return slot_alvo


def _extrair_afinidades_compartilhadas(membros_alocados):
    contagem = Counter()
    originais = {}
    for membro in membros_alocados:
        if not isinstance(membro, dict):
            continue
        vistas_no_membro = set()
        for tema in membro.get("afinidades") or []:
            limpo = str(tema).strip()
            chave = limpo.casefold()
            if limpo and chave not in vistas_no_membro:
                vistas_no_membro.add(chave)
                contagem[chave] += 1
                originais.setdefault(chave, limpo)
    ordenados = sorted(contagem.items(), key=lambda item: (-item[1], item[0]))
    return [originais[chave] for chave, _ in ordenados]


def _gerar_pauta_quebra_gelo(afinidades_grupo):
    """Gera 3 topicos leves de conversa baseados nas afinidades do grupo, sem expor autores."""
    topicos = []
    vistas = set()
    for tema in afinidades_grupo or []:
        tema_limpo = str(tema).strip()
        if not tema_limpo or tema_limpo.casefold() in vistas:
            continue
        vistas.add(tema_limpo.casefold())
        topicos.append(f"O que mais desperta seu interesse em {tema_limpo} ultimamente?")
        if len(topicos) == 3:
            break

    for padrao in _TOPICOS_PADRAO_QUEBRA_GELO:
        if len(topicos) == 3:
            break
        topicos.append(padrao)

    return topicos


def avaliar_checkin_final(membros_alocados, confirmados_checkin, afinidades_grupo=None):
    """Avalia o Quorum Minimo no Check-in Final e libera a Pauta Quebra-Gelo quando confirmado.

    Aplica maioria simples respeitando o piso absoluto e inegociavel de 3 Membros confirmados
    para impedir encontros 1-a-1 involuntarios entre desconhecidos.
    """
    alocados_ids = {_extrair_id_membro(m) for m in membros_alocados}
    confirmados_ids = [_extrair_id_membro(m) for m in confirmados_checkin]
    confirmados_validos = [m_id for m_id in dict.fromkeys(confirmados_ids) if m_id in alocados_ids]
    quorum_minimo = max(PISO_QUORUM_MINIMO, (len(alocados_ids) // 2) + 1)

    if len(confirmados_validos) < quorum_minimo:
        return {
            "encontro_confirmado": False,
            "status": "cancelado_quorum_insuficiente",
            "quorum_minimo": quorum_minimo,
            "total_confirmados": len(confirmados_validos),
            "pauta_quebra_gelo": [],
        }

    afinidades = (
        afinidades_grupo
        if afinidades_grupo is not None
        else _extrair_afinidades_compartilhadas(membros_alocados)
    )
    return {
        "encontro_confirmado": True,
        "status": "confirmado",
        "quorum_minimo": quorum_minimo,
        "total_confirmados": len(confirmados_validos),
        "pauta_quebra_gelo": _gerar_pauta_quebra_gelo(afinidades),
    }


def apurar_presenca(confirmados_checkin, desistencias_previas, presentes):
    """Classifica os participantes entre presenca cumprida, Desistencia Previa (isenta) e No-Show.

    Membros que comunicaram Desistencia Previa antes do encerramento da janela permanecem isentos
    de penalidade mesmo se tiverem confirmado previamente; apenas confirmados finais ausentes
    sem desistencia previa incorrem em No-Show (ADR-0003).
    """
    presentes_unicos = list(dict.fromkeys(_extrair_id_membro(m) for m in presentes))
    presentes_set = set(presentes_unicos)
    confirmados_unicos = list(dict.fromkeys(_extrair_id_membro(m) for m in confirmados_checkin))

    desistencias_isentas = [
        m_id
        for m_id in dict.fromkeys(_extrair_id_membro(m) for m in desistencias_previas)
        if m_id not in presentes_set
    ]
    desistencias_set = set(desistencias_isentas)
    no_shows = [
        m_id
        for m_id in confirmados_unicos
        if m_id not in presentes_set and m_id not in desistencias_set
    ]

    delta_compromisso = {}
    for m_id in desistencias_isentas:
        delta_compromisso[m_id] = 0
    for m_id in no_shows:
        delta_compromisso[m_id] = PENALIDADE_NO_SHOW
    for m_id in presentes_unicos:
        delta_compromisso[m_id] = BONUS_PRESENCA

    return {
        "presentes": presentes_unicos,
        "desistencias_previas_isentas": desistencias_isentas,
        "no_shows_penalizados": no_shows,
        "delta_compromisso": delta_compromisso,
    }


def _similaridade_interesses(local, interesses):
    if not interesses:
        return 0.5
    interesses_norm = {str(i).strip().casefold() for i in interesses if str(i).strip()}
    if not interesses_norm:
        return 0.5
    atributos_local = {str(local.get("categoria", "")).strip().casefold()}
    for chave, valor in (local.get("tags") or {}).items():
        atributos_local.add(str(chave).strip().casefold())
        for parte in str(valor).split(";"):
            atributos_local.add(parte.strip().casefold())
    atributos_local.update(str(t).strip().casefold() for t in local.get("etiquetas") or [])
    atributos_local.discard("")
    return len(interesses_norm & atributos_local) / len(interesses_norm)


def _pontuar_local_zero_turn(local, interesses, etiquetas_barreiras):
    similaridade = _similaridade_interesses(local, interesses)
    _, total = calcular_score(
        similaridade=similaridade,
        distancia_m=float(local.get("distancia_m", 0.0)),
        nota_google=local.get("nota_google"),
        nota_app=local.get("nota_app"),
        tags=local.get("tags") or {},
        etiquetas_desejadas=etiquetas_barreiras,
    )
    return total


def recomendar_zero_turn(perfil_base, catalogo_locais, k=3):
    """Retorna k Locais Verificados de categorias distintas aderentes ao Perfil Base (ADR-0003)."""
    if k < 1:
        raise ValueError("k deve ser pelo menos 1.")

    exige_acessibilidade = bool(
        perfil_base.get("acessibilidade_fisica") or perfil_base.get("wheelchair_required")
    )
    etiquetas_barreiras = {"wheelchair": "yes"} if exige_acessibilidade else {}
    tolerancia = perfil_base.get("tolerancia_sensorial", "indiferente")
    interesses = perfil_base.get("interesses") or []

    elegiveis = [
        local
        for local in catalogo_locais
        if local.get("is_public_verified") is True
        and atende_barreiras(
            local.get("tags"),
            etiquetas_barreiras,
            tolerancia_sensorial=tolerancia,
        )
    ]

    ordenados = sorted(
        elegiveis,
        key=lambda local: chave_ordenacao(
            _pontuar_local_zero_turn(local, interesses, etiquetas_barreiras),
            float(local.get("distancia_m", 0.0)),
            str(local.get("osm_type", "place")),
            str(local.get("osm_id", local.get("place_id", ""))),
        ),
    )

    selecionados = []
    categorias_vistas = set()
    sobras = []

    for local in ordenados:
        categoria = local.get("categoria")
        if categoria not in categorias_vistas:
            selecionados.append(local)
            categorias_vistas.add(categoria)
            if len(selecionados) == k:
                return selecionados
        else:
            sobras.append(local)

    # Completa ate k apenas se o catalogo elegivel tiver menos de k categorias distintas.
    for local in sobras:
        selecionados.append(local)
        if len(selecionados) == k:
            break

    return selecionados
