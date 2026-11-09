import json
from shapely.geometry import LineString
from shapely.ops import unary_union, polygonize

# Abrir o arquivo com o limite do Distrito Federal
with open("data/processed/limite_df.json", "r", encoding="utf-8") as arquivo:
    dados = json.load(arquivo)

# Pegar os trechos que formam o contorno externo
membros = dados["elements"][0]["members"]

linhas = []

for membro in membros:
    if membro["type"] == "way" and membro["role"] == "outer":
        coordenadas = [
            (ponto["lon"], ponto["lat"])
            for ponto in membro["geometry"]
        ]

        linhas.append(LineString(coordenadas))

print("Quantidade de trechos do contorno:", len(linhas))
# Unir os trechos do contorno
contorno_unido = unary_union(linhas)

# Transformar as linhas fechadas em polígonos
poligonos = list(polygonize(contorno_unido))

# Unir os polígonos encontrados
from shapely.geometry import MultiPolygon
limite_df = unary_union(poligonos)

print("Quantidade de polígonos:", len(poligonos))
print("Limite válido:", limite_df.is_valid)
print("Área calculada:", limite_df.area)
# Salvar o polígono em formato GeoJSON
with open("data/processed/limite_df.geojson", "w", encoding="utf-8") as arquivo:
    json.dump(
        {
            "type": "Feature",
            "properties": {"nome": "Distrito Federal"},
            "geometry": limite_df.__geo_interface__
        },
        arquivo,
        ensure_ascii=False,
        indent=2
    )

print("Polígono do DF salvo com sucesso!")
from shapely.geometry import Point

# Contar estabelecimentos dentro do DF
with open("data/raw/estabelecimentos.json", "r", encoding="utf-8") as arquivo:
    dados_estabelecimentos = json.load(arquivo)

dentro = 0
fora = 0

for elemento in dados_estabelecimentos["elements"]:
    if elemento["type"] == "node":
        lon = elemento["lon"]
        lat = elemento["lat"]
    else:
        centro = elemento.get("center")
        if not centro:
            continue
        lon = centro["lon"]
        lat = centro["lat"]

    ponto = Point(lon, lat)

    if limite_df.covers(ponto):
        dentro += 1
    else:
        fora += 1

print("Estabelecimentos dentro do DF:", dentro)
print("Estabelecimentos fora do DF:", fora)
# Identificar estabelecimentos fora do DF
for elemento in dados_estabelecimentos["elements"]:
    if elemento["type"] == "node":
        lon = elemento["lon"]
        lat = elemento["lat"]
    else:
        centro = elemento.get("center")
        if not centro:
            continue
        lon = centro["lon"]
        lat = centro["lat"]

    ponto = Point(lon, lat)

    if not limite_df.covers(ponto):
        print("Estabelecimento fora:", elemento.get("tags", {}).get("name"))
        print("Coordenadas:", lat, lon)