# Orquestrador Bubbles

Grafo LangGraph com quatro agentes: `NLU → Retrieval → Validation → Communication`.
Retrieval e Validation são reais e usam o PostgreSQL (PostGIS + pgvector, OSM do DF). NLU e
Communication ainda são stubs (`stubs.py`).

```
NLU --(intent_valid=false)------------------------------> Communication
 └─(ok)─> Retrieval ──> Validation ──(aprovado)──────────> Communication
             ▲              │
             └──(reprovado, até 2 reconsultas com hard_filters)
```

## Rodar

```bash
cd data-pipeline && ./setup_db.sh && cd ..      # sobe e popula o banco (idempotente)
pip install -r orchestrator/requirements.txt
python scripts/run_orquestrador.py --regiao "Asa Sul" --categoria cafe --raio-km 2 --sem-modelo
pytest orchestrator                              # testes de banco sao pulados sem Postgres
```

## O que cada agente faz

| Agente | Arquivo | Entrada → saída |
|---|---|---|
| Retrieval | `retrieval_agent.py` | `structured_request` (+ `validation_feedback`) → `search_response` (Contrato 3), via `busca.buscar` |
| Validation | `validation_agent.py` | `search_response` → `validation_feedback` + `evidence_records` (Contrato 4) |

- **Região:** `target_region` vira coordenada pela tabela `regioes` (OSM). Região desconhecida não
  busca: preenche `clarification_needed` e o Communication pergunta ao usuário.
- **Acessibilidade:** `wheelchair_required` só aceita `wheelchair=yes` explícito no OSM (ADR-0002).
- **RNF01:** o Validation audita só o que o item traz do OSM (`osm_id`, `osm_tags`,
  `is_public_verified`). Sem isso, reprova.
- **Rastro:** `evidencias_busca` (uma linha por busca) e `evidencias_auditoria` (uma por candidato
  auditado), ligadas por `consulta_id`. Falha de gravação vira abstenção segura.
- **RNF02:** `raw_query` é zerado depois do NLU; nada de texto livre chega ao Retrieval nem ao banco.

## Limites conhecidos

- A busca não filtra por horário nem por `elder_friendly`; o Validation reprova e a reconsulta
  exclui o local rejeitado. O estado guarda só o último feedback.
- Só ~4% dos lugares do DF têm `wheelchair=yes`; nenhum tem `noise_level` no OSM.
- `is_public_verified` é derivado da presença de `osm_id`/`osm_type` (todo `places` vem do OSM).
