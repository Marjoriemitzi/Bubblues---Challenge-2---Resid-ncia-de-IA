"""Regioes do DF: converte um nome ("Asa Sul") em coordenadas, sem catalogo em codigo.

As regioes vem do OSM (extract_regioes.py), ficam na tabela `regioes` (load_regioes.py)
e a busca de nome e feita aqui. Funcoes de parse/normalizacao nao precisam de banco.
"""

import re
import unicodedata

# Menor valor vence quando varios elementos tem o mesmo nome. Pontos mapeados por pessoas
# (place=*) antes do centro de uma relacao administrativa, que e so o centro da caixa.
PRIORIDADE_PLACE = {
    "city": 0, "town": 0, "suburb": 1, "neighbourhood": 2, "quarter": 3, "village": 3, "city_block": 7,
}
PRIORIDADE_ADMIN = {"8": 4, "9": 5, "10": 6, "11": 6}


def normalizar_nome(texto):
    """Minusculas, sem acento, so letras/numeros separados por um espaco."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def _classificar(tags):
    """Devolve (tipo, prioridade) ou None se o elemento nao serve como regiao."""
    admin = tags.get("admin_level")
    if tags.get("boundary") == "administrative" and admin in PRIORIDADE_ADMIN:
        return f"admin_level={admin}", PRIORIDADE_ADMIN[admin]
    place = tags.get("place")
    if place in PRIORIDADE_PLACE:
        return f"place={place}", PRIORIDADE_PLACE[place]
    return None


def elementos_para_linhas(elementos):
    """Converte a resposta da Overpass em linhas da tabela `regioes`. Ignora o que nao tem
    nome, coordenada ou classificacao; deduplica por (osm_type, osm_id)."""
    linhas, vistos = [], set()
    for el in elementos:
        tags = el.get("tags") or {}
        nome = (tags.get("name") or "").strip()
        classe = _classificar(tags)
        centro = el if el.get("lat") is not None else el.get("center") or {}
        lat, lon = centro.get("lat"), centro.get("lon")
        chave = (el.get("type"), el.get("id"))
        if not nome or classe is None or lat is None or lon is None or chave in vistos:
            continue
        if not normalizar_nome(nome):
            continue
        vistos.add(chave)
        linhas.append(
            {
                "nome": nome,
                "nome_normalizado": normalizar_nome(nome),
                "tipo": classe[0],
                "prioridade": classe[1],
                "osm_id": el["id"],
                "osm_type": el["type"],
                "latitude": lat,
                "longitude": lon,
            }
        )
    return linhas


SQL_EXATA = """
    SELECT nome, tipo, latitude, longitude FROM regioes
    WHERE nome_normalizado = %s
    ORDER BY prioridade, osm_type, osm_id LIMIT 1
"""
# O nome pedido esta dentro do nome da regiao ("asa sul" em "plano piloto asa sul").
SQL_CONTIDA = """
    SELECT nome, tipo, latitude, longitude FROM regioes
    WHERE (' ' || nome_normalizado || ' ') LIKE %s
    ORDER BY prioridade, length(nome_normalizado), osm_type, osm_id LIMIT 1
"""
# O nome de uma regiao esta dentro do texto pedido ("asa sul brasilia"): vence o mais longo.
SQL_CONTEM = """
    SELECT nome, tipo, latitude, longitude FROM regioes
    WHERE length(nome_normalizado) >= 4 AND %s LIKE ('%% ' || nome_normalizado || ' %%')
    ORDER BY length(nome_normalizado) DESC, prioridade, osm_type, osm_id LIMIT 1
"""


def resolver_regiao(conexao, nome):
    """Devolve (latitude, longitude, nome_encontrado) ou None se a regiao nao existe."""
    chave = normalizar_nome(nome or "")
    if not chave:
        return None
    consultas = (
        (SQL_EXATA, (chave,)),
        (SQL_CONTIDA, (f"% {chave} %",)),
        (SQL_CONTEM, (f" {chave} ",)),
    )
    for sql, params in consultas:
        linha = conexao.execute(sql, params).fetchone()
        if linha:
            return linha[2], linha[3], linha[0]
    return None
