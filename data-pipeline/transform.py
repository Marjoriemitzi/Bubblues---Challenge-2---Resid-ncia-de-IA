

import json
import pandas as pd
from pathlib import Path

# 1. Caminho dos dados brutos
arquivo_entrada = Path("data/raw/estabelecimentos.json")

if not arquivo_entrada.exists():
    raise FileNotFoundError(
        f"Arquivo não encontrado: {arquivo_entrada}. "
        "Execute primeiro o extract.py."
    )

# 2. Carregar os dados
with open(arquivo_entrada, "r", encoding="utf-8") as arquivo:
    dados = json.load(arquivo)

elementos = dados.get("elements", [])

print(f"Registros recebidos: {len(elementos)}")

# 3. Categorias permitidas
categorias_permitidas = {
    "amenity": [
        "restaurant", "cafe", "fast_food", "food_court",
        "bar", "pub", "ice_cream", "biergarten",
        "cinema", "theatre", "library", "arts_centre",
        "community_centre"
    ],
    "leisure": [
        "park", "garden", "nature_reserve", "playground",
        "sports_centre", "fitness_centre", "pitch",
        "bowling_alley", "stadium", "water_park"
    ],
    "tourism": [
        "museum", "attraction", "viewpoint",
        "zoo", "aquarium", "gallery"
    ],
    "shop": ["mall", "bakery"]
}

# 4. Organizar os dados
registros = []

for elemento in elementos:
    tags = elemento.get("tags", {})

    # Identificar coordenadas
    latitude = elemento.get("lat")
    longitude = elemento.get("lon")

    if latitude is None:
        centro = elemento.get("center", {})
        latitude = centro.get("lat")
        longitude = centro.get("lon")

    # Identificar categoria permitida
    categoria_tipo = "outro"
    categoria = "não informada"

    for tipo, valores in categorias_permitidas.items():
        if tags.get(tipo) in valores:
            categoria_tipo = tipo
            categoria = tags[tipo]
            break

    # Criar registro
    registro = {
        "osm_id": elemento["id"],
        "osm_type": elemento["type"],
        "nome": tags.get("name"),
        "tipo_categoria": categoria_tipo,
        "categoria": categoria,
        "latitude": latitude,
        "longitude": longitude,
        "cidade": "Brasília"
    }

    registros.append(registro)

# 5. Criar DataFrame
df = pd.DataFrame(registros)

if df.empty:
    raise ValueError("Nenhum estabelecimento foi encontrado na coleta.")

# 6. Verificar qualidade dos dados
print("Registros duplicados:",
      df.duplicated(subset=["osm_type", "osm_id"]).sum())

print("Nomes ausentes:", df["nome"].isna().sum())
print("Latitudes ausentes:", df["latitude"].isna().sum())
print("Longitudes ausentes:", df["longitude"].isna().sum())

# 7. Limpeza dos dados
df = df.drop_duplicates(subset=["osm_type", "osm_id"])

df["nome"] = df["nome"].fillna("Sem nome")

df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

df = df.dropna(subset=["latitude", "longitude"])

df = df[df["tipo_categoria"] != "outro"]

# 8. Padronizar categorias
df["categoria"] = df["categoria"].str.lower().str.strip()
df["tipo_categoria"] = df["tipo_categoria"].str.lower().str.strip()

print("\nQuantidade por tipo de categoria:")
print(df["tipo_categoria"].value_counts())

print("\nQuantidade por categoria:")
print(df["categoria"].value_counts())

# 9. Organizar as colunas
df = df[
    [
        "osm_id",
        "osm_type",
        "nome",
        "tipo_categoria",
        "categoria",
        "latitude",
        "longitude",
        "cidade"
    ]
]

# 10. Salvar os dados tratados
pasta_saida = Path("data/processed")
pasta_saida.mkdir(parents=True, exist_ok=True)

arquivo_saida = pasta_saida / "estabelecimentos.csv"

df.to_csv(arquivo_saida, index=False, encoding="utf-8-sig")

# 11. Mostrar resultado
print("\nTransformação concluída!")
print(f"Registros após limpeza: {len(df)}")
print(f"Arquivo salvo em: {arquivo_saida}")

print("\nPrévia dos dados tratados:")
print(df.head())

