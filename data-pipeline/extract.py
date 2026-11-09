import json
from pathlib import Path
import requests

# 1. Configuração da coleta
cidade = "Brasília"

url = "https://overpass-api.de/api/interpreter"

# 2. Consulta ao OpenStreetMap
consulta = """\
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
# Consulta do limite geográfico do Distrito Federal
consulta_limite = """
[out:json][timeout:120];

rel["name"="Distrito Federal"]["admin_level"="4"];

out geom;
"""

# Realizar a requisição
print(f"Iniciando coleta de dados em {cidade}...")

headers = {
    "User-Agent": "pipeline-brasilia/1.0 (projeto-estudo)"
}

resposta = requests.post(
    url,
    data={"data": consulta},
    headers=headers,
    timeout=150
)
# Coleta do limite geográfico do DF
resposta_limite = requests.post(
    url,
    data={"data": consulta_limite},
    headers=headers,
    timeout=150
)

resposta_limite.raise_for_status()

dados_limite = resposta_limite.json()

print("Limite do Distrito Federal coletado!")

# Salvar limite do DF
with open("data/processed/limite_df.json", "w", encoding="utf-8") as arquivo:
    json.dump(dados_limite, arquivo, ensure_ascii=False, indent=2)

print("Limite do DF salvo em data/processed/limite_df.json")

resposta.raise_for_status()
dados = resposta.json()
# 4. Verificar a resposta
resposta.raise_for_status()

dados = resposta.json()

# 5. Mostrar os resultados
elementos = dados["elements"]

print(f"Coleta concluída!")
print(f"Total de estabelecimentos: {len(elementos)}")

# Criar pasta para armazenar os dados brutos
pasta = Path("data/raw")
pasta.mkdir(parents=True, exist_ok=True)

# Salvar resposta original
with open(pasta / "estabelecimentos.json", "w", encoding="utf-8") as arquivo:
    json.dump(dados, arquivo, ensure_ascii=False, indent=4)

print("Dados brutos salvos com sucesso!")

# 6. Exibir os primeiros resultados
for estabelecimento in elementos[:5]:

    tags = estabelecimento.get("tags", {})

    nome = tags.get("name", "Sem nome")
    categoria = tags.get("amenity", "Não identificada")

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
