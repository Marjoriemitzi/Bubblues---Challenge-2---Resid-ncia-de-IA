import sys
from pathlib import Path

# Garante que o diretório raiz do projeto esteja acessível no PYTHONPATH
_raiz = Path(__file__).resolve().parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

from orchestrator.validation_agent import ValidationAgent, validation_agent

__all__ = ["ValidationAgent", "validation_agent"]
