"""Contratos de dados do Bubbles (Contratos 2, 3 e 4) como modelos Pydantic.

Por que Pydantic? Cada agente devolve dados "soltos" (dict / JSON de LLM).
Pydantic transforma isso em objetos tipados e LANCA ERRO se faltar campo
obrigatorio ou o tipo estiver errado. Assim o orquestrador barra payload ruim
antes que ele chegue ao proximo agente.

Referencia dos campos: docs/p1_contratos_llm_demonstracao.md (secao 1).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    # extra="forbid": campo desconhecido tambem e erro (pega typos do LLM).
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Contrato 2 - structured_request (saida do NLU_Guardrail_Agent)
# --------------------------------------------------------------------------
class SpatialConstraints(Contract):
    target_region: str | None = None
    max_radius_km: float = Field(default=5.0, gt=0)


class TemporalConstraints(Contract):
    preferred_time_slot: str | None = None
    specific_hours: str | None = None


class AccessibilityRequirements(Contract):
    wheelchair_required: bool = False
    elder_friendly: bool = False
    pet_friendly: bool = False


class StructuredRequest(Contract):
    request_id: str
    # RNF02: o texto livre do usuario e descartado logo apos o NLU. Por isso
    # aqui e opcional: o NLU o usa para extrair e o orquestrador o zera.
    raw_query: str | None = None
    intent_valid: bool
    out_of_scope: bool
    out_of_scope_reason: str | None = None
    impossible_criteria: bool
    impossible_criteria_reason: str | None = None
    activity: str
    target_amenities: list[str]
    vibe: str
    noise_tolerance: Literal["baixo", "moderado", "indiferente"]
    spatial_constraints: SpatialConstraints
    temporal_constraints: TemporalConstraints
    accessibility_requirements: AccessibilityRequirements
    search_vector_focus: list[str] = Field(default_factory=list)
    clarification_needed: str | None = None

    @model_validator(mode="after")
    def _consistent_flags(self):
        """Barra saidas contraditorias do LLM (o retry do NLU tenta de novo)."""
        blocked = self.out_of_scope or self.impossible_criteria
        if blocked and self.intent_valid:
            raise ValueError("intent_valid=true e incompativel com out_of_scope/impossible_criteria")
        if not blocked and not self.intent_valid:
            raise ValueError("intent_valid=false exige out_of_scope ou impossible_criteria")
        if self.out_of_scope and not self.out_of_scope_reason:
            raise ValueError("out_of_scope=true exige out_of_scope_reason")
        if self.impossible_criteria and not self.impossible_criteria_reason:
            raise ValueError("impossible_criteria=true exige impossible_criteria_reason")
        return self


# --------------------------------------------------------------------------
# Contrato 3 - search_response (saida do Retrieval_Agent)
# --------------------------------------------------------------------------
class AppliedFilters(Contract):
    radius_km: float
    expanded_once: bool
    amenities: list[str]


class ScoreDecomposition(Contract):
    vector_contribution: float
    distance_contribution: float
    reputation_contribution: float
    compatibility_contribution: float
    sum_check: float


class SearchItem(Contract):
    rank: int = Field(ge=1)
    place_id: str
    name: str
    amenity: str | None = None
    address: str | None = None
    distance_km: float = Field(ge=0)
    cosine_similarity: float = Field(ge=0, le=1)
    final_score: float = Field(ge=0, le=1)
    score_decomposition: ScoreDecomposition
    # Metadados do OpenStreetMap, vindos de `places` no PostgreSQL. O Validation_Agent
    # audita SO o que chega aqui (RNF01): sem osm_id valido ou sem
    # is_public_verified=True o candidato e reprovado.
    osm_id: int | None = None
    osm_type: str | None = None  # node | way | relation
    osm_tags: dict[str, str] = Field(default_factory=dict)  # wheelchair, noise_level, opening_hours...
    is_public_verified: bool | None = None


class SearchResponse(Contract):
    query_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["SUCCESS", "NO_RESULTS", "OUT_OF_SCOPE", "EXPANDED_RADIUS"]
    applied_filters: AppliedFilters
    results_count: int = Field(ge=0)
    items: list[SearchItem]


# --------------------------------------------------------------------------
# Contrato 4 - evidence_record (saida do Validation_Agent)
# --------------------------------------------------------------------------
class OsmReference(Contract):
    osm_id: int
    osm_type: str
    osm_link: str


class ScoreFactor(Contract):
    factor_name: str
    raw_value: float
    normalized_value: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1)
    weighted_contribution: float


class IntegrityTest(Contract):
    sum_equals_total: bool
    all_factors_in_range_0_1: bool
    passed: bool


class EvidenceRecord(Contract):
    evidence_id: str
    query_id: str
    place_id: str
    place_name: str
    osm_reference: OsmReference
    matched_tags: list[str]
    factors: list[ScoreFactor]
    total_score: float
    integrity_test: IntegrityTest
    grounding_notes: list[str]


# --------------------------------------------------------------------------
# Feedback Validation_Agent -> Retrieval_Agent (loop de reconsulta)
# Nao e um dos 3 contratos oficiais, mas o loop precisa de um formato fixo.
# --------------------------------------------------------------------------
class ValidationFeedback(Contract):
    approved: bool
    rejected_place_ids: list[str] = Field(default_factory=list)
    # Ex.: {"wheelchair": "yes"} -> Retrieval aplica filtro rigido na reconsulta.
    hard_filters: dict[str, str] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
