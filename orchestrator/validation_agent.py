"""COMPATIBILIDADE: o Validation deixou de ser "agente" (nao usa LLM) e virou ferramenta.

Use `orchestrator.validation_tool.EvidenceValidator`. Este modulo existe so para nao quebrar quem
importava os nomes antigos (ex.: src/agente_validador.py e os prototipos legados em src/).
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, Optional

from .evidence_store import PostgresEvidenceStore
from .state import AgentState
from .validation_tool import EvidenceValidator


class ValidationAgent(EvidenceValidator):
    """Nome antigo de `EvidenceValidator`. Aceita `db_path` so para nao quebrar chamadas legadas."""

    def __init__(self, db_path: Optional[str] = None, **kwargs: Any):
        if db_path is not None:
            warnings.warn(
                "ValidationAgent(db_path=...) foi removido: a auditoria vai para o PostgreSQL via EvidenceStore; "
                "o argumento e ignorado. Use EvidenceValidator(store=PostgresEvidenceStore()).",
                DeprecationWarning,
                stacklevel=2,
            )
        super().__init__(**kwargs)


_default_agent: Optional[ValidationAgent] = None


def validation_agent(state: AgentState) -> Dict[str, Any]:
    """Funcao de agente antiga (grava em PostgreSQL). Preferir o gate do Retrieval (Fase B)."""
    warnings.warn("validation_agent() esta obsoleto: o Validation agora e uma ferramenta do Retrieval.", DeprecationWarning, stacklevel=2)
    global _default_agent
    if _default_agent is None:
        _default_agent = ValidationAgent(store=PostgresEvidenceStore())
    return _default_agent(state)


__all__ = ["ValidationAgent", "validation_agent", "EvidenceValidator"]
