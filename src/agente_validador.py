import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Any


class ValidationAgent:
    """
    Issue #04 — Implementação do Validation_Agent (Auditoria RNF01 e Consistência)
    """
    TOLERANCIA_MATEMATICA = 1e-5

    def __init__(self, db_path: str = "banco_inicial.db"):
        self.db_path = db_path
        self._inicializar_tabela_evidencias()

    def _inicializar_tabela_evidencias(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS evidencias_busca (
                evidence_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                osm_id TEXT,
                candidate_name TEXT,
                rnf01_passed INTEGER NOT NULL,
                constraints_passed INTEGER NOT NULL,
                math_integrity_passed INTEGER NOT NULL,
                approved INTEGER NOT NULL,
                score_total REAL,
                soma_contribuicoes REAL,
                erro_matematico REAL,
                score_contributions_json TEXT,
                rejection_reasons_json TEXT,
                retry_instruction TEXT,
                timestamp_utc TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    def auditar_candidato(self, structured_request: Dict[str, Any], candidato: Dict[str, Any]) -> Dict[str, Any]:
        req_id = structured_request.get("request_id", "REQ-UNKNOWN")
        nome = candidato.get("nome", "Desconhecido")
        osm_id = candidato.get("osm_id")
        is_public_verified = candidato.get("is_public_verified")

        motivos_rejeicao: List[str] = []
        instrucoes_correcao: List[str] = []

        # -----------------------------------------------------------------
        # 1. Auditoria RNF01 (Zero Alucinação: osm_id válido + is_public_verified)
        # -----------------------------------------------------------------
        osm_valido = isinstance(osm_id, str) and len(osm_id.strip()) > 0 and any(char.isdigit() for char in osm_id)
        publico_verificado = (is_public_verified is True)
        rnf01_passed = osm_valido and publico_verificado

        if not osm_valido:
            motivos_rejeicao.append("RNF01 Violado: candidato sem osm_id válido.")
            instrucoes_correcao.append("RETRIEVAL_FIX: Filtrar resultados mantendo apenas registros com osm_id NOT NULL.")
        if not publico_verificado:
            motivos_rejeicao.append("RNF01 Violado: is_public_verified != true (local não verificado como público).")
            instrucoes_correcao.append("RETRIEVAL_FIX: Adicionar cláusula WHERE is_public_verified = TRUE na query.")

        # -----------------------------------------------------------------
        # 2. Auditoria de Restrições Críticas (Acessibilidade e Ruído/Horário)
        # -----------------------------------------------------------------
        req_acess = structured_request.get("accessibility_requirements", {})
        wheelchair_req = req_acess.get("wheelchair_required", False)
        elder_req = req_acess.get("elder_friendly", False)

        cand_wheelchair = str(candidato.get("wheelchair", "")).lower()
        cand_elder = candidato.get("elder_friendly", True)

        constraints_passed = True

        if wheelchair_req and cand_wheelchair in ["no", "false", "none", ""]:
            constraints_passed = False
            motivos_rejeicao.append(
                f"Violação de Acessibilidade: requisição exige wheelchair_required=true, mas o local possui wheelchair='{candidato.get('wheelchair')}'."
            )
            instrucoes_correcao.append(
                "RETRIEVAL_FIX: Excluir candidatos com wheelchair='no' e restringir busca para wheelchair IN ('yes', 'designated')."
            )

        if elder_req and cand_elder is False:
            constraints_passed = False
            motivos_rejeicao.append(
                "Violação de Acessibilidade: requisição exige elder_friendly=true, mas o local é inadequado para idosos."
            )
            instrucoes_correcao.append(
                "RETRIEVAL_FIX: Priorizar locais planos, com assentos de descanso e elder_friendly=true."
            )

        # -----------------------------------------------------------------
        # 3. Integridade Matemática: |soma(contribuições) - score_total| < 1e-5
        # -----------------------------------------------------------------
        contribuicoes: Dict[str, float] = candidato.get("score_contributions", {})
        score_total = float(candidato.get("score_total", 0.0))
        soma_contrib = float(sum(contribuicoes.values())) if contribuicoes else 0.0
        erro_matematico = abs(soma_contrib - score_total)

        math_integrity_passed = bool(contribuicoes) and (erro_matematico < self.TOLERANCIA_MATEMATICA)

        if not math_integrity_passed:
            motivos_rejeicao.append(
                f"Inconsistência Matemática: |soma({soma_contrib:.6f}) - score_total({score_total:.6f})| = {erro_matematico:.6f} >= 1e-5."
            )
            instrucoes_correcao.append(
                "RETRIEVAL_FIX: Recalcular score_total garantindo soma exata dos pesos parciais antes do retorno."
            )

        # -----------------------------------------------------------------
        # 4. Consolidação e Persistência em evidencias_busca
        # -----------------------------------------------------------------
        approved = rnf01_passed and constraints_passed and math_integrity_passed
        retry_instruction = " | ".join(instrucoes_correcao) if instrucoes_correcao else None

        evidence_record = {
            "evidence_id": f"EVID-{uuid.uuid4().hex[:8].upper()}",
            "request_id": req_id,
            "osm_id": osm_id,
            "candidate_name": nome,
            "rnf01_passed": rnf01_passed,
            "constraints_passed": constraints_passed,
            "math_integrity_passed": math_integrity_passed,
            "approved": approved,
            "score_total": score_total,
            "soma_contribuicoes": soma_contrib,
            "erro_matematico": erro_matematico,
            "score_contributions": contribuicoes,
            "rejection_reasons": motivos_rejeicao,
            "retry_instruction": retry_instruction,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }

        self._persistir_evidencia(evidence_record)
        return evidence_record

    def _persistir_evidencia(self, record: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO evidencias_busca (
                evidence_id, request_id, osm_id, candidate_name,
                rnf01_passed, constraints_passed, math_integrity_passed, approved,
                score_total, soma_contribuicoes, erro_matematico,
                score_contributions_json, rejection_reasons_json, retry_instruction, timestamp_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["evidence_id"],
            record["request_id"],
            record["osm_id"],
            record["candidate_name"],
            int(record["rnf01_passed"]),
            int(record["constraints_passed"]),
            int(record["math_integrity_passed"]),
            int(record["approved"]),
            record["score_total"],
            record["soma_contribuicoes"],
            record["erro_matematico"],
            json.dumps(record["score_contributions"], ensure_ascii=False),
            json.dumps(record["rejection_reasons"], ensure_ascii=False),
            record["retry_instruction"],
            record["timestamp_utc"]
        ))
        conn.commit()
        conn.close()

    def auditar_lote(self, structured_request: Dict[str, Any], candidatos: List[Dict[str, Any]]) -> Dict[str, Any]:
        aprovados = []
        reprovados = []
        instrucoes_para_retrieval = []

        for cand in candidatos:
            evidencia = self.auditar_candidato(structured_request, cand)
            if evidencia["approved"]:
                aprovados.append(evidencia)
            else:
                reprovados.append(evidencia)
                if evidencia["retry_instruction"]:
                    instrucoes_para_retrieval.append({
                        "candidato": cand.get("nome"),
                        "instrucao": evidencia["retry_instruction"]
                    })

        return {
            "request_id": structured_request.get("request_id"),
            "total_auditados": len(candidatos),
            "aprovados": aprovados,
            "reprovados": reprovados,
            "requer_nova_busca": len(aprovados) == 0 and len(instrucoes_para_retrieval) > 0,
            "instrucoes_correcao_retrieval": instrucoes_para_retrieval
        }