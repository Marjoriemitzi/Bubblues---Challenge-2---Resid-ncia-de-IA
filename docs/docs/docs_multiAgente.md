# Protótipo de Sistema Multiagentes — Projeto Bubbles (RES IA ELD UnB)

**Autora:** Marjorie Mitzi Cavalcante Rodrigues  
**Branch:** `feat/pipeline-agente`  
**Repositório:** `https://github.com/Marjoriemitzi/Bubblues---Challenge-2---Resid-ncia-de-IA`

---

## 1. Diagrama da Arquitetura dos Agentes

O sistema multiagentes do **Bubbles** opera em uma topologia sequencial com portões de qualidade (*guardrails* de entrada e auditoria pós-recuperação):

```text
[ Solicitação do Usuário ]
            │
            ▼
┌──────────────────────────────────────────────────────────┐
│ 1. Intake_NLU_Agent (Agente de Entrada e Guardrails)     │
│    • Extrai entidades (Contrato 2: structured_request)   │
│    • Avalia out_of_scope e impossible_criteria           │
└───────────┬──────────────────────────────────┬───────────┘
            │ intent_valid = true              │ intent_valid = false
            ▼                                  ▼
┌───────────────────────────────────┐   [ Bloqueio Imediato / Abstenção ]
│ 2. Research_Agent (Busca RAG)     │
│    • Vetoriza search_vector_focus │
│    • Busca em banco_inicial.db    │
│    • Calcula score_contributions  │
└───────────┬───────────────────────┘
            │ Lista de Candidatos + Pesos
            ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Validation_Agent (Auditoria RNF01 e Consistência)     │
│    • Verifica osm_id válido e is_public_verified == true │
│    • Audita restrições críticas (wheelchair / elder)     │
│    • Valida |soma(contribuições) - score_total| < 1e-5   │
│    • Persiste auditoria na tabela evidencias_busca       │
└───────────┬──────────────────────────────────┬───────────┘
            │ Candidatos Aprovados             │ Candidatos Reprovados
            ▼                                  ▼
┌───────────────────────────────────┐   [ Instrução RETRIEVAL_FIX ]
│ 4. Communication_Agent            │
│    • Adapta linguagem à persona   │
│    • Apresenta locais + Evidência │
└───────────┬───────────────────────┘
            │
            ▼
[ Resposta Final Auditada ao Usuário ]
```

---

## 2. Descrição das Responsabilidades de Cada Agente

1. **`Intake_NLU_Agent` (`src/agente_entrada_nlu.py`) — Interpretação e Bloqueio de Entrada:**
   * **Papel:** Guardião de escopo e extrator de requisitos (Contrato 2).
   * **Responsabilidades:** Converter o pedido em linguagem natural para o schema JSON estrito `StructuredRequestContrato2` (validado via Pydantic com mecanismo de *retry*), preencher requisitos de acessibilidade (`wheelchair_required`, `elder_friendly`), sintetizar o `search_vector_focus` e barrar solicitações fora de escopo (ex.: fretes, serviços comerciais, encontros privados) ou com critérios impossíveis (ex.: cafeteria silenciosa às 03h30).

2. **`Research_Agent` (`src/6_multiagente_prototipo.py`) — Recuperação de Informações (RAG):**
   * **Papel:** Especialista em busca semântica vetorial e pontuação multicritério.
   * **Responsabilidades:** Codificar o `search_vector_focus` em um vetor denso de 768 dimensões (`paraphrase-multilingual-mpnet-base-v2`), consultar o banco vetorial (`banco_inicial.db`), cruzar com metadados do OpenStreetMap e decompor a nota de cada candidato em `score_contributions` (`semantic_similarity`, `noise_compatibility`, `accessibility_match`).

3. **`Validation_Agent` (`src/agente_validador.py`) — Validação e Identificação de Inconsistências (Issue #04):**
   * **Papel:** Auditor de qualidade, conformidade RNF01 (zero alucinação) e integridade matemática.
   * **Responsabilidades:** Inspecionar cada candidato retornado pelo `Research_Agent`, reprovando locais sem `osm_id` válido ou com `is_public_verified != true`, barrando violações de acessibilidade (ex.: `wheelchair_required=true` vs. local com `wheelchair='no'`), verificando se $\vert{} \sum \text{contribuições} - \text{score\_total} \vert{} < 10^{-5}$, emitindo instruções `RETRIEVAL_FIX` e gravando o `evidence_record` na tabela `evidencias_busca`.

4. **`Communication_Agent` (`src/6_multiagente_prototipo.py`) — Adaptação da Comunicação ao Público-Alvo:**
   * **Papel:** Redator empático ancorado exclusivamente em evidências aprovadas.
   * **Responsabilidades:** Receber apenas os candidatos aprovados pelo `Validation_Agent`, adaptar o tom da mensagem às necessidades da persona (como conforto e acessibilidade para idosos/cadeirantes) e apresentar as recomendações acompanhadas do `osm_id`, `score_total` auditado e código de rastreabilidade (`evidence_id`).

---

## 3. Fluxo de Interação e Colaboração entre os Agentes

1. **Etapa 1 (Usuário $\rightarrow$ `Intake_NLU_Agent`):** O usuário envia sua solicitação. Se `intent_valid` for `false`, o fluxo é encerrado imediatamente com a justificativa em `out_of_scope_reason` ou `impossible_criteria_reason`.
2. **Etapa 2 (`Intake_NLU_Agent` $\rightarrow$ `Research_Agent`):** Caso válido, o JSON do Contrato 2 é repassado ao `Research_Agent`, que usa o campo `search_vector_focus` e a tolerância de ruído para ranquear os candidatos do banco.
3. **Etapa 3 (`Research_Agent` $\rightarrow$ `Validation_Agent`):** A lista de candidatos e o Contrato 2 são entregues ao `Validation_Agent`, que audita candidato por candidato, persiste os resultados em `evidencias_busca` e separa os registros em `aprovados` e `reprovados` (anexando instruções de correção `RETRIEVAL_FIX`).
4. **Etapa 4 (`Validation_Agent` $\rightarrow$ `Communication_Agent` $\rightarrow$ Usuário):** Os candidatos aprovados seguem para o `Communication_Agent`, que formata a resposta final segura e rastreável para o usuário.

---

## 4. Demonstração de Execução (Fluxo Completo)

Comando de execução:

```bash
python src/6_multiagente_prototipo.py
```

Saída real obtida:

```text
Inicializando Sistema Multiagentes (4 Agentes) — Projeto Bubbles

===========================================================================
 ENTRADA DO USUÁRIO: "Sou a Dona Helena, uso cadeira de rodas e quero um café calmo e silencioso na Asa Norte para ler e conversar à tarde."
===========================================================================
 [1. Intake_NLU_Agent] Extraindo Contrato 2 e verificando guardrails...
 [2. Research_Agent] Vetorizando foco semântico: 'encontro social para conversa e café. Ambiente calmo, acolhedor e silencioso. Ruído: Baixo. Acessibilidade: cadeirante=True, idosos=True.'
   -> 3 candidatos recuperados do banco vetorial.
 [3. Validation_Agent] Auditando RNF01, acessibilidade e soma matemática...
   -> Aprovados: 2 | Reprovados: 1
   -> [REPROVADO] Ernesto Cafés Especiais Asa Sul: Violação de Acessibilidade: requisição exige wheelchair_required=true, mas o local possui wheelchair='no'.
 [4. Communication_Agent] Adaptando resposta ao perfil do usuário...

 RESPOSTA ENTREGUE AO USUÁRIO:
Olá! Selecionamos apenas locais públicos verificados no OpenStreetMap com acessibilidade para cadeira de rodas e conforto para idosos:

  1. Sebinho Livraria Café e Bistrô Asa Norte (OSM: node/1849203941)
     • Score Auditado: 0.8495 | Evidência: EVID-C37C4CDC
  2. Parque da Cidade Sarah Kubitschek (OSM: way/2938475610)
     • Score Auditado: 0.6546 | Evidência: EVID-32AA2894

===========================================================================
 ENTRADA DO USUÁRIO: "Preciso contratar um frete de caminhão para mudança em Taguatinga."
===========================================================================
 [1. Intake_NLU_Agent] Extraindo Contrato 2 e verificando guardrails...
 [1. Intake_NLU_Agent] Pedido bloqueado na entrada: Solicitação de serviço comercial/logístico (frete/transporte), fora do escopo de encontros sociais públicos.
