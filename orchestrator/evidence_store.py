"""Persistencia da auditoria do Validation_Agent (Contrato 4) no PostgreSQL.

O validador conhece so a interface `salvar(auditorias, consulta_id)`. Em producao ela grava em
`evidencias_auditoria` (data-pipeline/db/schema.sql); nos testes entra um store em memoria.

Falhas de gravacao SOBEM como excecao (fail-closed): sem rastro de auditoria o resultado nao pode
ser entregue, e o orquestrador converte a falha em abstencao segura.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

_PIPELINE_DIR = Path(__file__).resolve().parent.parent / "data-pipeline"
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

COLUNAS = (
    "evidence_id", "query_id", "consulta_id", "place_id", "place_name", "osm_id", "osm_type",
    "aprovado", "rnf01_passed", "constraints_passed", "math_integrity_passed", "score_total",
    "motivos_rejeicao", "evidence", "criada_em",
)


class EvidenceStore(Protocol):
    def salvar(self, auditorias: List[Dict[str, Any]], consulta_id: Optional[str] = None) -> None: ...


class MemoryEvidenceStore:
    """Guarda em memoria (testes e demos)."""

    def __init__(self):
        self.linhas: List[Dict[str, Any]] = []

    def salvar(self, auditorias, consulta_id=None):
        self.linhas.extend({**a, "consulta_id": consulta_id} for a in auditorias)


def _linha(auditoria: Dict[str, Any], consulta_id: Optional[str]) -> Dict[str, Any]:
    ref = (auditoria.get("evidence_payload") or {}).get("osm_reference") or {}
    osm_id = ref.get("osm_id") or None  # 0 = candidato sem osm_id valido
    return {
        "evidence_id": auditoria["evidence_id"],
        "query_id": auditoria["request_id"],
        "consulta_id": consulta_id if consulta_id and _UUID.match(consulta_id) else None,
        "place_id": auditoria["place_id"],
        "place_name": auditoria["candidate_name"],
        "osm_id": osm_id,
        "osm_type": ref.get("osm_type") if osm_id else None,
        "aprovado": bool(auditoria["approved"]),
        "rnf01_passed": bool(auditoria["rnf01_passed"]),
        "constraints_passed": bool(auditoria["constraints_passed"]),
        "math_integrity_passed": bool(auditoria["math_integrity_passed"]),
        "score_total": auditoria["score_total"],
        "motivos_rejeicao": auditoria["rejection_reasons"],
        "evidence": auditoria["evidence_payload"],
        "criada_em": auditoria["timestamp_utc"],
    }


class PostgresEvidenceStore:
    """Grava em `evidencias_auditoria`, todas as linhas de uma auditoria numa so transacao."""

    def __init__(self, conexao_factory: Optional[Callable[[], Any]] = None):
        self._conexao_factory = conexao_factory

    def _factory(self):
        if self._conexao_factory is None:
            if str(_PIPELINE_DIR) not in sys.path:
                sys.path.insert(0, str(_PIPELINE_DIR))
            import busca  # noqa: PLC0415

            self._conexao_factory = busca.conectar
        return self._conexao_factory

    def salvar(self, auditorias, consulta_id=None):
        if not auditorias:
            return
        from psycopg.types.json import Jsonb  # noqa: PLC0415

        linhas = []
        for a in auditorias:
            linha = _linha(a, consulta_id)
            linha["motivos_rejeicao"] = Jsonb(linha["motivos_rejeicao"])
            linha["evidence"] = Jsonb(linha["evidence"])
            linhas.append(linha)

        colunas = ", ".join(COLUNAS)
        valores = ", ".join(f"%({c})s" for c in COLUNAS)
        atualiza = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUNAS if c != "evidence_id")
        sql = (
            f"INSERT INTO evidencias_auditoria ({colunas}) VALUES ({valores}) "
            f"ON CONFLICT (evidence_id) DO UPDATE SET {atualiza}"
        )
        with self._factory()() as conexao, conexao.transaction(), conexao.cursor() as cursor:
            cursor.executemany(sql, linhas)
