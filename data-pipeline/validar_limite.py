
import json
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import unary_union, polygonize

# 1. Definir caminhos dos arquivos
arquivo_limite = Path("data/processed/limite_df.json")
arquivo_estabelecimentos = Path("data/raw/estabelecimentos.json")
arquivo_saida = Path("data/processed/limite_df.geojson")

# 2. Verificar se os arquivos existem
if not arquivo_limite.exists():
    raise FileNotFoundError(
        "Limite do DF não encontrado. Execute primeiro extract.py."
    )

if not arquivo_estabelecimentos.exists():
    raise FileNotFoundError(
        "Dados dos estabelecimentos não encontrados. Execute extract.py."
    )

# 3. Carregar limite geográfico
with open(arquivo_limite, "r", encoding="utf-8") as arquivo:
    dados = json.load(arquivo)

elementos_limite = dados.get("elements", [])

if not elementos_limite:
    raise ValueError("Nenhum dado do limite do DF foi encontrado.")

membros = elementos_limite[0].get("members", [])

# 4. Construir os trechos do contorno externo
linhas = []

for membro in membros:
    if membro.get("type") == "way" and membro.get("role") == "outer":
        geometria = membro.get("geometry", [])

        coordenadas = [
            (ponto["lon"], ponto["lat"])
            for ponto in geometria
        ]

        if len(coordenadas) >= 2:
            linhas.append(LineString(coordenadas))

print("Quantidade de trechos do contorno:", len(linhas))

if not linhas:
    raise ValueError("Não foram encontrados trechos externos do limite.")

# 5. Unir os trechos e formar polígonos
contorno_unido = unary_union(linhas)
poligonos = list(polygonize(contorno_unido))

if not poligonos:
    raise ValueError("Não foi possível formar o polígono do DF.")

limite_df = unary_union(poligonos)

print("Quantidade de polígonos:", len(poligonos))
print("Limite válido:", limite_df.is_valid)
print("Área calculada:", limite_df.area)

# 6. Salvar o limite em GeoJSON
arquivo_saida.parent.mkdir(parents=True, exist_ok=True)

with open(arquivo_saida, "w", encoding="utf-8") as arquivo:
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

# 7. Carregar estabelecimentos
with open(arquivo_estabelecimentos, "r", encoding="utf-8") as arquivo:
    dados_estabelecimentos = json.load(arquivo)

elementos = dados_estabelecimentos.get("elements", [])

# 8. Função para obter coordenadas
def obter_coordenadas(elemento):
    latitude = elemento.get("lat")
    longitude = elemento.get("lon")

    if latitude is None or longitude is None:
        centro = elemento.get("center", {})
        latitude = centro.get("lat")
        longitude = centro.get("lon")

    if latitude is None or longitude is None:
        return None

    return longitude, latitude


# 9. Verificar estabelecimentos dentro e fora do DF
dentro = 0
fora = 0
estabelecimentos_fora = []

for elemento in elementos:
    coordenadas = obter_coordenadas(elemento)

    if coordenadas is None:
        continue

    ponto = Point(coordenadas)

    if limite_df.covers(ponto):
        dentro += 1
    else:
        fora += 1
        estabelecimentos_fora.append(elemento)

# 10. Exibir resultados
print("\nResultado da validação geográfica:")
print("Estabelecimentos dentro do DF:", dentro)
print("Estabelecimentos fora do DF:", fora)

# 11. Identificar estabelecimentos fora do DF
print("\nEstabelecimentos identificados fora do DF:")

for elemento in estabelecimentos_fora:
    nome = elemento.get("tags", {}).get("name", "Sem nome")
    coordenadas = obter_coordenadas(elemento)

    print("----------------------------")
    print("Estabelecimento:", nome)
    print("Coordenadas:", coordenadas[1], coordenadas[0])
