"""Catalogo FIXO de POIs de exemplo, so para testes e demos.

Nunca usar em producao: la, os metadados do OSM chegam no proprio SearchItem
(osm_id, osm_type, osm_tags, is_public_verified) vindos do PostgreSQL.
"""

from typing import Any, Dict

BASE_POIS_CATALOG: Dict[str, Dict[str, Any]] = {
    "POI-01": {
        "place_id": "POI-01",
        "name": "Ernesto Cafés Especiais",
        "osm_id": 482910482,
        "osm_type": "node",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "noise_level": "baixo",
        "opening_hours": "07:00-20:00",
        "tags": ["cafe", "calmo", "acessivel", "leitura", "conversa", "brunch", "asa sul"],
    },
    "POI-02": {
        "place_id": "POI-02",
        "name": "Parque da Cidade Dona Sarah Kubitschek",
        "osm_id": 918237412,
        "osm_type": "way",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "noise_level": "moderado",
        "opening_hours": "06:00-22:00",
        "tags": ["parque", "ar livre", "caminhada", "pista plana", "acessivel", "pet", "xadrez", "sombra"],
    },
    "POI-03": {
        "place_id": "POI-03",
        "name": "Sephinah Casa de Chá e Cafeteria",
        "osm_id": 593817261,
        "osm_type": "node",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "noise_level": "baixo",
        "opening_hours": "08:00-19:00",
        "tags": ["cafe", "casa de cha", "calmo", "acessivel", "leitura", "conversa", "asa sul"],
    },
    "Sebinho Livraria Café e Bistrô Asa Norte": {
        "place_id": "POI-SEBINHO",
        "name": "Sebinho Livraria Café e Bistrô Asa Norte",
        "osm_id": 1849203941,
        "osm_type": "node",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "noise_level": "baixo",
        "opening_hours": "09:00-22:00",
        "tags": ["livraria", "cafe", "bistro", "calmo", "acessivel", "leitura", "asa norte"],
    },
    "Parque da Cidade Sarah Kubitschek": {
        "place_id": "POI-02",
        "name": "Parque da Cidade Sarah Kubitschek",
        "osm_id": 2938475610,
        "osm_type": "way",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "noise_level": "moderado",
        "opening_hours": "06:00-22:00",
        "tags": ["parque", "ar livre", "caminhada", "acessivel"],
    },
    "Ernesto Cafés Especiais Asa Sul": {
        "place_id": "POI-01",
        "name": "Ernesto Cafés Especiais Asa Sul",
        "osm_id": 4455667788,
        "osm_type": "node",
        "is_public_verified": True,
        "wheelchair": "no",  # Configurado propositalmente para testar reprovação
        "elder_friendly": True,
        "noise_level": "baixo",
        "opening_hours": "07:00-20:00",
        "tags": ["cafe", "calmo", "asa sul"],
    },
}
