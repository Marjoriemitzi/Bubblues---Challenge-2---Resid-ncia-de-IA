# Orquestrador Bubbles

> **Documentação:** [arquitetura e responsabilidades dos agentes](../docs/arquitetura_agentes.md) · [demonstração de um fluxo completo](../docs/demo_fluxo_completo.md) · [avaliação do agente LLM](../docs/avaliacao/fase_f_resultados.md)

Grafo LangGraph: `NLU → Retrieval → Communication`. **"Agente" é só o que usa LLM** (NLU e Communication,
e o Retrieval quando virar agente). O Validation não usa LLM: é uma **ferramenta** do Retrieval.

```
NLU --(intent_valid=false | clarification_needed)--------------> Communication
 └─(ok)─> Retrieval ───────────────────────────────────────────> Communication
            │
            └─ por dentro: regiao → buscar_lugares → GATE (EvidenceValidator) → aprovado? entrega
                                          ▲                          │
                                          └── reconsulta com os filtros do feedback (até MAX_RETRIES)
```

## Rodar

```bash
cd data-pipeline && ./setup_db.sh && cd ..      # sobe e popula o banco (idempotente)
pip install -r orchestrator/requirements.txt
python scripts/run_orquestrador.py --regiao "Asa Sul" --categoria cafe --raio-km 2 --sem-modelo
pytest orchestrator                              # testes de banco são pulados sem Postgres
```

## Componentes

| Componente | Arquivo | Usa LLM? | O que faz |
|---|---|---|---|
| NLU | `nlu_agent.py` (+ `llm_client.py`) | sim (DeepSeek) | texto livre → `structured_request` (Contrato 2), validado e restrito às categorias da base |
| Retrieval (hoje) | `retrieval_pipeline.py` | não | busca determinística + gate + reconsulta; devolve `search_response`, `evidence_records` (Contrato 4), `validation_feedback`, `retry_count` |
| Tools de busca | `retrieval_tools.py` | não | `resolver_regiao`, `listar_categorias`, `buscar_lugares`, `validar_candidatos`; filtros obrigatórios dentro da tool |
| Gate | `retrieval_gate.py` | não | auditoria **obrigatória** da seleção final; grava a auditoria; recusa lugar que não veio da busca |
| Cliente LLM | `llm_client.py` (+ `llm_fake.py` para testes) | sim | DeepSeek: retry, tool calling, thinking (`reasoning_content`), `strict`, contagem de tokens e prazo |
| Validação | `validation_tool.py` (`EvidenceValidator`) | não | RNF01, restrições (acessibilidade, ruído, horário) e integridade matemática do score |
| Communication | `stubs.py` (stub) | — | em desenvolvimento por outra pessoa |

`validation_agent.py` é só um shim de compatibilidade (nomes antigos `ValidationAgent` e `validation_agent`).

- **Região:** `target_region` vira coordenada pela tabela `regioes` (OSM). Região desconhecida não busca:
  preenche `clarification_needed` e o Communication pergunta ao usuário.
- **Acessibilidade:** `wheelchair_required` só aceita `wheelchair=yes` explícito no OSM (ADR-0002).
- **RNF01:** o validador audita só o que o item traz do OSM (`osm_id`, `osm_tags`, `is_public_verified`).
- **Rastro:** `evidencias_busca` (uma linha por busca) e `evidencias_auditoria` (uma por candidato auditado),
  ligadas por `consulta_id`. **Fail-closed:** falha ao gravar a auditoria vira abstenção.
- **RNF02:** `raw_query` é zerado depois do NLU; nada de texto livre chega ao Retrieval nem ao banco.
- `retry_count` = reconsultas realizadas (0 = aprovado na primeira busca).

## Configuração e tracing

- **`RETRIEVAL_MODE=deterministic|llm`** (padrão `deterministic`): `criar_retrieval()` / `montar_grafo()` em `retrieval_factory.py`.
  `llm` usa o agente DeepSeek **com fallback** para o pipeline; a avaliação passa `fallback=None` para medir o agente cru.
- **Tracing no Langfuse** (`observabilidade.py`): liga sozinho se houver `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY`; sob pytest fica desligado.
  Árvore por pedido: `pedido` → `no.<nó>` → `tool.*`, `gate.auditar` e `llm.chat` (generation, com tokens).
  **RNF02:** não grava o conteúdo das mensagens (o NLU manda o texto livre do usuário ao LLM), só formato, tokens e nomes de tools;
  `LANGFUSE_LOG_CONTENT=1` liga o conteúdo, só para depuração. Falha de tracing nunca derruba o sistema.

## LLM (DeepSeek)

Variáveis em `.env.example`. Padrão: `deepseek-flash`, thinking desligado. `python scripts/diagnostico_llm.py` roda um loop real de tool use
e compara configurações; resultados e recomendação em `docs/diagnostico_llm_deepseek.md`.

## Avaliação

`scripts/avaliacao/rodar_experimento.py` roda o grafo sobre o dataset `bubbles-retrieval-osm-v1` no Langfuse
(P@3, nDCG@3, restrições entregues, latência...). Baseline em `docs/avaliacao/baseline_retrieval_deterministico.md`.

## Limites conhecidos

- A busca não filtra por horário nem por `elder_friendly`; o gate reprova e a reconsulta exclui o lugar rejeitado.
- Só ~4% dos lugares do DF têm `wheelchair=yes`; nenhum tem `noise_level` no OSM.
- `is_public_verified` é derivado da presença de `osm_id`/`osm_type` (todo `places` vem do OSM).
