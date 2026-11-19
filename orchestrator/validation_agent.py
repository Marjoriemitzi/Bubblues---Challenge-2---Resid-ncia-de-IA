"""Agente de Validação (Validation_Agent) do Bubbles.

Responsável por inspecionar o `search_response` antes que os resultados cheguem
ao usuário final, garantindo:
  1. Conformidade RNF01 (zero alucinação): todo POI aprovado deve possuir `osm_id`
     válido (> 0) e `is_public_verified == True`.
  2. Auditoria de Restrições Críticas: valida acessibilidade (`wheelchair_required`),
     tolerância de ruído (`noise_tolerance`), horários de funcionamento (`opening_hours`)
     e adequação para idosos (`elder_friendly`).
  3. Integridade Matemática: valida que |sum(contribuições) - score_total| < 1e-5
     e que fatores estão no intervalo [0, 1].
  4. Persistência: grava a auditoria (Contrato 4) em `evidencias_auditoria` (PostgreSQL), via EvidenceStore.
  5. Diagnóstico Estruturado e Hard Filters para o Retrieval_Agent em caso de reprovação.

Compatível com o orquestrador LangGraph (AgentState -> dict) e utilizável como módulo
autônomo em scripts e protótipos legados.
"""

from __future__ import annotations

import math
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .contracts import (
    EvidenceRecord,
    IntegrityTest,
    OsmReference,
    ScoreDecomposition,
    ScoreFactor,
    SearchItem,
    SearchResponse,
    StructuredRequest,
    ValidationFeedback,
)
from .evidence_store import EvidenceStore, PostgresEvidenceStore
from .state import AgentState


# Tags do OSM que entram em `matched_tags` do Contrato 4 (so as que o item realmente tem).
_TAGS_RELEVANTES = (
    "amenity", "leisure", "shop", "cuisine", "wheelchair",
    "noise_level", "nivel_ruido", "outdoor_seating", "elder_friendly",
)


def _metadados_do_item(cand: Dict[str, Any]) -> Dict[str, Any]:
    """Deriva wheelchair/noise_level/opening_hours/elder_friendly das `osm_tags` do item.

    So preenche o que a tag realmente informa; nada e inventado.
    """
    tags = cand.get("osm_tags") or {}
    out: Dict[str, Any] = {}
    if tags.get("wheelchair"):
        out["wheelchair"] = tags["wheelchair"]
    noise = tags.get("noise_level") or tags.get("nivel_ruido")
    if noise:
        out["noise_level"] = noise
    if tags.get("opening_hours"):
        out["opening_hours"] = tags["opening_hours"]
    elder = str(tags.get("elder_friendly", "")).strip().lower()
    if elder in ("yes", "true", "sim"):
        out["elder_friendly"] = True
    elif elder in ("no", "false", "nao", "não"):
        out["elder_friendly"] = False
    out["matched_tags"] = [f"{k}={tags[k]}" for k in _TAGS_RELEVANTES if tags.get(k)]
    return out


def _extrair_osm_id_e_tipo(osm_id_raw: Any, osm_type_raw: Optional[str] = None) -> Tuple[Optional[int], str]:
    """Extrai osm_id como inteiro positivo e osm_type (node/way/relation)."""
    if osm_id_raw is None:
        return None, osm_type_raw or "node"

    if isinstance(osm_id_raw, int):
        return (osm_id_raw if osm_id_raw > 0 else None), osm_type_raw or "node"

    osm_str = str(osm_id_raw).strip()
    osm_type = osm_type_raw or "node"

    if "/" in osm_str:
        partes = osm_str.split("/", 1)
        tipo = partes[0].strip().lower()
        if tipo in ("node", "way", "relation"):
            osm_type = tipo
        osm_str = partes[1].strip()

    match = re.search(r"\d+", osm_str)
    if not match:
        return None, osm_type

    try:
        val = int(match.group())
        return (val if val > 0 else None), osm_type
    except ValueError:
        return None, osm_type


def _verificar_horario(
    opening_hours: Optional[str],
    preferred_slot: Optional[str],
    specific_hours: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """Verifica compatibilidade entre horário de funcionamento e restrição temporal."""
    if not opening_hours or opening_hours.strip().lower() in ("24/7", "aberto", "unknown"):
        return True, None

    texto_tempo = f"{preferred_slot or ''} {specific_hours or ''}".strip().lower()
    if not texto_tempo:
        return True, None

    # Caso especial: madrugada (00:00 - 06:00) ou horários da madrugada
    if any(k in texto_tempo for k in ("madrugada", "03:30", "03h30", "04:00", "02:00")):
        # Se opening_hours indica funcionamento diurno convencional (ex: 07:00-20:00)
        match_hours = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", opening_hours)
        if match_hours:
            start_h = int(match_hours.group(1))
            end_h = int(match_hours.group(3))
            if start_h >= 6 and end_h <= 23:
                return (
                    False,
                    f"Horário de funcionamento '{opening_hours}' incompatível com pedido para a madrugada ({texto_tempo}).",
                )

    return True, None


class ValidationAgent:
    """Agente Auditor de Resultados de Busca do Sistema Bubbles."""

    TOLERANCIA_MATEMATICA = 1e-5

    def __init__(
        self,
        store: Optional[EvidenceStore] = None,
        metadata_catalog: Optional[Dict[str, Dict[str, Any]]] = None,
        min_approved: int = 1,
    ):
        # store=None: nao persiste (so testes/demos). Em producao use PostgresEvidenceStore;
        # `validation_agent` (abaixo) ja vem configurado assim.
        self.store = store
        self.min_approved = min_approved
        # Catalogo opcional, SO para testes/demos legados. Em producao os metadados
        # vem no proprio SearchItem (osm_id, osm_tags, is_public_verified).
        self.metadata_catalog = dict(metadata_catalog or {})

    def _obter_metadados(self, place_id: Optional[str], nome: Optional[str]) -> Dict[str, Any]:
        """Recupera metadados adicionais do catálogo local para validação."""
        if place_id and place_id in self.metadata_catalog:
            return dict(self.metadata_catalog[place_id])
        if nome and nome in self.metadata_catalog:
            return dict(self.metadata_catalog[nome])
        # Busca parcial por nome
        if nome:
            nome_norm = nome.strip().lower()
            for k, v in self.metadata_catalog.items():
                if k.strip().lower() in nome_norm or nome_norm in k.strip().lower():
                    return dict(v)
        return {}

    def auditar_candidato(
        self,
        structured_request: Union[Dict[str, Any], StructuredRequest],
        candidato: Union[Dict[str, Any], SearchItem],
    ) -> Dict[str, Any]:
        """Audita um único candidato contra o Contrato 2 (StructuredRequest)."""
        # Normalização dos inputs para dict
        if isinstance(structured_request, StructuredRequest):
            req_dict = structured_request.model_dump()
        else:
            req_dict = dict(structured_request)

        if isinstance(candidato, SearchItem):
            cand_dict = candidato.model_dump()
        else:
            cand_dict = dict(candidato)

        req_id = req_dict.get("request_id", "REQ-UNKNOWN")
        cand_id = cand_dict.get("place_id") or cand_dict.get("id") or "UNKNOWN-POI"
        nome = cand_dict.get("name") or cand_dict.get("nome") or "Estabelecimento Desconhecido"

        # Mescla metadados do catálogo
        meta = self._obter_metadados(cand_id, nome)
        # Ordem de precedencia: catalogo (so testes) < tags do item < campos explicitos do item.
        # Valores None nao sobrescrevem: ausencia de dado nao pode apagar dado conhecido.
        derivados = _metadados_do_item(cand_dict)
        explicitos = {k: v for k, v in cand_dict.items() if v is not None}
        merged_candidato = {**meta, **derivados, **explicitos}

        osm_id_raw = merged_candidato.get("osm_id")
        osm_type_raw = merged_candidato.get("osm_type")
        is_public_verified = merged_candidato.get("is_public_verified")

        parsed_osm_id, parsed_osm_type = _extrair_osm_id_e_tipo(osm_id_raw, osm_type_raw)

        motivos_rejeicao: List[str] = []
        diagnosticos: List[str] = []
        hard_filters: Dict[str, str] = {}

        # -----------------------------------------------------------------
        # 1. Verificação RNF01 (Zero Alucinação: osm_id válido e verificado)
        # -----------------------------------------------------------------
        osm_valido = parsed_osm_id is not None and parsed_osm_id > 0
        publico_verificado = (is_public_verified is True)
        rnf01_passed = osm_valido and publico_verificado

        if not osm_valido:
            motivos_rejeicao.append(f"RNF01 Violado: candidato '{nome}' sem osm_id válido no OpenStreetMap.")
            diagnosticos.append(
                f"Candidato '{nome}' ({cand_id}): RNF01 Violado: sem osm_id válido. Excluir candidatos fictícios."
            )
        if not publico_verificado:
            motivos_rejeicao.append(
                f"RNF01 Violado: candidato '{nome}' com is_public_verified != true (local não verificado)."
            )
            diagnosticos.append(
                f"Candidato '{nome}' ({cand_id}): RNF01 Violado: is_public_verified != true. Filtrar com WHERE is_public_verified = TRUE."
            )

        # -----------------------------------------------------------------
        # 2. Auditoria de Restrições Críticas (Acessibilidade, Ruído, Horário)
        # -----------------------------------------------------------------
        req_acess = req_dict.get("accessibility_requirements") or {}
        wheelchair_req = bool(req_acess.get("wheelchair_required", False))
        elder_req = bool(req_acess.get("elder_friendly", False))

        cand_wheelchair = str(merged_candidato.get("wheelchair", "")).strip().lower()
        cand_elder = merged_candidato.get("elder_friendly", True)

        constraints_passed = True

        # Restrição de cadeira de rodas
        if wheelchair_req:
            if cand_wheelchair in ("no", "false", "nao", "não", "none", ""):
                constraints_passed = False
                motivos_rejeicao.append(
                    f"Violação de Acessibilidade: requisição exige wheelchair_required=true, mas '{nome}' possui wheelchair='{cand_wheelchair or 'não informado'}'."
                )
                diagnosticos.append(
                    f"Candidato '{nome}' ({cand_id}): Violação de Acessibilidade: wheelchair='{cand_wheelchair}' incompatível com wheelchair_required=true."
                )
                hard_filters["wheelchair"] = "yes"

        # Restrição para idosos
        if elder_req and cand_elder is False:
            constraints_passed = False
            motivos_rejeicao.append(
                f"Violação de Acessibilidade: requisição exige elder_friendly=true, mas '{nome}' não é adequado para idosos."
            )
            diagnosticos.append(
                f"Candidato '{nome}' ({cand_id}): Violação de Acessibilidade: elder_friendly=false incompatível com elder_friendly=true."
            )
            hard_filters["elder_friendly"] = "true"

        # Restrição sensorial / nível de ruído
        noise_tolerance = req_dict.get("noise_tolerance", "indiferente")
        cand_noise = str(merged_candidato.get("noise_level") or merged_candidato.get("nivel_ruido") or "").strip().lower()
        if noise_tolerance in ("baixo", "moderado") and cand_noise in ("alto", "elevado", "barulhento"):
            constraints_passed = False
            motivos_rejeicao.append(
                f"Violação de Tolerância Sensorial: requisição possui tolerância '{noise_tolerance}', mas '{nome}' possui ruído '{cand_noise}'."
            )
            diagnosticos.append(
                f"Candidato '{nome}' ({cand_id}): Violação de Ruído: ruído '{cand_noise}' incompatível com tolerância '{noise_tolerance}'."
            )
            hard_filters["noise_level"] = "baixo" if noise_tolerance == "baixo" else "moderado"

        # Restrição de horário de funcionamento
        temporal = req_dict.get("temporal_constraints") or {}
        preferred_slot = temporal.get("preferred_time_slot")
        specific_hours = temporal.get("specific_hours")
        cand_hours = merged_candidato.get("opening_hours")
        horario_ok, motivo_horario = _verificar_horario(cand_hours, preferred_slot, specific_hours)
        if not horario_ok:
            constraints_passed = False
            motivos_rejeicao.append(f"Violação de Horário: {motivo_horario}")
            diagnosticos.append(f"Candidato '{nome}' ({cand_id}): {motivo_horario}")
            if preferred_slot:
                hard_filters["preferred_time_slot"] = preferred_slot
            if specific_hours:
                hard_filters["specific_hours"] = specific_hours

        # -----------------------------------------------------------------
        # 3. Integridade Matemática: |sum(contribuições) - score_total| < 1e-5
        # -----------------------------------------------------------------
        factors_list: List[Dict[str, Any]] = []
        score_total = float(cand_dict.get("final_score") if "final_score" in cand_dict else cand_dict.get("score_total", 0.0))

        # Caso venha no padrão Contrato 3 (ScoreDecomposition)
        score_decomp = cand_dict.get("score_decomposition")
        if isinstance(score_decomp, ScoreDecomposition):
            decomp_dict = score_decomp.model_dump()
        elif isinstance(score_decomp, dict):
            decomp_dict = score_decomp
        else:
            decomp_dict = None

        if decomp_dict:
            c_vec = float(decomp_dict.get("vector_contribution", 0.0))
            c_dist = float(decomp_dict.get("distance_contribution", 0.0))
            c_rep = float(decomp_dict.get("reputation_contribution", 0.0))
            c_comp = float(decomp_dict.get("compatibility_contribution", 0.0))
            soma_contrib = c_vec + c_dist + c_rep + c_comp
            contribuicoes_map = {
                "vector_contribution": c_vec,
                "distance_contribution": c_dist,
                "reputation_contribution": c_rep,
                "compatibility_contribution": c_comp,
            }

            # Monta ScoreFactors tipados para o Contrato 4
            cos_sim = float(cand_dict.get("cosine_similarity", 0.0))
            dist_km = float(cand_dict.get("distance_km", 0.0))
            factors_list = [
                {
                    "factor_name": "similaridade_vetorial",
                    "raw_value": cos_sim,
                    "normalized_value": max(0.0, min(1.0, cos_sim)),
                    "weight": 0.40,
                    "weighted_contribution": c_vec,
                },
                {
                    "factor_name": "proximidade_fisica",
                    "raw_value": dist_km,
                    "normalized_value": max(0.0, min(1.0, 1.0 / (1.0 + dist_km / 5.0))),
                    "weight": 0.25,
                    "weighted_contribution": c_dist,
                },
                {
                    "factor_name": "reputacao_comunitaria",
                    "raw_value": score_total,
                    "normalized_value": max(0.0, min(1.0, score_total)),
                    "weight": 0.15,
                    "weighted_contribution": c_rep,
                },
                {
                    "factor_name": "compatibilidade_psicossocial",
                    "raw_value": 1.0 if constraints_passed else 0.5,
                    "normalized_value": 1.0 if constraints_passed else 0.5,
                    "weight": 0.20,
                    "weighted_contribution": c_comp,
                },
            ]
        else:
            # Caso venha do protótipo legado (score_contributions)
            contribuicoes_map = cand_dict.get("score_contributions") or {}
            soma_contrib = float(sum(contribuicoes_map.values())) if contribuicoes_map else 0.0
            for fname, fcontrib in contribuicoes_map.items():
                factors_list.append(
                    {
                        "factor_name": str(fname),
                        "raw_value": float(fcontrib),
                        "normalized_value": max(0.0, min(1.0, float(fcontrib))),
                        "weight": 0.25,
                        "weighted_contribution": float(fcontrib),
                    }
                )

        erro_matematico = abs(soma_contrib - score_total)
        math_integrity_passed = bool(contribuicoes_map) and (erro_matematico < self.TOLERANCIA_MATEMATICA)

        # Validação adicional de intervalo [0, 1]
        all_in_range = (0.0 <= score_total <= 1.000001) and all(
            0.0 <= f["normalized_value"] <= 1.000001 for f in factors_list
        )

        if not math_integrity_passed:
            motivos_rejeicao.append(
                f"Inconsistência Matemática: |soma({soma_contrib:.6f}) - score_total({score_total:.6f})| = {erro_matematico:.6f} >= 1e-5."
            )
            diagnosticos.append(
                f"Candidato '{nome}' ({cand_id}): Inconsistência Matemática: soma ({soma_contrib:.6f}) != score_total ({score_total:.6f})."
            )

        if not all_in_range:
            motivos_rejeicao.append("Fatores ou score_total fora do intervalo [0, 1].")
            diagnosticos.append(f"Candidato '{nome}' ({cand_id}): valores fora da faixa normalizada [0, 1].")

        # -----------------------------------------------------------------
        # 4. Consolidação do Resultado
        # -----------------------------------------------------------------
        approved = rnf01_passed and constraints_passed and math_integrity_passed and all_in_range

        grounding_notes = [
            f"Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/{parsed_osm_type}/{parsed_osm_id or 0}).",
            f"Acessibilidade: wheelchair={cand_wheelchair or 'não especificado'}.",
            f"Nível de ruído: {cand_noise or 'não informado'}.",
        ]
        if cand_hours:
            grounding_notes.append(f"Horário de funcionamento: {cand_hours}.")

        matched_tags = merged_candidato.get("tags") or merged_candidato.get("matched_tags") or []
        if not isinstance(matched_tags, list):
            matched_tags = [str(matched_tags)]

        evidence_payload = {
            "evidence_id": f"EV-{uuid.uuid4().hex[:8].upper()}",
            "query_id": str(req_id),
            "place_id": str(cand_id),
            "place_name": str(nome),
            "osm_reference": {
                "osm_id": parsed_osm_id or 0,
                "osm_type": parsed_osm_type,
                "osm_link": f"https://www.openstreetmap.org/{parsed_osm_type}/{parsed_osm_id or 0}",
            },
            "matched_tags": matched_tags,
            "factors": factors_list,
            "total_score": round(score_total, 6),
            "integrity_test": {
                "sum_equals_total": bool(math_integrity_passed),
                "all_factors_in_range_0_1": bool(all_in_range),
                "passed": bool(math_integrity_passed and all_in_range),
            },
            "grounding_notes": grounding_notes,
        }

        retry_instruction = " | ".join(diagnosticos) if diagnosticos else None

        return {
            "evidence_id": evidence_payload["evidence_id"],
            "request_id": str(req_id),
            "place_id": str(cand_id),
            "candidate_name": str(nome),
            "osm_id": f"{parsed_osm_type}/{parsed_osm_id}" if parsed_osm_id else None,
            "rnf01_passed": bool(rnf01_passed),
            "constraints_passed": bool(constraints_passed),
            "math_integrity_passed": bool(math_integrity_passed and all_in_range),
            "approved": bool(approved),
            "score_total": score_total,
            "soma_contribuicoes": soma_contrib,
            "erro_matematico": erro_matematico,
            "score_contributions": contribuicoes_map,
            "rejection_reasons": motivos_rejeicao,
            "diagnostics": diagnosticos,
            "hard_filters": hard_filters,
            "retry_instruction": retry_instruction,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "evidence_payload": evidence_payload,
        }

    def auditar_lote(
        self,
        structured_request: Union[Dict[str, Any], StructuredRequest],
        candidatos: List[Union[Dict[str, Any], SearchItem]],
    ) -> Dict[str, Any]:
        """Audita uma lista de candidatos e consolida instruções de correção (nao persiste)."""
        aprovados = []
        reprovados = []
        instrucoes_para_retrieval = []
        hard_filters_agregados: Dict[str, str] = {}
        todos_diagnosticos: List[str] = []

        req_id = (
            structured_request.request_id
            if isinstance(structured_request, StructuredRequest)
            else structured_request.get("request_id", "REQ-UNKNOWN")
        )

        for cand in candidatos:
            auditoria = self.auditar_candidato(structured_request, cand)
            if auditoria["approved"]:
                aprovados.append(auditoria)
            else:
                reprovados.append(auditoria)
                if auditoria["retry_instruction"]:
                    instrucoes_para_retrieval.append(
                        {
                            "candidato": auditoria["candidate_name"],
                            "instrucao": auditoria["retry_instruction"],
                        }
                    )
                hard_filters_agregados.update(auditoria["hard_filters"])
                todos_diagnosticos.extend(auditoria["diagnostics"])

        return {
            "request_id": req_id,
            "total_auditados": len(candidatos),
            "aprovados": aprovados,
            "reprovados": reprovados,
            "requer_nova_busca": len(reprovados) > 0,
            "hard_filters": hard_filters_agregados,
            "diagnostics": todos_diagnosticos,
            "instrucoes_correcao_retrieval": instrucoes_para_retrieval,
        }

    def auditar_search_response(
        self,
        structured_request: StructuredRequest,
        search_response: SearchResponse,
    ) -> Tuple[ValidationFeedback, List[EvidenceRecord]]:
        """Audita um SearchResponse oficial (Contrato 3) gerando ValidationFeedback e EvidenceRecords (Contrato 4)."""
        if not search_response.items or search_response.results_count == 0:
            fb = ValidationFeedback(
                approved=False,
                rejected_place_ids=[],
                hard_filters={},
                diagnostics=["Nenhum candidato retornado pelo Retrieval_Agent."],
            )
            return fb, []

        lote = self.auditar_lote(structured_request, search_response.items)
        aprovados = lote["aprovados"]
        reprovados = lote["reprovados"]

        # Rastro de auditoria, numa transacao so. Reprovados sempre; aprovados so se o top
        # inteiro foi aprovado (so entao viram EvidenceRecord entregue). Falha de gravacao sobe.
        if self.store is not None:
            gravar = reprovados + (aprovados if not reprovados else [])
            self.store.salvar(gravar, search_response.consulta_id)

        # Se houver qualquer candidato reprovado no lote avaliado:
        if reprovados:
            rejected_ids = [r["place_id"] for r in reprovados]
            fb = ValidationFeedback(
                approved=False,
                rejected_place_ids=rejected_ids,
                hard_filters=lote["hard_filters"],
                diagnostics=lote["diagnostics"],
            )
            return fb, []

        # Todos foram aprovados com sucesso!
        evidence_records: List[EvidenceRecord] = []
        for ap in aprovados:
            record = EvidenceRecord.model_validate(ap["evidence_payload"])
            evidence_records.append(record)

        fb = ValidationFeedback(
            approved=True,
            rejected_place_ids=[],
            hard_filters={},
            diagnostics=[],
        )
        return fb, evidence_records

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Ponto de entrada para o orquestrador LangGraph (AgentState -> dict parcial)."""
        req = state.get("structured_request")
        resp = state.get("search_response")

        if req is None or resp is None:
            fb = ValidationFeedback(
                approved=False,
                rejected_place_ids=[],
                hard_filters={},
                diagnostics=["Estado incompleto: structured_request ou search_response ausente."],
            )
            return {
                "validation_feedback": fb,
                "note": "Auditoria falhou: dados ausentes no estado.",
            }

        fb, evidence_records = self.auditar_search_response(req, resp)

        if fb.approved:
            return {
                "validation_feedback": fb,
                "evidence_records": evidence_records,
                "note": f"Top-{len(evidence_records)} aprovado pela auditoria (RNF01, restrições e integridade matemática 100% conformes).",
            }

        return {
            "validation_feedback": fb,
            "note": f"Auditoria reprovou {len(fb.rejected_place_ids)} candidato(s). Diagnóstico: {'; '.join(fb.diagnostics[:2])}",
        }


_default_agent: Optional[ValidationAgent] = None


def validation_agent(state: AgentState) -> Dict[str, Any]:
    """Função de agente injetável diretamente no build_graph (grava em PostgreSQL)."""
    global _default_agent
    if _default_agent is None:
        _default_agent = ValidationAgent(store=PostgresEvidenceStore())
    return _default_agent(state)
