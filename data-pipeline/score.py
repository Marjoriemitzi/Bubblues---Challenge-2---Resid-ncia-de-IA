"""Calculo do score, decomposicao por fator e validacao da evidencia (sem banco)."""

import math

PESOS = {
    "similaridade": 0.40,
    "distancia": 0.25,
    "reputacao": 0.15,
    "compatibilidade": 0.20,
}

PESO_NOTA_GOOGLE = 0.4
PESO_NOTA_APP = 0.6
NOTA_MAXIMA = 5.0

# Valor de um fator sem dado: nao premia nem pune o lugar.
VALOR_NEUTRO = 0.5
SEM_DADO = "sem_dado"

# Mesma curva do benchmark: 1 / (1 + km / 5).
ESCALA_DISTANCIA_M = 5000.0

TOLERANCIA = 1e-9


def limitar(valor):
    """Restringe a [0, 1]. NaN vira 0: o pgvector devolve NaN para vetor nulo."""
    if math.isnan(valor):
        return 0.0
    return max(0.0, min(1.0, valor))


def fator_distancia(distancia_m):
    return limitar(1 / (1 + distancia_m / ESCALA_DISTANCIA_M))


def fator_reputacao(nota_google, nota_app):
    """Devolve (valor, origem). Com uma so nota, usa essa nota sozinha."""
    if nota_google is not None and nota_app is not None:
        nota = PESO_NOTA_GOOGLE * float(nota_google) + PESO_NOTA_APP * float(nota_app)
        origem = "nota_google_e_app"
    elif nota_google is not None:
        nota, origem = float(nota_google), "nota_google"
    elif nota_app is not None:
        nota, origem = float(nota_app), "nota_app"
    else:
        return VALOR_NEUTRO, SEM_DADO
    return limitar(nota / NOTA_MAXIMA), origem


def _etiqueta_atende(valor_osm, valor_desejado):
    # O OSM guarda listas separadas por ponto e virgula: cuisine=sushi;japanese.
    valores = {parte.strip().casefold() for parte in str(valor_osm).split(";")}
    return str(valor_desejado).strip().casefold() in valores


def fator_compatibilidade(tags, etiquetas_desejadas):
    """Media por etiqueta pedida: atende = 1, contraria = 0, ausente = neutro.

    Etiqueta ausente nao conta como "nao": o OSM e esparso, e a falta do registro
    nao significa que o lugar nao tenha o atributo.
    """
    if not etiquetas_desejadas or not any(c in tags for c in etiquetas_desejadas):
        return VALOR_NEUTRO, SEM_DADO
    notas = [
        VALOR_NEUTRO if chave not in tags
        else float(_etiqueta_atende(tags[chave], desejado))
        for chave, desejado in etiquetas_desejadas.items()
    ]
    return limitar(math.fsum(notas) / len(notas)), "etiquetas_osm"


def calcular_score(similaridade, distancia_m, nota_google, nota_app, tags, etiquetas_desejadas):
    """Devolve (fatores, total), em que total e a soma das contribuicoes."""
    medidas = {
        "similaridade": (limitar(similaridade), "pgvector_cosseno"),
        "distancia": (fator_distancia(distancia_m), "postgis"),
        "reputacao": fator_reputacao(nota_google, nota_app),
        "compatibilidade": fator_compatibilidade(tags, etiquetas_desejadas),
    }
    fatores = [
        {
            "nome": nome,
            "valor": medidas[nome][0],
            "peso": peso,
            "contribuicao": medidas[nome][0] * peso,
            "origem": medidas[nome][1],
        }
        for nome, peso in PESOS.items()
    ]
    total = limitar(math.fsum(f["contribuicao"] for f in fatores))
    return fatores, total


def chave_ordenacao(score_total, distancia_m, osm_type, osm_id):
    """Maior score, depois mais perto, depois o identificador OSM.

    O score e arredondado para ruido de ponto flutuante nao decidir um empate.
    O desempate final usa o id OSM porque place_id muda a cada curadoria.
    """
    return (-round(score_total, 9), distancia_m, osm_type, osm_id)


def link_osm(osm_type, osm_id):
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def etiquetas_usadas(tipo_categoria, categoria, tags, etiquetas_desejadas):
    """Etiquetas que influenciaram o resultado: a do tipo e as pedidas que existem."""
    usadas = {tipo_categoria: categoria}
    for chave in etiquetas_desejadas or {}:
        if chave in tags:
            usadas[chave] = tags[chave]
    return usadas


CAMPOS_REGISTRO = ("consulta_id", "criada_em", "consulta", "raio", "status", "pesos", "resultados")
CAMPOS_RAIO = ("solicitado_m", "final_m", "ampliado")
CAMPOS_RESULTADO = ("posicao", "local", "osm_url", "etiquetas_usadas", "fatores", "score_total")
CAMPOS_LOCAL = ("place_id", "nome", "categoria", "latitude", "longitude", "distancia_m")
CAMPOS_FATOR = ("nome", "valor", "peso", "contribuicao", "origem")


def _exigir_campos(objeto, campos, contexto):
    faltando = [c for c in campos if c not in objeto or objeto[c] is None]
    if faltando:
        raise ValueError(f"{contexto}: campos ausentes: {faltando}")


def _exigir_intervalo(valor, contexto):
    if not (isinstance(valor, (int, float)) and 0.0 <= valor <= 1.0):
        raise ValueError(f"{contexto}: valor fora de [0, 1]: {valor!r}")


def _validar_resultado(resultado, posicao_esperada):
    contexto = f"resultado {posicao_esperada}"
    _exigir_campos(resultado, CAMPOS_RESULTADO, contexto)
    _exigir_campos(resultado["local"], CAMPOS_LOCAL, f"{contexto}, local")

    if resultado["posicao"] != posicao_esperada:
        raise ValueError(f"{contexto}: posicao {resultado['posicao']} fora de ordem")
    if not resultado["osm_url"].startswith("https://www.openstreetmap.org/"):
        raise ValueError(f"{contexto}: link do OSM invalido: {resultado['osm_url']!r}")
    if not resultado["etiquetas_usadas"]:
        raise ValueError(f"{contexto}: nenhuma etiqueta registrada")

    fatores = resultado["fatores"]
    if [f.get("nome") for f in fatores] != list(PESOS):
        raise ValueError(f"{contexto}: fatores diferentes de {list(PESOS)}")

    for fator in fatores:
        rotulo = f"{contexto}, fator {fator['nome']}"
        _exigir_campos(fator, CAMPOS_FATOR, rotulo)
        _exigir_intervalo(fator["valor"], rotulo)
        _exigir_intervalo(fator["contribuicao"], rotulo)
        if not math.isclose(fator["peso"], PESOS[fator["nome"]], abs_tol=TOLERANCIA):
            raise ValueError(f"{rotulo}: peso {fator['peso']} difere do configurado")
        if not math.isclose(fator["valor"] * fator["peso"], fator["contribuicao"], abs_tol=TOLERANCIA):
            raise ValueError(f"{rotulo}: contribuicao diferente de valor * peso")

    total = resultado["score_total"]
    _exigir_intervalo(total, contexto)
    soma = math.fsum(f["contribuicao"] for f in fatores)
    if not math.isclose(soma, total, abs_tol=TOLERANCIA):
        raise ValueError(f"{contexto}: soma das contribuicoes {soma} difere do total {total}")


def validar_evidencia(registro):
    """Levanta ValueError se o registro estiver incompleto ou inconsistente."""
    _exigir_campos(registro, CAMPOS_REGISTRO, "registro")
    _exigir_campos(registro["raio"], CAMPOS_RAIO, "raio")
    for posicao, resultado in enumerate(registro["resultados"], start=1):
        _validar_resultado(resultado, posicao)
