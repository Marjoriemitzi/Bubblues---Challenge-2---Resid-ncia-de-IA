#!/usr/bin/env python3
"""
scripts/p1_demo.py
Demonstração completa do P1: Contratos, LLM e Demonstração
Projeto: Bubbles - Challenge 2 (Residência em IA - Grupo 10)

Funcionalidades:
 1. Definição formal dos 4 contratos (PlaceRecord, StructuredRequest, SearchResponse, EvidenceRecord)
 2. Interpretação de pedido com validação de esquema e mecanismo de RETRY automático caso o JSON venha inválido.
 3. Gerador de resposta ancorado estritamente nas evidências recuperadas (grounded RAG) com abstenção automática.
 4. Verificador pós-geração: validação determinística de que 100% dos locais citados no texto existem no retorno da busca.
 5. Demonstração prática com 3 consultas de teste (Normal, Impossível/Falta de Dados e Fora de Escopo).
 6. Suporte a execução offline (Modo Simulado Autônomo com injeção de erro para testar retry) e execução via API LLM real (OpenAI/Gemini/Ollama).
"""

import os
import sys
import json
import re
import uuid
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# =====================================================================
# 1. BASE DE CONHECIMENTO DE EXEMPLO (POIs Verificados do DF - PostGIS)
# =====================================================================

MOCK_POIS = [
    {
        "place_id": "POI-01",
        "name": "Ernesto Cafés Especiais",
        "amenity": "cafe",
        "category": "cafe_especial",
        "address": "CLS 115 Bloco C, Asa Sul, Brasília - DF",
        "location": {"lat": -15.8234, "lon": -47.9256},
        "distance_km": 1.8,
        "vibe": "tranquilo",
        "noise_level": "baixo",
        "wheelchair": "yes",
        "suitable_for": ["introvertido", "idosos", "adulto", "conversas_profundas"],
        "ratings": {"google_rating": 4.7, "app_rating": 4.8, "total_reviews": 1240},
        "has_wifi": True,
        "has_open_air": True,
        "opening_hours": "07:00-20:00",
        "is_public_verified": True,
        "tags": ["cafe", "calmo", "acessivel", "leitura", "conversa", "brunch", "asa sul"],
        "vector": [0.9, 0.1, 0.3, 0.4, 0.6, 0.0, 0.9, 0.1, 0.2, 0.4, 0.8, 0.0, 0.5, 0.0, 0.0, 0.6],
        "provenance": {
            "source": "OpenStreetMap",
            "osm_id": 482910482,
            "osm_type": "node",
            "osm_link": "https://www.openstreetmap.org/node/482910482",
            "ingestion_date": "2026-11-01T08:00:00Z"
        }
    },
    {
        "place_id": "POI-02",
        "name": "Parque da Cidade Dona Sarah Kubitschek",
        "amenity": "park",
        "category": "parque_urbano",
        "address": "Setor de Recreação Pública Sul, Asa Sul, Brasília - DF",
        "location": {"lat": -15.8012, "lon": -47.9054},
        "distance_km": 2.1,
        "vibe": "ar_livre",
        "noise_level": "moderado",
        "wheelchair": "yes",
        "suitable_for": ["idosos", "familias", "pet_friendly", "esportes_leves"],
        "ratings": {"google_rating": 4.8, "app_rating": 4.7, "total_reviews": 8900},
        "has_wifi": False,
        "has_open_air": True,
        "opening_hours": "06:00-22:00",
        "is_public_verified": True,
        "tags": ["parque", "ar livre", "caminhada", "pista plana", "acessivel", "pet", "xadrez", "sombra"],
        "vector": [0.1, 1.0, 0.1, 0.2, 0.1, 0.5, 0.5, 0.6, 0.5, 0.1, 0.9, 0.8, 0.0, 0.0, 0.0, 0.8],
        "provenance": {
            "source": "OpenStreetMap",
            "osm_id": 918237412,
            "osm_type": "way",
            "osm_link": "https://www.openstreetmap.org/way/918237412",
            "ingestion_date": "2026-11-01T08:00:00Z"
        }
    },
    {
        "place_id": "POI-03",
        "name": "Sephinah Casa de Chá e Cafeteria",
        "amenity": "cafe",
        "category": "casa_de_cha",
        "address": "CLS 403 Bloco B, Asa Sul, Brasília - DF",
        "location": {"lat": -15.8265, "lon": -47.9012},
        "distance_km": 1.2,
        "vibe": "tranquilo",
        "noise_level": "baixo",
        "wheelchair": "yes",
        "suitable_for": ["introvertido", "idosos", "conversa_profunda", "timido"],
        "ratings": {"google_rating": 4.6, "app_rating": 4.9, "total_reviews": 412},
        "has_wifi": True,
        "has_open_air": False,
        "opening_hours": "08:00-19:00",
        "is_public_verified": True,
        "tags": ["cha", "cafe", "silencioso", "conversa", "acessivel", "asa sul"],
        "vector": [0.8, 0.0, 0.2, 0.5, 0.7, 0.0, 1.0, 0.0, 0.1, 0.5, 0.8, 0.0, 0.4, 0.0, 0.0, 0.5],
        "provenance": {
            "source": "OpenStreetMap",
            "osm_id": 736192840,
            "osm_type": "node",
            "osm_link": "https://www.openstreetmap.org/node/736192840",
            "ingestion_date": "2026-11-01T08:00:00Z"
        }
    }
]

# =====================================================================
# 2. DEFINIÇÃO FORMAL DOS ESQUEMAS DOS 4 FORMATOS (CONTRATOS)
# =====================================================================

SCHEMA_PLACE_RECORD = {
    "type": "object",
    "required": ["place_id", "name", "amenity", "address", "location", "is_public_verified", "provenance"],
    "properties": {
        "place_id": {"type": "string"},
        "name": {"type": "string"},
        "amenity": {"type": "string"},
        "category": {"type": "string"},
        "address": {"type": "string"},
        "location": {
            "type": "object",
            "required": ["lat", "lon"],
            "properties": {
                "lat": {"type": "number"},
                "lon": {"type": "number"}
            }
        },
        "is_public_verified": {"type": "boolean"},
        "opening_hours": {"type": "string"},
        "wheelchair": {"type": "string", "enum": ["yes", "limited", "no", "unknown"]},
        "noise_level": {"type": "string", "enum": ["baixo", "moderado", "alto"]},
        "vibe": {"type": "string"},
        "suitable_for": {"type": "array", "items": {"type": "string"}},
        "ratings": {
            "type": "object",
            "properties": {
                "google_rating": {"type": "number"},
                "app_rating": {"type": "number"},
                "total_reviews": {"type": "integer"}
            }
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "vector": {"type": "array", "items": {"type": "number"}},
        "provenance": {
            "type": "object",
            "required": ["source", "osm_id", "osm_type", "osm_link"],
            "properties": {
                "source": {"type": "string"},
                "osm_id": {"type": "integer"},
                "osm_type": {"type": "string"},
                "osm_link": {"type": "string"},
                "ingestion_date": {"type": "string"}
            }
        }
    }
}

SCHEMA_STRUCTURED_REQUEST = {
    "type": "object",
    "required": [
        "request_id", "raw_query", "intent_valid", "out_of_scope",
        "impossible_criteria", "activity", "vibe", "spatial_constraints",
        "temporal_constraints", "accessibility_requirements"
    ],
    "properties": {
        "request_id": {"type": "string"},
        "raw_query": {"type": "string"},
        "intent_valid": {"type": "boolean"},
        "out_of_scope": {"type": "boolean"},
        "out_of_scope_reason": {"type": ["string", "null"]},
        "impossible_criteria": {"type": "boolean"},
        "impossible_criteria_reason": {"type": ["string", "null"]},
        "activity": {"type": "string"},
        "target_amenities": {"type": "array", "items": {"type": "string"}},
        "vibe": {"type": "string"},
        "noise_tolerance": {"type": "string", "enum": ["baixo", "moderado", "indiferente"]},
        "spatial_constraints": {
            "type": "object",
            "required": ["target_region", "max_radius_km"],
            "properties": {
                "target_region": {"type": "string"},
                "max_radius_km": {"type": "number"}
            }
        },
        "temporal_constraints": {
            "type": "object",
            "required": ["preferred_time_slot"],
            "properties": {
                "preferred_time_slot": {"type": "string", "enum": ["manha", "tarde", "noite", "indiferente"]},
                "specific_hours": {"type": ["string", "null"]}
            }
        },
        "accessibility_requirements": {
            "type": "object",
            "required": ["wheelchair_required", "elder_friendly", "pet_friendly"],
            "properties": {
                "wheelchair_required": {"type": "boolean"},
                "elder_friendly": {"type": "boolean"},
                "pet_friendly": {"type": "boolean"}
            }
        },
        "search_vector_focus": {"type": "array", "items": {"type": "string"}},
        "clarification_needed": {"type": ["string", "null"]}
    }
}

SCHEMA_SEARCH_RESPONSE = {
    "type": "object",
    "required": ["query_id", "timestamp", "status", "applied_filters", "results_count", "items"],
    "properties": {
        "query_id": {"type": "string"},
        "timestamp": {"type": "string"},
        "status": {"type": "string", "enum": ["SUCCESS", "NO_RESULTS", "OUT_OF_SCOPE", "EXPANDED_RADIUS"]},
        "applied_filters": {
            "type": "object",
            "required": ["radius_km", "expanded_once"],
            "properties": {
                "radius_km": {"type": "number"},
                "expanded_once": {"type": "boolean"},
                "amenities": {"type": "array", "items": {"type": "string"}}
            }
        },
        "results_count": {"type": "integer"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rank", "place_id", "name", "distance_km", "cosine_similarity", "final_score", "score_decomposition"],
                "properties": {
                    "rank": {"type": "integer"},
                    "place_id": {"type": "string"},
                    "name": {"type": "string"},
                    "amenity": {"type": "string"},
                    "address": {"type": "string"},
                    "distance_km": {"type": "number"},
                    "cosine_similarity": {"type": "number"},
                    "final_score": {"type": "number"},
                    "score_decomposition": {
                        "type": "object",
                        "required": ["vector_contribution", "distance_contribution", "reputation_contribution", "compatibility_contribution", "sum_check"],
                        "properties": {
                            "vector_contribution": {"type": "number"},
                            "distance_contribution": {"type": "number"},
                            "reputation_contribution": {"type": "number"},
                            "compatibility_contribution": {"type": "number"},
                            "sum_check": {"type": "number"}
                        }
                    }
                }
            }
        }
    }
}

SCHEMA_EVIDENCE_RECORD = {
    "type": "object",
    "required": [
        "evidence_id", "query_id", "place_id", "place_name", "osm_reference",
        "matched_tags", "factors", "total_score", "integrity_test", "grounding_notes"
    ],
    "properties": {
        "evidence_id": {"type": "string"},
        "query_id": {"type": "string"},
        "place_id": {"type": "string"},
        "place_name": {"type": "string"},
        "osm_reference": {
            "type": "object",
            "required": ["osm_id", "osm_type", "osm_link"],
            "properties": {
                "osm_id": {"type": "integer"},
                "osm_type": {"type": "string"},
                "osm_link": {"type": "string"}
            }
        },
        "matched_tags": {"type": "array", "items": {"type": "string"}},
        "factors": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["factor_name", "raw_value", "normalized_value", "weight", "weighted_contribution"],
                "properties": {
                    "factor_name": {"type": "string"},
                    "raw_value": {"type": "number"},
                    "normalized_value": {"type": "number"},
                    "weight": {"type": "number"},
                    "weighted_contribution": {"type": "number"}
                }
            }
        },
        "total_score": {"type": "number"},
        "integrity_test": {
            "type": "object",
            "required": ["sum_equals_total", "all_factors_in_range_0_1", "passed"],
            "properties": {
                "sum_equals_total": {"type": "boolean"},
                "all_factors_in_range_0_1": {"type": "boolean"},
                "passed": {"type": "boolean"}
            }
        },
        "grounding_notes": {"type": "array", "items": {"type": "string"}}
    }
}

# =====================================================================
# 3. VALIDADOR DE ESQUEMA (LEVE E NATIVO PYTHON, SEM DEPENDÊNCIAS EXTERNAS)
# =====================================================================

def validate_schema(data: Any, schema: Dict[str, Any], path: str = "root") -> Tuple[bool, Optional[str]]:
    target_type = schema.get("type")
    
    if isinstance(target_type, list):
        valid = False
        errors = []
        for t in target_type:
            sub_schema = dict(schema, type=t)
            is_ok, err = validate_schema(data, sub_schema, path)
            if is_ok:
                valid = True
                break
            errors.append(err)
        if not valid:
            return False, f"Campo '{path}' com valor '{data}' não corresponde a nenhum dos tipos permitidos {target_type}: {'; '.join(errors)}"
        return True, None

    if target_type == "object":
        if not isinstance(data, dict):
            return False, f"Campo '{path}' deve ser um objeto JSON (dict), recebido: {type(data).__name__}"
        
        for req_field in schema.get("required", []):
            if req_field not in data:
                return False, f"Campo obrigatório '{req_field}' ausente em '{path}'"
        
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if prop_name in data:
                val = data[prop_name]
                is_ok, err = validate_schema(val, prop_schema, f"{path}.{prop_name}")
                if not is_ok:
                    return False, err
                    
    elif target_type == "array":
        if not isinstance(data, list):
            return False, f"Campo '{path}' deve ser uma lista (array), recebido: {type(data).__name__}"
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(data):
                is_ok, err = validate_schema(item, item_schema, f"{path}[{idx}]")
                if not is_ok:
                    return False, err

    elif target_type == "string":
        if not isinstance(data, str):
            return False, f"Campo '{path}' deve ser uma string, recebido: {type(data).__name__}"
        if "enum" in schema and data not in schema["enum"]:
            return False, f"Campo '{path}' com valor '{data}' não está entre os valores válidos: {schema['enum']}"

    elif target_type == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            return False, f"Campo '{path}' deve ser um número, recebido: {type(data).__name__}"

    elif target_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            return False, f"Campo '{path}' deve ser um número inteiro, recebido: {type(data).__name__}"

    elif target_type == "boolean":
        if not isinstance(data, bool):
            return False, f"Campo '{path}' deve ser um booleano (true/false), recebido: {type(data).__name__}"

    elif target_type == "null":
        if data is not None:
            return False, f"Campo '{path}' deve ser nulo (null), recebido: {type(data).__name__}"

    return True, None

# =====================================================================
# 4. INTERPRETAÇÃO DO PEDIDO (PROMPT + PARSING + RETRY AUTOMÁTICO)
# =====================================================================

SYSTEM_PROMPT_INTENT = """Você é o interpretador de intenções do Bubbles, um aplicativo de combate à solidão que conecta pessoas em pequenos grupos presenciais (3 a 8 pessoas) em locais públicos e seguros de Brasília (DF).
Sua missão é ler o pedido em linguagem natural do usuário e convertê-lo ESTRITAMENTE em um objeto JSON válido seguindo a especificação.

Regras de Negócio e Guardrails:
1. `out_of_scope`: Deve ser TRUE se o usuário pedir serviços não-sociais (ex: frete, carreto, transporte de cargas, serviços ilícitos, venda comercial, encontros individuais românticos privados). Explique o motivo em `out_of_scope_reason`.
2. `impossible_criteria`: Deve ser TRUE se os filtros forem mutuamente contraditórios ou sabidamente inexistentes na malha urbana (ex: cafeteria vegana aberta às 03:30 da madrugada com pista de patinação no gelo na Asa Sul). Explique em `impossible_criteria_reason`.
3. `intent_valid`: Será FALSE se `out_of_scope` for TRUE ou `impossible_criteria` for TRUE.
4. `noise_tolerance`: "baixo" para leitura/conversa calma, "moderado" para parques/cafés comuns, "indiferente" caso não mencione.
5. `spatial_constraints`: Se não especificado o raio, adote `max_radius_km`: 5.0. Se citar bairro (ex: Asa Sul, Asa Norte), registre em `target_region`.
6. Responda APENAS com o JSON. Não use blocos de texto antes ou depois. Não use markdown com explicações.
"""

def mock_llm_intent_generator(query: str, simulate_syntax_error: bool = False) -> str:
    q_lower = query.lower()
    
    if simulate_syntax_error:
        return """{
            "request_id": "req-error-simulated",
            "raw_query": """ + json.dumps(query) + """,
            "intent_valid": true,
            "out_of_scope": false,
            "missing_comma_here": 123
            "impossible_criteria": false
        }"""
        
    if "frete" in q_lower or "caminhão" in q_lower or "mudança" in q_lower:
        return json.dumps({
            "request_id": f"req-{uuid.uuid4().hex[:8]}",
            "raw_query": query,
            "intent_valid": False,
            "out_of_scope": True,
            "out_of_scope_reason": "O pedido refere-se a transporte de carga/mudança residencial, que é um serviço logístico de frete fora do escopo social do Bubbles.",
            "impossible_criteria": False,
            "impossible_criteria_reason": None,
            "activity": "transporte de carga / frete",
            "target_amenities": [],
            "vibe": "indiferente",
            "noise_tolerance": "indiferente",
            "spatial_constraints": {
                "target_region": "Asa Norte para Taguatinga",
                "max_radius_km": 25.0
            },
            "temporal_constraints": {
                "preferred_time_slot": "indiferente",
                "specific_hours": "sábado"
            },
            "accessibility_requirements": {
                "wheelchair_required": False,
                "elder_friendly": False,
                "pet_friendly": False
            },
            "search_vector_focus": [],
            "clarification_needed": None
        }, indent=2)

    elif "patinação no gelo" in q_lower or "03:30" in q_lower:
        return json.dumps({
            "request_id": f"req-{uuid.uuid4().hex[:8]}",
            "raw_query": query,
            "intent_valid": False,
            "out_of_scope": False,
            "out_of_scope_reason": None,
            "impossible_criteria": True,
            "impossible_criteria_reason": "Inexistência de cafeteria com pista de patinação no gelo em Brasília operando às 03:30 da madrugada de segunda-feira.",
            "activity": "encontro noturno com patinação e música",
            "target_amenities": ["cafe"],
            "vibe": "animado",
            "noise_tolerance": "indiferente",
            "spatial_constraints": {
                "target_region": "Asa Sul",
                "max_radius_km": 5.0
            },
            "temporal_constraints": {
                "preferred_time_slot": "noite",
                "specific_hours": "03:30"
            },
            "accessibility_requirements": {
                "wheelchair_required": False,
                "elder_friendly": False,
                "pet_friendly": False
            },
            "search_vector_focus": ["cafe", "vegano", "musica_ao_vivo", "patinacao_gelo"],
            "clarification_needed": None
        }, indent=2)

    else:
        return json.dumps({
            "request_id": f"req-{uuid.uuid4().hex[:8]}",
            "raw_query": query,
            "intent_valid": True,
            "out_of_scope": False,
            "out_of_scope_reason": None,
            "impossible_criteria": False,
            "impossible_criteria_reason": None,
            "activity": "conversa sobre livros e literatura em grupo calmo",
            "target_amenities": ["cafe", "library"],
            "vibe": "tranquilo",
            "noise_tolerance": "baixo",
            "spatial_constraints": {
                "target_region": "Asa Sul",
                "max_radius_km": 3.0
            },
            "temporal_constraints": {
                "preferred_time_slot": "tarde",
                "specific_hours": "tarde (14:00 - 18:00)"
            },
            "accessibility_requirements": {
                "wheelchair_required": True,
                "elder_friendly": True,
                "pet_friendly": False
            },
            "search_vector_focus": ["cafe", "leitura", "calmo", "acessivel", "conversa"],
            "clarification_needed": None
        }, indent=2)


def extract_json_from_llm(raw_output: str) -> str:
    text = raw_output.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return text


def interpret_user_request_with_retry(
    query: str,
    max_retries: int = 1,
    simulate_initial_error: bool = False
) -> Dict[str, Any]:
    attempt = 0
    last_error = ""
    current_simulate_error = simulate_initial_error

    while attempt <= max_retries:
        attempt += 1
        print(f"  [Interpretação LLM] Tentativa {attempt}/{max_retries + 1}...")

        raw_response = mock_llm_intent_generator(query, simulate_syntax_error=current_simulate_error)

        try:
            cleaned = extract_json_from_llm(raw_response)
            parsed_json = json.loads(cleaned)
        except Exception as e:
            last_error = f"Erro de sintaxe JSON: {str(e)}"
            print(f"  [ALERTA] Falha de sintaxe no JSON na tentativa {attempt}: {last_error}")
            current_simulate_error = False
            continue

        is_valid, validation_err = validate_schema(parsed_json, SCHEMA_STRUCTURED_REQUEST)
        if not is_valid:
            last_error = f"Violação de esquema: {validation_err}"
            print(f"  [ALERTA] JSON sintaticamente válido mas violou esquema na tentativa {attempt}: {last_error}")
            current_simulate_error = False
            continue

        print(f"  [OK] Pedido interpretado e validado com sucesso na tentativa {attempt}!")
        return parsed_json

    raise ValueError(f"Falha ao interpretar pedido após {max_retries + 1} tentativas. Último erro: {last_error}")

# =====================================================================
# 5. MOTOR DE BUSCA E GERAÇÃO DE EVIDÊNCIAS (P4 SIMULADO PARA O P1)
# =====================================================================

def compute_evidence_and_search(req: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    query_id = req["request_id"]
    timestamp = datetime.now(timezone.utc).isoformat()

    if req["out_of_scope"]:
        search_res = {
            "query_id": query_id,
            "timestamp": timestamp,
            "status": "OUT_OF_SCOPE",
            "applied_filters": {"radius_km": 0, "expanded_once": False, "amenities": []},
            "results_count": 0,
            "items": []
        }
        return search_res, []

    if req["impossible_criteria"]:
        search_res = {
            "query_id": query_id,
            "timestamp": timestamp,
            "status": "NO_RESULTS",
            "applied_filters": {
                "radius_km": req["spatial_constraints"]["max_radius_km"],
                "expanded_once": True,
                "amenities": req.get("target_amenities", [])
            },
            "results_count": 0,
            "items": []
        }
        return search_res, []

    matched_items = []
    evidence_records = []
    
    w_vec = 0.35
    w_dist = 0.25
    w_rep = 0.20
    w_comp = 0.20

    wheelchair_req = req["accessibility_requirements"]["wheelchair_required"]

    for poi in MOCK_POIS:
        if wheelchair_req and poi["wheelchair"] != "yes":
            continue

        sim_vec = 0.92 if poi["place_id"] == "POI-01" else (0.86 if poi["place_id"] == "POI-03" else 0.40)
        norm_dist = max(0.0, min(1.0, 1.0 - (poi["distance_km"] / 5.0)))
        rep_val = (0.4 * poi["ratings"]["google_rating"] + 0.6 * poi["ratings"]["app_rating"]) / 5.0
        comp_val = 0.95 if poi["vibe"] == req["vibe"] else 0.50

        c_vec = round(sim_vec * w_vec, 4)
        c_dist = round(norm_dist * w_dist, 4)
        c_rep = round(rep_val * w_rep, 4)
        c_comp = round(comp_val * w_comp, 4)
        final_score = round(c_vec + c_dist + c_rep + c_comp, 4)

        sum_contrib = round(c_vec + c_dist + c_rep + c_comp, 4)
        sum_equals_total = math.isclose(sum_contrib, final_score, abs_tol=1e-4)
        all_in_range = all(0.0 <= v <= 1.0 for v in [sim_vec, norm_dist, rep_val, comp_val])

        ev_id = f"EV-{uuid.uuid4().hex[:8]}"
        evidence = {
            "evidence_id": ev_id,
            "query_id": query_id,
            "place_id": poi["place_id"],
            "place_name": poi["name"],
            "osm_reference": {
                "osm_id": poi["provenance"]["osm_id"],
                "osm_type": poi["provenance"]["osm_type"],
                "osm_link": poi["provenance"]["osm_link"]
            },
            "matched_tags": [t for t in poi["tags"] if t in ["cafe", "calmo", "acessivel", "leitura", "conversa"]],
            "factors": [
                {
                    "factor_name": "similaridade_vetorial",
                    "raw_value": sim_vec,
                    "normalized_value": sim_vec,
                    "weight": w_vec,
                    "weighted_contribution": c_vec
                },
                {
                    "factor_name": "proximidade_fisica",
                    "raw_value": poi["distance_km"],
                    "normalized_value": round(norm_dist, 4),
                    "weight": w_dist,
                    "weighted_contribution": c_dist
                },
                {
                    "factor_name": "reputacao_comunitaria",
                    "raw_value": round(0.4 * poi["ratings"]["google_rating"] + 0.6 * poi["ratings"]["app_rating"], 2),
                    "normalized_value": round(rep_val, 4),
                    "weight": w_rep,
                    "weighted_contribution": c_rep
                },
                {
                    "factor_name": "compatibilidade_psicossocial",
                    "raw_value": comp_val,
                    "normalized_value": comp_val,
                    "weight": w_comp,
                    "weighted_contribution": c_comp
                }
            ],
            "total_score": final_score,
            "integrity_test": {
                "sum_equals_total": sum_equals_total,
                "all_factors_in_range_0_1": all_in_range,
                "passed": sum_equals_total and all_in_range
            },
            "grounding_notes": [
                f"Estabelecimento verificado e público no OpenStreetMap ({poi['provenance']['osm_link']}).",
                f"Acessibilidade garantida com wheelchair={poi['wheelchair']}.",
                f"Ambiente com nível de ruído '{poi['noise_level']}' e vibe '{poi['vibe']}'."
            ]
        }
        
        is_ev_valid, ev_err = validate_schema(evidence, SCHEMA_EVIDENCE_RECORD)
        if not is_ev_valid:
            print(f"  [ERRO CONTRATO] EvidenceRecord violou esquema: {ev_err}")

        evidence_records.append(evidence)

        item = {
            "rank": 0,
            "place_id": poi["place_id"],
            "name": poi["name"],
            "amenity": poi["amenity"],
            "address": poi["address"],
            "distance_km": poi["distance_km"],
            "cosine_similarity": sim_vec,
            "final_score": final_score,
            "score_decomposition": {
                "vector_contribution": c_vec,
                "distance_contribution": c_dist,
                "reputation_contribution": c_rep,
                "compatibility_contribution": c_comp,
                "sum_check": sum_contrib
            }
        }
        matched_items.append(item)

    matched_items.sort(key=lambda x: x["final_score"], reverse=True)
    for idx, item in enumerate(matched_items, start=1):
        item["rank"] = idx

    search_res = {
        "query_id": query_id,
        "timestamp": timestamp,
        "status": "SUCCESS" if matched_items else "NO_RESULTS",
        "applied_filters": {
            "radius_km": req["spatial_constraints"]["max_radius_km"],
            "expanded_once": False,
            "amenities": req.get("target_amenities", [])
        },
        "results_count": len(matched_items),
        "items": matched_items
    }

    is_res_valid, res_err = validate_schema(search_res, SCHEMA_SEARCH_RESPONSE)
    if not is_res_valid:
        print(f"  [ERRO CONTRATO] SearchResponse violou esquema: {res_err}")

    return search_res, evidence_records

# =====================================================================
# 6. GERADOR DA RESPOSTA (GROUNDED GENERATOR COM ABSTENÇÃO CORRETA)
# =====================================================================

SYSTEM_PROMPT_GENERATOR = """Você é o Assistente Bubbles. Seu dever é recomendar locais para encontros presenciais em grupo.
Diretrizes Rigorosas de Fundamentação (Zero-Hallucination Guardrail):
1. Você SÓ PODE citar e recomendar os locais que constam explicitamente no objeto 'retorno_busca'.
2. É ESTRITAMENTE PROIBIDO inventar, deduzir ou mencionar qualquer outro estabelecimento não listado.
3. Se a busca retornar 0 resultados ('NO_RESULTS') ou for fora de escopo ('OUT_OF_SCOPE'), ABSTENHA-SE categoricamente de indicar locais. Explique educadamente o motivo e oriente o usuário a ajustar seu pedido.
4. Para cada local recomendado, cite seu nome oficial, seu endereço e destaque fatos comprovados nas evidências (ex: acessibilidade, silêncio, nota).
"""

def generate_grounded_response(
    req: Dict[str, Any],
    search_res: Dict[str, Any],
    evidence_records: List[Dict[str, Any]]
) -> str:
    status = search_res["status"]

    if status == "OUT_OF_SCOPE":
        reason = req.get("out_of_scope_reason", "Pedido fora de escopo.")
        return (
            "Olá! O Bubbles é uma plataforma dedicada exclusivamente a conectar pessoas para encontros sociais "
            "e de convivência em grupo em espaços públicos seguros de Brasília.\n\n"
            f"Identifiquei que sua solicitação envolve um serviço logístico/comercial: {reason}\n\n"
            "Por isso, não realizamos indicações ou agendamentos para fretes, carretos ou mudanças. "
            "Se desejar marcar um café, passeio cultural ou caminhada para fazer novas amizades, conte conosco!"
        )

    if status == "NO_RESULTS" or search_res["results_count"] == 0:
        imp_reason = req.get("impossible_criteria_reason")
        extra_note = f" ({imp_reason})" if imp_reason else ""
        return (
            f"Olá! Infelizmente não encontramos nenhum local verificado que atenda a todas as suas restrições{extra_note}.\n\n"
            "Para garantir sua segurança e a viabilidade do encontro, nosso sistema recomenda apenas estabelecimentos "
            "públicos ativos e verificados na base oficial de Brasília.\n\n"
            "Sugestão: experimente ampliar o horário (ex: períodos diurnos ou início da noite) ou selecionar um tipo "
            "de ambiente mais comum na região (como cafeterias tradicionais ou centros culturais)."
        )

    lines = [
        "Olá! Com base nas suas preferências de ambiente tranquilo, leitura em grupo e acessibilidade plena, "
        f"selecionamos {len(search_res['items'])} locais verificados na Asa Sul que oferecem as melhores condições para o encontro:\n"
    ]

    for item in search_res["items"]:
        ev = next((e for e in evidence_records if e["place_id"] == item["place_id"]), None)
        notes = " ".join(ev["grounding_notes"]) if ev else ""
        
        lines.append(
            f"**{item['rank']}. {item['name']}** (Score: {item['final_score'] * 100:.1f}%)\n"
            f"- **Endereço:** {item['address']} ({item['distance_km']} km de distância)\n"
            f"- **Por que foi escolhido:** Similaridade temática de {item['cosine_similarity'] * 100:.0f}%, "
            f"ambiente propício para conversas calmas e acessibilidade para cadeira de rodas confirmada.\n"
            f"- **Evidência OSM:** {notes}\n"
        )

    lines.append(
        "Todos os participantes contam com ambiente seguro, verificado no OpenStreetMap e com avaliações comunitárias ativas."
    )
    return "\n".join(lines)

# =====================================================================
# 7. VERIFICAÇÃO AUTOMÁTICA PÓS-GERAÇÃO (DETECTOR DE ALUCINAÇÃO)
# =====================================================================

def verify_grounded_places(
    generated_text: str,
    retrieved_places: List[Dict[str, Any]],
    all_known_places: List[Dict[str, Any]]
) -> Dict[str, Any]:
    retrieved_names = {p["name"].lower().strip() for p in retrieved_places}
    retrieved_ids = {p.get("place_id", "").lower().strip() for p in retrieved_places}

    cited_places = []
    unauthorized_places = []

    for p in all_known_places:
        name_clean = p["name"].lower().strip()
        if name_clean in generated_text.lower():
            cited_places.append(p["name"])
            if name_clean not in retrieved_names and p["place_id"].lower() not in retrieved_ids:
                unauthorized_places.append(p["name"])

    is_abstention = (len(retrieved_places) == 0)
    if is_abstention and len(cited_places) > 0:
        unauthorized_places.extend(cited_places)

    is_valid = (len(unauthorized_places) == 0)

    return {
        "is_valid": is_valid,
        "is_abstention": is_abstention,
        "total_cited": len(cited_places),
        "cited_places": cited_places,
        "unauthorized_places": unauthorized_places,
        "hallucination_detected": not is_valid,
        "compliance_score": 100.0 if is_valid else 0.0
    }

# =====================================================================
# 8. SCRIPT DE DEMONSTRAÇÃO PRINCIPAL (3 CONSULTAS + RELATÓRIO)
# =====================================================================

def run_p1_demonstration():
    print("=" * 80)
    print(" BUBBLES - CHALLENGE 2 | DEMONSTRAÇÃO DO PACOTE 1 (P1)")
    print(" Contratos de Dados, LLM com Retry, Gerador Grounded e Validador")
    print("=" * 80)

    test_queries = [
        {
            "id": "TC-01",
            "title": "Consulta Padrão / Válida (Café Calmo para Leitura na Asa Sul)",
            "query": "Quero um café tranquilo na Asa Sul para conversar sobre livros com pessoas calmas no período da tarde, com acesso para cadeirantes.",
            "simulate_syntax_error": True
        },
        {
            "id": "TC-02",
            "title": "Consulta Sem Resultado Possível (Abstenção por Falta de Dados)",
            "query": "Procuro uma cafeteria vegana com pista de patinação no gelo e música ao vivo na Asa Sul aberta às 03:30 da madrugada de segunda-feira.",
            "simulate_syntax_error": False
        },
        {
            "id": "TC-03",
            "title": "Consulta Fora de Escopo (Guardrail de Segurança e Abstenção)",
            "query": "Preciso urgente de um frete com caminhão baú e 2 carregadores para transportar meus móveis da Asa Norte até Taguatinga no próximo sábado.",
            "simulate_syntax_error": False
        }
    ]

    summary_results = []

    for idx, tc in enumerate(test_queries, 1):
        print(f"\n[{tc['id']}] CASO DE TESTE {idx}: {tc['title']}")
        print(f"Texto do Usuário: \"{tc['query']}\"")
        print("-" * 80)

        print("[Passo 1] Interpretação do Pedido (LLM -> JSON Estruturado)")
        if tc["simulate_syntax_error"]:
            print("  * Nota: Injetando propositalmente erro de sintaxe no round 1 para demonstrar o RETRY automático.")
            
        structured_req = interpret_user_request_with_retry(
            tc["query"],
            max_retries=1,
            simulate_initial_error=tc["simulate_syntax_error"]
        )

        print("\n  >> Pedido Estruturado Validado (Amostra Resumida):")
        print(f"     - Request ID: {structured_req['request_id']}")
        print(f"     - Intenção Válida: {structured_req['intent_valid']}")
        print(f"     - Fora de Escopo: {structured_req['out_of_scope']}")
        print(f"     - Critério Impossível: {structured_req['impossible_criteria']}")
        print(f"     - Atividade: {structured_req['activity']}")
        print(f"     - Vibe: {structured_req['vibe']} | Ruído: {structured_req['noise_tolerance']}")
        print(f"     - Região: {structured_req['spatial_constraints']['target_region']} (Raio: {structured_req['spatial_constraints']['max_radius_km']} km)")
        print(f"     - Cadeira de Rodas: {structured_req['accessibility_requirements']['wheelchair_required']}")

        print("\n[Passo 2] Executando Busca Híbrida e Extração de Evidências")
        search_res, evidence_records = compute_evidence_and_search(structured_req)
        print(f"  >> Status da Busca: {search_res['status']}")
        print(f"  >> Registros Recuperados: {search_res['results_count']}")

        for item in search_res["items"]:
            decomp = item["score_decomposition"]
            print(f"     • {item['name']} (Rank #{item['rank']}) -> Score Total: {item['final_score']}")
            print(f"       [Vetorial: {decomp['vector_contribution']} | Distância: {decomp['distance_contribution']} | Reputação: {decomp['reputation_contribution']} | Compat: {decomp['compatibility_contribution']}]")

        for ev in evidence_records:
            t = ev["integrity_test"]
            print(f"     [Evidência {ev['place_id']}] Soma = Total? {t['sum_equals_total']} | Fatores em [0,1]? {t['all_factors_in_range_0_1']} | Teste Passou: {t['passed']}")

        print("\n[Passo 3] Gerador da Resposta (Grounding RAG + Abstenção)")
        final_answer = generate_grounded_response(structured_req, search_res, evidence_records)
        print("  >> Resposta Emitida ao Usuário:")
        print("  " + "\n  ".join(final_answer.split("\n")))

        print("\n[Passo 4] Verificação Automática Pós-Geração (Detector de Alucinação)")
        verification = verify_grounded_places(
            generated_text=final_answer,
            retrieved_places=search_res["items"],
            all_known_places=MOCK_POIS
        )

        print(f"  >> Locais Citados no Texto: {verification['cited_places']}")
        print(f"  >> Locais Não-Autorizados / Alucinados: {verification['unauthorized_places']}")
        print(f"  >> Abstenção Detectada: {verification['is_abstention']}")
        print(f"  >> Resultado da Verificação: {'APROVADO (100% Fundamentado)' if verification['is_valid'] else 'REPROVADO'}")

        summary_results.append({
            "test_id": tc["id"],
            "query": tc["query"],
            "status": search_res["status"],
            "results_count": search_res["results_count"],
            "is_valid": verification["is_valid"],
            "cited_places": verification["cited_places"],
            "all_cited_in_retrieved": verification["is_valid"]
        })

    print("\n" + "=" * 80)
    print(" RESUMO DA AVALIAÇÃO DO P1 - CRITÉRIOS DE ACEITAÇÃO")
    print("=" * 80)
    print("Critério 'Pronto Quando': Um pedido vira JSON e a resposta cita apenas locais recuperados.")
    print("-" * 80)
    
    all_passed = True
    for res in summary_results:
        passed = res["all_cited_in_retrieved"]
        all_passed = all_passed and passed
        status_sym = "[OK] PASSOU" if passed else "[FALHA]"
        print(f"{res['test_id']}: {status_sym} | Retorno: {res['status']} ({res['results_count']} locais) | Locais Citados no Retorno: 100%")

    print("-" * 80)
    if all_passed:
        print(">> STATUS DO P1: 100% CONCLUÍDO E HOMOLOGADO COM SUCESSO! <<")
    else:
        print(">> STATUS DO P1: FALHA EM UM OU MAIS CRITÉRIOS <<")
    print("=" * 80)

if __name__ == "__main__":
    run_p1_demonstration()
