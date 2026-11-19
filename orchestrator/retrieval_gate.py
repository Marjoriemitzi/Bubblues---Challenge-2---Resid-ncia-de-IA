"""Gate do Retrieval: a auditoria que NAO e opcional.

Nada sai do Retrieval sem passar por aqui. O gate roda o EvidenceValidator na selecao final de uma
busca (do `RunLog`), grava a auditoria (via o store do validador) e devolve o feedback e as evidencias
(Contrato 4). O LLM pode ate chamar `validar_candidatos` antes, mas isso e so autocorrecao: se ele nao
chamar, o gate audita do mesmo jeito.

A selecao final so pode conter lugares da busca registrada; qualquer outro `place_id` e recusado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from .contracts import EvidenceRecord, SearchResponse, StructuredRequest, ValidationFeedback
from .retrieval_tools import BuscaRegistrada
from .validation_tool import EvidenceValidator


class SelecaoInvalida(ValueError):
    """A selecao final cita lugares que nao vieram da busca (ou esta vazia)."""


@dataclass
class ResultadoGate:
    feedback: ValidationFeedback
    evidence_records: List[EvidenceRecord]
    search_response: SearchResponse  # a selecao auditada (ranks renumerados)

    @property
    def aprovado(self) -> bool:
        return self.feedback.approved


def _selecionar(busca: BuscaRegistrada, place_ids: Optional[Sequence[str]]) -> dict:
    resposta = dict(busca.search_response)
    resposta["consulta_id"] = busca.consulta_id
    if place_ids is None:
        return resposta
    por_id = {i["place_id"]: i for i in busca.search_response["items"]}
    ids = [str(p) for p in place_ids]
    if not ids:
        raise SelecaoInvalida("selecao vazia")
    desconhecidos = [p for p in ids if p not in por_id]
    if desconhecidos:
        raise SelecaoInvalida(f"lugares fora da busca {busca.busca_id}: {desconhecidos}")
    if len(set(ids)) != len(ids):
        raise SelecaoInvalida("selecao com lugares repetidos")
    itens = [{**por_id[p], "rank": r} for r, p in enumerate(ids, start=1)]
    resposta["items"] = itens
    resposta["results_count"] = len(itens)
    return resposta


class RetrievalGate:
    def __init__(self, validator: EvidenceValidator):
        self.validator = validator

    def auditar(
        self,
        req: StructuredRequest,
        busca: BuscaRegistrada,
        place_ids: Optional[Sequence[str]] = None,
    ) -> ResultadoGate:
        """Audita a busca inteira, ou so a selecao `place_ids` (subconjunto e ordem escolhidos)."""
        resposta = SearchResponse.model_validate(_selecionar(busca, place_ids))
        if not resposta.items:
            fb = ValidationFeedback(approved=False, diagnostics=["Nenhum candidato retornado pela busca."])
            return ResultadoGate(fb, [], resposta)
        fb, records = self.validator.auditar_search_response(req, resposta)
        return ResultadoGate(fb, records, resposta)
