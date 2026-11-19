# Demonstração: um fluxo completo, do texto livre à resposta com fontes

Execução **real** (DeepSeek, PostgreSQL com o OSM do DF e modelo de embeddings), gerada por `scripts/demo_fluxo_completo.py`.
As tabelas, a cronologia e as respostas abaixo são a **saída do script, sem edição**; só os trechos "O que este cenário mostra" são comentários nossos. Arquitetura e responsabilidades: [`arquitetura_agentes.md`](arquitetura_agentes.md).

```bash
cd data-pipeline && ./setup_db.sh && cd ..        # banco no ar e populado (uma vez)
python scripts/demo_fluxo_completo.py "Quero um café calmo e acessível para cadeirante na Asa Sul, de manhã, para ler um livro"
python scripts/demo_fluxo_completo.py "..." --modo deterministic      # Retrieval sem LLM
python scripts/demo_fluxo_completo.py "..." --md saida.md             # grava o relato
```

> **Sobre o Communication desta demonstração.** Nos cenários A e B ele é o **Communication Agent (LLM, DeepSeek)**, `orchestrator/communication_agent.py`, que evolui o formatador do PR #15 (agora o fallback). A demonstração monta o **grafo padrão** (`montar_grafo`): NLU Agent + Retrieval do `RETRIEVAL_MODE` + Communication Agent. Cada texto passa por **verificação em código** (lugares, links e distâncias existem nas evidências; avisos obrigatórios presentes). Nos desvios (C, D, E) a mensagem vem pronta do NLU e **não chama o LLM**. Como o NLU e os agentes usam LLM, **cada execução pode variar um pouco**; estas são execuções reais de 19/11/2026.

---

## Cenário A: o caminho feliz (todos colaboram)

> **Pergunta do usuário:** Quero um café calmo e acessível para cadeirante na Asa Sul, de manhã, para ler um livro

Modo do Retrieval: `llm` · Communication: Communication Agent (LLM) · request_id `demo-A`

### 1. NLU Agent (LLM): texto livre → `structured_request` (Contrato 2)

| Campo | Valor |
|---|---|
| intenção válida / fora de escopo / impossível | True / False / False |
| atividade | ler um livro em café calmo |
| categorias (da base) | `['cafe']` |
| clima (vibe) | calmo |
| tolerância a ruído | baixo |
| região · raio | Asa Sul · 3.0 km |
| turno · horário | manha · None |
| acessibilidade | cadeira de rodas=True, idosos=False, pet=False |
| foco semântico | `['calmo', 'acessível', 'leitura']` |
| pergunta de esclarecimento | None |

O texto livre foi **descartado** logo depois (RNF02): `raw_query` = `None` no estado.

### 2. Retrieval: o que aconteceu por dentro (cronologia)

- `  4.0s` **NLU** chamou o LLM (3.9 s) e devolveu o JSON validado pelo contrato.
- `  5.4s` **LLM, passo 1** (1.4 s) pediu: `resolver_regiao({"nome": "Asa Sul"})`; `listar_categorias({})`
  - `  5.4s` tool **resolver_regiao** → `{"regioes": ["Asa Sul"]}`
  - `  5.4s` tool **listar_categorias** → `{"n_categorias": 31}`
- `  6.7s` **LLM, passo 2** (1.3 s) pediu: `buscar_lugares({"latitude": -15.8169455, "longitude": -47.900049, "raio_km": 3, "cat…)`
  - `  6.8s` tool **buscar_lugares** → `{"busca_id": "B1", "status": "EXPANDED_RADIUS", "total": 3, "raio_aplicado_km": 6.0, "raio_ampliado": true, "ajustes": [], "lugares": ["Tomilla Café", "Saboretto Cafés Especiais", "Caramella"]}`
- `  8.0s` **LLM, passo 3** (1.2 s) pediu: `validar_candidatos({"busca_id": "B1"})`
  - `  8.0s` tool **validar_candidatos** → `{"todos_aprovados": true, "reprovados": []}`
- `  9.4s` **LLM, passo 4** (1.3 s) decidiu: `{"busca_escolhida": "B1", "place_ids": ["2723", "970", "1188"], "motivo": "Três cafés aprovados na auditoria, todos com wheelchair=yes; priorizei os que abrem de manhã (Saboretto 09h, Caramella 07h30…`
- `  9.4s` **GATE** auditou a busca `B1` (seleção ['2723', '970', '1188']): **APROVADO**; evidências: ['Saboretto Cafés Especiais', 'Caramella', 'Tomilla Café']
- ` 12.0s` **Communication** chamou o LLM (2.7 s) para redigir a resposta; o texto passa por verificação em código.

### 3. Evidências entregues (Contrato 4, auditadas e gravadas no PostgreSQL)

| # | Lugar | Distância | Score | Fonte no OpenStreetMap | Integridade do score |
|---|---|---:|---:|---|---|
| 1 | **Saboretto Cafés Especiais** | 3.32 km | 0.628 | https://www.openstreetmap.org/node/11913506269 | ok |
| 2 | **Caramella** | 4.29 km | 0.625 | https://www.openstreetmap.org/node/3222516874 | ok |
| 3 | **Tomilla Café** | 3.78 km | 0.661 | https://www.openstreetmap.org/node/3958863455 | ok |

Notas de fundamentação do primeiro lugar (só fatos vindos do banco):

- Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/11913506269).
- Acessibilidade: wheelchair=yes.
- Nível de ruído: não informado.
- Horário de funcionamento: Mo-Su 09:00-19:00 (compatível com o pedido).

### 4. Communication → resposta ao usuário

```text
Olá! Encontrei três cafés no Distrito Federal, com base no OpenStreetMap. O raio da busca foi ampliado de 3 km para 6 km porque não havia resultados suficientes no raio pedido, então os lugares podem estar mais longe do que o desejado.

1. Tomilla Café — 3,78 km. Estabelecimento verificado e público no OpenStreetMap, com acessibilidade (wheelchair=yes). O nível de ruído não foi informado. Link: https://www.openstreetmap.org/node/3958863455

2. Saboretto Cafés Especiais — 3,32 km. Estabelecimento verificado e público no OpenStreetMap, com acessibilidade (wheelchair=yes) e assentos externos. Horário de funcionamento: Mo-Su 09:00-19:00, compatível com o pedido. Link: https://www.openstreetmap.org/node/11913506269

3. Caramella — 4,29 km. Estabelecimento verificado e público no OpenStreetMap, com acessibilidade (wheelchair=yes). Horário de funcionamento: Mo-Su 07:30-21:00, compatível com o pedido. Link: https://www.openstreetmap.org/node/3222516874

Sobre o horário: não foi possível confirmar no OpenStreetMap o horário pedido ("manhã") para o Tomilla Café. Vale confirmar com o local antes de ir.
```

### 5. Trilha do grafo (`agent_trace`)

| Nó | Próximo | Justificativa |
|---|---|---|
| `nlu_guardrail_agent` | `retrieval` | intent_valid=true: segue para busca |
| `retrieval` | `communication_agent` | evidencias aprovadas pelo gate de auditoria |
| `communication_agent` | `__end__` | fim do fluxo |

Nota do Retrieval: `agente llm: 3 aprovado(s); passos=4; tools=buscar_lugaresx1,listar_categoriasx1,resolver_regiaox1,validar_candidatosx1; reconsultas=0; tokens=10310/402/0; consulta_id=8ddd46c7-482f-4119-a2c2-334626d0681b`

**O que este cenário mostra**

- O **NLU Agent** transformou a frase em um contrato (Contrato 2) e **marcou acessibilidade** a partir de "cadeirante", sem ninguém pedir.
- O **Retrieval Agent** decidiu a ordem das ferramentas: duas em paralelo (região e categorias), depois a busca, depois a validação, e só então escolheu **quais 3 lugares** entregar. Os **filtros de acessibilidade** foram aplicados pela ferramenta, não pelo modelo.
- O **gate** auditou a escolha final; só então os lugares viraram **evidências** (Contrato 4), gravadas no PostgreSQL com o link do OSM.
- O **Communication Agent (LLM)** redigiu a resposta só com os fatos das evidências. O código **calculou dois avisos obrigatórios** e o texto os trouxe: o **raio foi ampliado de 3 km para 6 km** e o **horário "manhã" não pôde ser confirmado** para um dos cafés (sem `opening_hours` no OSM). Antes o usuário não era avisado de nenhum dos dois.

---

## Cenário B: colaboração com autocorreção (horário)

> **Pergunta do usuário:** Quero uma lanchonete ou café aberto até às 22h, com clima jovem, no Plano Piloto

Modo do Retrieval: `llm` · Communication: Communication Agent (LLM) · request_id `demo-B`

### 1. NLU Agent (LLM): texto livre → `structured_request` (Contrato 2)

| Campo | Valor |
|---|---|
| intenção válida / fora de escopo / impossível | True / False / False |
| atividade | lanchar ou tomar café |
| categorias (da base) | `['cafe', 'fast_food']` |
| clima (vibe) | jovem |
| tolerância a ruído | indiferente |
| região · raio | Plano Piloto · 3.0 km |
| turno · horário | None · até 22h |
| acessibilidade | cadeira de rodas=False, idosos=False, pet=False |
| foco semântico | `['jovem', 'lanchonete', 'café', 'descontraído']` |
| pergunta de esclarecimento | None |

O texto livre foi **descartado** logo depois (RNF02): `raw_query` = `None` no estado.

### 2. Retrieval: o que aconteceu por dentro (cronologia)

- `  2.4s` **NLU** chamou o LLM (2.3 s) e devolveu o JSON validado pelo contrato.
- `  3.6s` **LLM, passo 1** (1.3 s) pediu: `resolver_regiao({"nome": "Plano Piloto"})`; `listar_categorias({})`
  - `  3.6s` tool **resolver_regiao** → `{"regioes": ["Plano Piloto"]}`
  - `  3.7s` tool **listar_categorias** → `{"n_categorias": 31}`
- `  4.9s` **LLM, passo 2** (1.2 s) pediu: `buscar_lugares({"latitude": -15.7185371, "longitude": -47.9362166, "raio_km": 3, "ca…)`
  - `  5.0s` tool **buscar_lugares** → `{"busca_id": "B1", "status": "EXPANDED_RADIUS", "total": 3, "raio_aplicado_km": 6.0, "raio_ampliado": true, "ajustes": [], "lugares": ["Marilda Café", "Acorde 27", "Dia de açai"]}`
- `  6.5s` **LLM, passo 3** (1.5 s) pediu: `buscar_lugares({"categorias": ["cafe", "fast_food"], "k": 5, "latitude": -15.7185371…)`
  - `  6.6s` tool **buscar_lugares** → `{"busca_id": "B2", "status": "EXPANDED_RADIUS", "total": 5, "raio_aplicado_km": 6.0, "raio_ampliado": true, "ajustes": [], "lugares": ["Cheirin Bão", "Glória", "Marilda Café", "Casa do Pão de Queijo", "Acorde 27"]}`
- `  7.4s` **LLM, passo 4** (0.8 s) pediu: `validar_candidatos({"busca_id": "B2"})`
  - `  7.4s` tool **validar_candidatos** → `{"todos_aprovados": false, "reprovados": ["2373", "2457"]}`
- `  8.7s` **LLM, passo 5** (1.3 s) decidiu: `{"busca_escolhida": "B2", "place_ids": ["1431", "1430", "1523"], "motivo": "Cafés aprovados na auditoria (Cheirin Bão, Glória, Casa do Pão de Queijo); a busca ampliou o raio para 6 km, então todos fi…`
- `  8.8s` **GATE** auditou a busca `B2` (seleção ['1431', '1430', '1523']): **APROVADO**; evidências: ['Cheirin Bão', 'Glória', 'Casa do Pão de Queijo']
- ` 10.9s` **Communication** chamou o LLM (2.1 s) para redigir a resposta; o texto passa por verificação em código.

### 3. Evidências entregues (Contrato 4, auditadas e gravadas no PostgreSQL)

| # | Lugar | Distância | Score | Fonte no OpenStreetMap | Integridade do score |
|---|---|---:|---:|---|---|
| 1 | **Cheirin Bão** | 5.80 km | 0.563 | https://www.openstreetmap.org/node/4591337317 | ok |
| 2 | **Glória** | 5.77 km | 0.545 | https://www.openstreetmap.org/node/4591337315 | ok |
| 3 | **Casa do Pão de Queijo** | 4.35 km | 0.538 | https://www.openstreetmap.org/node/4825889842 | ok |

Notas de fundamentação do primeiro lugar (só fatos vindos do banco):

- Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/4591337317).
- Acessibilidade: wheelchair=não especificado.
- Nível de ruído: não informado.

### 4. Communication → resposta ao usuário

```text
Olá! Encontrei estas opções de espaços públicos no Distrito Federal:

1. Cheirin Bão — 5,8 km. Estabelecimento verificado e público no OpenStreetMap, registrado como café. Acessibilidade e nível de ruído não especificados. Link: https://www.openstreetmap.org/node/4591337317

2. Glória — 5,77 km. Estabelecimento verificado e público no OpenStreetMap, registrado como café. Acessibilidade e nível de ruído não especificados. Link: https://www.openstreetmap.org/node/4591337315

3. Casa do Pão de Queijo — 4,35 km. Estabelecimento verificado e público no OpenStreetMap, registrado como café e cafeteria. Acessibilidade e nível de ruído não especificados. Link: https://www.openstreetmap.org/node/4825889842

Avisos importantes: o raio da busca foi ampliado de 3 km para 6 km porque não havia resultados suficientes no raio pedido, então os lugares podem estar mais longe do que o desejado. Além disso, não foi possível confirmar no OpenStreetMap o horário pedido ("até 22h") para Cheirin Bão, Glória e Casa do Pão de Queijo; vale confirmar com o local antes de ir.
```

### 5. Trilha do grafo (`agent_trace`)

| Nó | Próximo | Justificativa |
|---|---|---|
| `nlu_guardrail_agent` | `retrieval` | intent_valid=true: segue para busca |
| `retrieval` | `communication_agent` | evidencias aprovadas pelo gate de auditoria |
| `communication_agent` | `__end__` | fim do fluxo |

Nota do Retrieval: `agente llm: 3 aprovado(s); passos=5; tools=buscar_lugaresx2,listar_categoriasx1,resolver_regiaox1,validar_candidatosx1; reconsultas=0; tokens=14872/578/0; consulta_id=f5f80ed6-6f42-4f07-b3d7-e09e5e68d047`

**O que este cenário mostra**

- O pedido exige **"aberto até às 22h"**. O agente fez **duas buscas** (a segunda com outras categorias) e chamou **`validar_candidatos`**, que **reprovou 2 lugares** (`2373` e `2457`). Entre eles, o Marilda Café, cujo `opening_hours` no OSM é `Tu-Fr 12:00-20:00` (fecha antes das 22h): reprovação com evidência, não com palpite.
- O agente então **escolheu só os 3 aprovados** (`place_ids`) e o gate confirmou. A autocorreção aconteceu **antes** do gate, por isso `reconsultas=0`.
- Os 3 lugares entregues **não têm horário no OSM**; o gate só reprova com evidência. O **Communication Agent** então avisou que o "até 22h" **não pôde ser confirmado** para os três ("vale confirmar com o local antes de ir") e que o raio passou de 3 para 6 km. Esses avisos são impostos em código: se o texto do modelo os omitisse, a verificação o recusaria.

---

## Cenários curtos: o NLU decide sozinho e a busca nem acontece

### C. Fora de escopo
> **Pergunta do usuário:** Preciso de um frete com caminhão baú para levar meus móveis da Asa Norte até Taguatinga

#### Resposta ao usuário (Communication)

```text
Não consigo atender a esse pedido porque ele está fora do escopo da busca. Motivo: serviço de frete/mudança, não é local público. Tente buscar locais públicos ou estabelecimentos da região.
```

#### Trilha do grafo (`agent_trace`)

| Nó | Próximo | Justificativa |
|---|---|---|
| `nlu_guardrail_agent` | `communication_agent` | intent_valid=false (out_of_scope): abstencao precoce |
| `communication_agent` | `__end__` | fim do fluxo |

### D. Pedido ambíguo
> **Pergunta do usuário:** Quero sair para algum lugar legal, qualquer coisa bacana serve

#### Resposta ao usuário (Communication)

```text
Voce prefere um lugar mais calmo ou mais movimentado?
```

#### Trilha do grafo (`agent_trace`)

| Nó | Próximo | Justificativa |
|---|---|---|
| `nlu_guardrail_agent` | `communication_agent` | clarification_needed: pergunta ao usuario antes de buscar |
| `communication_agent` | `__end__` | fim do fluxo |

### E. Região que não existe
> **Pergunta do usuário:** Quero um café tranquilo em Narnia

#### Resposta ao usuário (Communication)

```text
Não foi possível encontrar uma combinação viável dos critérios solicitados. Motivo: Narnia não é uma região do Distrito Federal. Você pode flexibilizar algum requisito ou ampliar a região.
```

#### Trilha do grafo (`agent_trace`)

| Nó | Próximo | Justificativa |
|---|---|---|
| `nlu_guardrail_agent` | `communication_agent` | intent_valid=false (impossible_criteria): abstencao precoce |
| `communication_agent` | `__end__` | fim do fluxo |

Nos três casos o **Retrieval nem é chamado**: o NLU Agent barra o pedido e o grafo vai direto ao Communication. Não há nenhuma chamada de busca, e o custo é uma única chamada de LLM.

---

## O que a demonstração prova, e o que ainda falta

**Prova:** os componentes colaboram sem que nenhum precise confiar no outro: o NLU não inventa categorias, o Retrieval não escreve resultado, o gate audita o que sai e a auditoria fica no banco. Cada decisão aparece no `agent_trace` e no Langfuse.

**Falta** (também em [`arquitetura_agentes.md`](arquitetura_agentes.md), seção 9): revisar com pessoas o tom do Communication Agent e testá-lo com os perfis (Helena, Carla); plugar o **NLU Agent no grafo padrão** (hoje ele só roda nesta demonstração; a avaliação usa pedidos já estruturados); e revisar com pessoas os rótulos da avaliação.
