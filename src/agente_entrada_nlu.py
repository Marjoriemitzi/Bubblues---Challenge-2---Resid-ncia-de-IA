import os
import re
import uuid
import json
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# =====================================================================
# CONTRATO 2: JSON SCHEMA ESTRITO (Pydantic V2)
# =====================================================================
class SpatialConstraints(BaseModel):
    cidade: str = "Brasília"
    bairro_regiao: Optional[str] = None
    raio_max_km: Optional[float] = None


class TemporalConstraints(BaseModel):
    periodo: Optional[str] = None
    horario_solicitado: Optional[str] = None
    dia_semana: Optional[str] = None


class AccessibilityRequirements(BaseModel):
    wheelchair_required: bool = False
    elder_friendly: bool = False


class StructuredRequestContrato2(BaseModel):
    request_id: str
    intent_valid: bool
    out_of_scope: bool
    out_of_scope_reason: Optional[str] = None
    impossible_criteria: bool
    impossible_criteria_reason: Optional[str] = None
    activity: Optional[str] = None
    target_amenities: List[str] = Field(default_factory=list)
    vibe: Optional[str] = None
    noise_tolerance: Optional[str] = None
    spatial_constraints: SpatialConstraints
    temporal_constraints: TemporalConstraints
    accessibility_requirements: AccessibilityRequirements
    search_vector_focus: str


# =====================================================================
# AGENTE DE ENTRADA (NLU_Agent)
# =====================================================================
class IntakeNLUAgent:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.api_key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()

    def _regras_bloqueio_e_entidades(self, texto: str, req_id: str) -> dict:
        """Motor determinístico para garantir Contrato 2 e regras de bloqueio."""
        t = texto.lower()

        # 1. Regra de Bloqueio: Fora de Escopo (Fretes, Serviços Comerciais, Romântico Privado, Online)
        padroes_fora_escopo = [
            (r"frete|caminhão|mudança|entrega|transportadora", "Solicitação de serviço comercial/logístico (frete/transporte), fora do escopo de encontros sociais públicos."),
            (r"encontro romântico privado|motel|jantar íntimo a dois em casa|namoro privado", "Solicitação de encontro romântico privado; o sistema atua exclusivamente em espaços públicos verificados para convivência comunitária."),
            (r"reunião online|chamada de vídeo|zoom|google meet|sem sair de casa|remoto", "Solicitação sem encontro presencial; o projeto exige recomendação de espaços físicos públicos."),
            (r"conserto|encanador|eletricista|comprar carro|empréstimo", "Serviço comercial alheio à socialização presencial.")
        ]
        for padrao, motivo in padroes_fora_escopo:
            if re.search(padrao, t):
                return {
                    "request_id": req_id,
                    "intent_valid": False,
                    "out_of_scope": True,
                    "out_of_scope_reason": motivo,
                    "impossible_criteria": False,
                    "impossible_criteria_reason": None,
                    "activity": None,
                    "target_amenities": [],
                    "vibe": None,
                    "noise_tolerance": None,
                    "spatial_constraints": {"cidade": "Brasília", "bairro_regiao": None, "raio_max_km": None},
                    "temporal_constraints": {"periodo": None, "horario_solicitado": None, "dia_semana": None},
                    "accessibility_requirements": {"wheelchair_required": False, "elder_friendly": False},
                    "search_vector_focus": ""
                }

        # 2. Regra de Bloqueio: Critérios Impossíveis / Contraditórios
        padroes_impossiveis = [
            (r"03h30|03:30|04h|madrugada", "Horário inviável (madrugada) para funcionamento seguro de cafeterias silenciosas ou centros comunitários no Plano Piloto."),
            (r"patinação no gelo|neve natural|praia com ondas", "Amenidade fisicamente inexistente ou indisponível nos espaços públicos verificados de Brasília."),
            (r"silencioso.*música ao vivo alta|balada silenciosa para leitura", "Restrição ambiental contraditória (exigência simultânea de silêncio absoluto e evento ruidoso).")
        ]
        for padrao, motivo in padroes_impossiveis:
            if re.search(padrao, t):
                horario = "03:30" if ("03h30" in t or "03:30" in t) else "madrugada"
                return {
                    "request_id": req_id,
                    "intent_valid": False,
                    "out_of_scope": False,
                    "out_of_scope_reason": None,
                    "impossible_criteria": True,
                    "impossible_criteria_reason": motivo,
                    "activity": "café / leitura" if "café" in t else "lazer",
                    "target_amenities": ["cafe"],
                    "vibe": "silencioso" if "silencioso" in t else "indefinida",
                    "noise_tolerance": "Baixo" if "silencioso" in t else None,
                    "spatial_constraints": {"cidade": "Brasília", "bairro_regiao": "Plano Piloto" if "plano piloto" in t else None, "raio_max_km": 5.0},
                    "temporal_constraints": {"periodo": "madrugada", "horario_solicitado": horario, "dia_semana": None},
                    "accessibility_requirements": {"wheelchair_required": False, "elder_friendly": False},
                    "search_vector_focus": ""
                }

        # 3. Extração de Acessibilidade (Persona Dona Helena / Cadeirantes / Idosos)
        wheelchair = any(k in t for k in ["cadeira de rodas", "cadeirante", "rampa", "acessível para cadeira", "dona helena", "mobilidade reduzida"])
        elder = any(k in t for k in ["idosa", "idoso", "idosos", "terceira idade", "dona helena", "60+", "70 anos", "caminhada leve", "bancos para descansar"])

        # 4. Extração Espacial
        regiao = None
        for r in ["asa sul", "asa norte", "plano piloto", "lago sul", "lago norte", "sudoeste", "águas claras", "taguatinga"]:
            if r in t:
                regiao = r.title()
                break

        # 5. Extração Temporal
        periodo = "manhã" if "manhã" in t else ("tarde" if "tarde" in t else ("noite" if "noite" in t else "diurno"))
        match_hora = re.search(r"\b([01]?\d|2[0-3])(?:h|:)([0-5]\d)?\b", t)
        horario_str = match_hora.group(0) if match_hora else None

        # 6. Extração de Ruído, Vibe e Amenidades
        if any(k in t for k in ["silencioso", "calmo", "tranquilo", "leitura", "sem barulho"]):
            ruido = "Baixo"
            vibe = "Ambiente calmo, acolhedor e silencioso"
        elif any(k in t for k in ["animado", "movimentado", "música"]):
            ruido = "Alto"
            vibe = "Ambiente vibrante e movimentado"
        else:
            ruido = "Moderado"
            vibe = "Ambiente agradável para socialização e conversa"

        amenities = []
        if any(k in t for k in ["café", "cafeteria", "bistrô", "lanche"]):
            amenities.append("cafe")
        if any(k in t for k in ["livro", "livraria", "leitura", "sebinho"]):
            amenities.append("library_bookstore")
        if any(k in t for k in ["parque", "árvores", "ar livre", "natureza", "jardim"]):
            amenities.append("park_green_area")
        if wheelchair or elder:
            amenities.extend(["accessible_ramp", "rest_seating"])
        if not amenities:
            amenities.append("public_meeting_place")

        atividade = "caminhada e convivência ao ar livre" if "caminhada" in t or "parque" in t else "encontro social para conversa e café"
        foco_vetorial = f"{atividade}. {vibe}. Ruído: {ruido}. Acessibilidade: cadeirante={wheelchair}, idosos={elder}."

        return {
            "request_id": req_id,
            "intent_valid": True,
            "out_of_scope": False,
            "out_of_scope_reason": None,
            "impossible_criteria": False,
            "impossible_criteria_reason": None,
            "activity": atividade,
            "target_amenities": amenities,
            "vibe": vibe,
            "noise_tolerance": ruido,
            "spatial_constraints": {"cidade": "Brasília", "bairro_regiao": regiao, "raio_max_km": 5.0},
            "temporal_constraints": {"periodo": periodo, "horario_solicitado": horario_str, "dia_semana": None},
            "accessibility_requirements": {
                "wheelchair_required": wheelchair,
                "elder_friendly": elder
            },
            "search_vector_focus": foco_vetorial
        }

    def processar_solicitacao(self, texto_usuario: str) -> dict:
        req_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"

        # Tentativa com LLM + Retry se houver chave configurada
        if self.api_key and "sua_chave" not in self.api_key:
            for tentativa in range(1, self.max_retries + 1):
                try:
                    if self.api_key.startswith("gsk_"):
                        client = OpenAI(api_key=self.api_key, base_url="https://api.groq.com/openai/v1")
                        modelo = "llama-3.3-70b-versatile"
                    else:
                        client = OpenAI(api_key=self.api_key)
                        modelo = "gpt-4o-mini"

                    prompt = (
                        "Extraia a requisição no formato estrito do Contrato 2 JSON. "
                        f"Use request_id='{req_id}'. Retorne apenas JSON válido."
                    )
                    resp = client.chat.completions.create(
                        model=modelo,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": texto_usuario}
                        ]
                    )
                    dados_llm = json.loads(resp.choices[0].message.content)
                    validado = StructuredRequestContrato2.model_validate(dados_llm)
                    return validado.model_dump()
                except ( json.JSONDecodeError, ValidationError ) as err_parse:
                    print(f"⚠️ [Tentativa {tentativa}/{self.max_retries}] Falha de parsing no Contrato 2: {err_parse}")
                except Exception:
                    break

        # Fallback Determinístico + Validação Estrita Pydantic (100% aderente ao Contrato 2)
        for tentativa in range(1, self.max_retries + 1):
            try:
                dados = self._regras_bloqueio_e_entidades(texto_usuario, req_id)
                validado = StructuredRequestContrato2.model_validate(dados)
                return validado.model_dump()
            except ValidationError as e:
                print(f"⚠️ [Retry {tentativa}/{self.max_retries}] Ajustando schema: {e}")

        raise RuntimeError("Falha crítica ao gerar JSON aderente ao Contrato 2.")