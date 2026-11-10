
import json
from pathlib import Path
import requests

# 1. Configuração da coleta
cidade = "Brasília"

url = "https://overpass-api.de/api/interpreter"

# Criar as pastas antes de salvar qualquer arquivo
pasta_raw = Path("data/raw")
pasta_processed = Path("data/processed")

pasta_raw.mkdir(parents=True, exist_ok=True)
pasta_processed.mkdir(parents=True, exist_ok=True)

# 2. Consulta aos estabelecimentos no OpenStreetMap
consulta = """
[out:json][timeout:120];

area["name"="Distrito Federal"]["admin_level"="4"]->.df;

(
 nwr["amenity"~"^(restaurant|cafe|fast_food|food_court|bar|pub|ice_cream|biergarten)$"]["name"](area.df);
 nwr["amenity"~"^(cinema|theatre|library|arts_centre|community_centre)$"]["name"](area.df);
 nwr["leisure"~"^(park|garden|nature_reserve|playground|sports_centre|fitness_centre|pitch|bowling_alley|stadium|water_park)$"]["name"](area.df);
 nwr["tourism"~"^(museum|attraction|viewpoint|zoo|aquarium|gallery)$"]["name"](area.df);
 nwr["shop"~"^(mall|bakery)$"]["name"](area.df);
);

out center tags;
"""

# 3. Consulta do limite geográfico do Distrito Federal
consulta_limite = """
[out:json][timeout:120];

rel["name"="Distrito Federal"]["admin_level"="4"];

out geom;
"""

headers = {
    "User-Agent": "pipeline-brasilia/1.0 (projeto-estudo)"
}

# 4. Realizar a coleta
print(f"Iniciando coleta de dados em {cidade}...")

resposta = requests.post(
    url,
    data={"data": consulta},
    headers=headers,
    timeout=150
)

resposta.raise_for_status()
dados = resposta.json()

print("Estabelecimentos coletados!")

# 5. Coletar o limite geográfico do DF
resposta_limite = requests.post(
    url,
    data={"data": consulta_limite},
    headers=headers,
    timeout=150
)

resposta_limite.raise_for_status()
dados_limite = resposta_limite.json()

print("Limite do Distrito Federal coletado!")

# 6. Salvar os arquivos JSON
with open(pasta_raw / "estabelecimentos.json", "w", encoding="utf-8") as arquivo:
    json.dump(dados, arquivo, ensure_ascii=False, indent=4)

with open(pasta_processed / "limite_df.json", "w", encoding="utf-8") as arquivo:
    json.dump(dados_limite, arquivo, ensure_ascii=False, indent=2)

print("Dados brutos e limite geográfico salvos com sucesso!")

# 7. Exibir os resultados
elementos = dados.get("elements", [])

print("Coleta concluída!")
print(f"Total de estabelecimentos: {len(elementos)}")

for estabelecimento in elementos[:5]:
    tags = estabelecimento.get("tags", {})

    nome = tags.get("name", "Sem nome")

    categoria = (
        tags.get("amenity")
        or tags.get("leisure")
        or tags.get("tourism")
        or tags.get("shop")
        or "Não identificada"
    )

    latitude = estabelecimento.get("lat")
    longitude = estabelecimento.get("lon")

    # Vias e relações podem ter coordenadas em center
    if latitude is None:
        centro = estabelecimento.get("center", {})
        latitude = centro.get("lat")
        longitude = centro.get("lon")

    print("----------------------------")
    print(f"Nome: {nome}")
    print(f"Categoria: {categoria}")
    print(f"Latitude: {latitude}")
    print(f"Longitude: {longitude}")
