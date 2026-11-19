# Demonstração: um fluxo completo, do texto livre à resposta com fontes

Execução **real** (DeepSeek, PostgreSQL com o OSM do DF e modelo de embeddings), gerada por `scripts/demo_fluxo_completo.py`.
As tabelas, a cronologia e as respostas abaixo são a **saída do script, sem edição**; só os trechos "O que este cenário mostra" são comentários nossos. Arquitetura e responsabilidades: [`arquitetura_agentes.md`](arquitetura_agentes.md).

```bash
cd data-pipeline && ./setup_db.sh && cd ..        # banco no ar e populado (uma vez)
python scripts/demo_fluxo_completo.py "Quero um café calmo e acessível para cadeirante na Asa Sul, de manhã, para ler um livro"
python scripts/demo_fluxo_completo.py "..." --modo deterministic      # Retrieval sem LLM
python scripts/demo_fluxo_completo.py "..." --md saida.md             # grava o relato
```

> **Sobre o Communication desta demonstração.** No grafo padrão o Communication ainda é um *stub* (responde só `top-3 auditado`). Para mostrar uma resposta de
> verdade, as execuções abaixo plugam o `communication_agent` do **PR #15** (um formatador determinístico, **não é LLM**), carregado do branch dele com
> `--comunicacao arquivo.py:communication_agent`. Sem isso, a etapa 4 mostra o texto do stub; as etapas 1 a 3 e 5 são idênticas.
> Como o NLU e o agente usam LLM, **cada execução pode variar um pouco**; estas são execuções reais de 19/11/2026.

---

## Cenário A: o caminho feliz (todos colaboram)

> **Pergunta do usuário:** Quero um café calmo e acessível para cadeirante na Asa Sul, de manhã, para ler um livro

Modo do Retrieval: `llm` · Communication: formatador do PR #15 · request_id `demo-A`

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

- `  4.6s` **NLU** chamou o LLM (4.5 s) e devolveu o JSON validado pelo contrato.
- `  6.1s` **LLM, passo 1** (1.5 s) pediu: `resolver_regiao({"nome": "Asa Sul"})`; `listar_categorias({})`
  - `  6.1s` tool **resolver_regiao** → `{"regioes": ["Asa Sul"]}`
  - `  6.1s` tool **listar_categorias** → `{"n_categorias": 31}`
- `  7.8s` **LLM, passo 2** (1.6 s) pediu: `buscar_lugares({"latitude": -15.8169455, "longitude": -47.900049, "raio_km": 3, "cat…)`
  - `  7.9s` tool **buscar_lugares** → `{"busca_id": "B1", "status": "EXPANDED_RADIUS", "total": 3, "raio_aplicado_km": 6.0, "raio_ampliado": true, "ajustes": [], "lugares": ["Tomilla Café", "Saboretto Cafés Especiais", "Caramella"]}`
- `  9.2s` **LLM, passo 3** (1.4 s) pediu: `validar_candidatos({"busca_id": "B1"})`
  - `  9.2s` tool **validar_candidatos** → `{"todos_aprovados": true, "reprovados": []}`
- ` 10.9s` **LLM, passo 4** (1.7 s) decidiu: `{"busca_escolhida": "B1", "place_ids": ["2723", "970", "1188"], "motivo": "Cafés aprovados na auditoria, todos com wheelchair=yes; priorizei os que abrem de manhã (Saboretto 09h, Caramella 07h30) — a…`
- ` 10.9s` **GATE** auditou a busca `B1` (seleção ['2723', '970', '1188']): **APROVADO**; evidências: ['Saboretto Cafés Especiais', 'Caramella', 'Tomilla Café']

### 3. Evidências entregues (Contrato 4, auditadas e gravadas no PostgreSQL)

| # | Lugar | Distância | Score | Fonte no OpenStreetMap | Integridade do score |
|---|---|---:|---:|---|---|
| 1 | **Saboretto Cafés Especiais** | 3.32 km | 0.625 | https://www.openstreetmap.org/node/11913506269 | ok |
| 2 | **Caramella** | 4.29 km | 0.614 | https://www.openstreetmap.org/node/3222516874 | ok |
| 3 | **Tomilla Café** | 3.78 km | 0.652 | https://www.openstreetmap.org/node/3958863455 | ok |

Notas de fundamentação do primeiro lugar (só fatos vindos do banco):

- Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/11913506269).
- Acessibilidade: wheelchair=yes.
- Nível de ruído: não informado.
- Horário de funcionamento: Mo-Su 09:00-19:00 (compatível com o pedido).

### 4. Communication → resposta ao usuário

```text
Confira os locais aprovados na validação:

1. Tomilla Café
Localização: Endereço não informado
Distância: 3.78 km
Destaques: Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/3958863455). Acessibilidade: wheelchair=yes. Nível de ruído: não informado. Características registradas no OpenStreetMap: amenity=cafe, wheelchair=yes
Fonte OSM: https://www.openstreetmap.org/node/3958863455

2. Saboretto Cafés Especiais
Localização: Endereço não informado
Distância: 3.32 km
Destaques: Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/11913506269). Acessibilidade: wheelchair=yes. Nível de ruído: não informado. Horário de funcionamento: Mo-Su 09:00-19:00 (compatível com o pedido). Características registradas no OpenStreetMap: amenity=cafe, cuisine=coffee_shop;sandwich;breakfast;dessert;crepe, wheelchair=yes, outdoor_seating=yes
Fonte OSM: https://www.openstreetmap.org/node/11913506269

3. Caramella
Localização: Endereço não informado
Distância: 4.29 km
Destaques: Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/3222516874). Acessibilidade: wheelchair=yes. Nível de ruído: não informado. Horário de funcionamento: Mo-Su 07:30-21:00 (compatível com o pedido). Características registradas no OpenStreetMap: amenity=cafe, wheelchair=yes
Fonte OSM: https://www.openstreetmap.org/node/3222516874
```

### 5. Trilha do grafo (`agent_trace`)

| Nó | Próximo | Justificativa |
|---|---|---|
| `nlu_guardrail_agent` | `retrieval` | intent_valid=true: segue para busca |
| `retrieval` | `communication_agent` | evidencias aprovadas pelo gate de auditoria |
| `communication_agent` | `__end__` | fim do fluxo |

Nota do Retrieval: `agente llm: 3 aprovado(s); passos=4; tools=buscar_lugaresx1,listar_categoriasx1,resolver_regiaox1,validar_candidatosx1; reconsultas=0; tokens=10306/391/0; consulta_id=46f63ab1-9803-4859-852e-88a4b0ab8ffb`


**O que este cenário mostra**

- O **NLU Agent** transformou a frase em um contrato (Contrato 2) e **marcou acessibilidade** a partir de "cadeirante", sem ninguém pedir.
- O **Retrieval Agent** decidiu a ordem das ferramentas: duas em paralelo (região e categorias), depois a busca, depois a validação, e só então escolheu **quais 3 lugares** entregar.
- Os **filtros de acessibilidade** não foram passados pelo modelo: a ferramenta os aplicou sozinha. Por isso todos os lugares têm `wheelchair=yes`.
- O **gate** auditou a escolha final e só então os lugares viraram **evidências** (Contrato 4), gravadas no PostgreSQL com o link do OSM.
- **Uma coisa que o usuário não vê, mas deveria:** o NLU assumiu 3 km, não havia café acessível nesse raio, e a busca **ampliou o raio para 6 km** (`EXPANDED_RADIUS`). Os 3 lugares estão entre 3,3 e 4,3 km, e **a resposta não avisa isso**. O sistema fez o que foi projetado, mas o Communication deveria dizê-lo.

---

## Cenário B: colaboração com autocorreção (horário)

> **Pergunta do usuário:** Quero uma lanchonete ou café aberto até às 22h, com clima jovem, no Plano Piloto

Modo do Retrieval: `llm` · Communication: formatador do PR #15 · request_id `demo-B`

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
| foco semântico | `['jovem', 'descontraído', 'lanches', 'café']` |
| pergunta de esclarecimento | None |

O texto livre foi **descartado** logo depois (RNF02): `raw_query` = `None` no estado.

### 2. Retrieval: o que aconteceu por dentro (cronologia)

- `  5.2s` **NLU** chamou o LLM (5.1 s) e devolveu o JSON validado pelo contrato.
- `  6.5s` **LLM, passo 1** (1.3 s) pediu: `resolver_regiao({"nome": "Plano Piloto"})`; `listar_categorias({})`
  - `  6.5s` tool **resolver_regiao** → `{"regioes": ["Plano Piloto"]}`
  - `  6.5s` tool **listar_categorias** → `{"n_categorias": 31}`
- `  8.1s` **LLM, passo 2** (1.5 s) pediu: `buscar_lugares({"latitude": -15.7185371, "longitude": -47.9362166, "raio_km": 3, "ca…)`
  - `  8.2s` tool **buscar_lugares** → `{"busca_id": "B1", "status": "EXPANDED_RADIUS", "total": 3, "raio_aplicado_km": 6.0, "raio_ampliado": true, "ajustes": [], "lugares": ["Marilda Café", "Acorde 27", "Casa do Pão de Queijo"]}`
- `  9.7s` **LLM, passo 3** (1.5 s) pediu: `buscar_lugares({"categorias": ["cafe", "fast_food"], "k": 3, "latitude": -15.7185371…)`
  - `  9.8s` tool **buscar_lugares** → `{"busca_id": "B2", "status": "EXPANDED_RADIUS", "total": 3, "raio_aplicado_km": 6.0, "raio_ampliado": true, "ajustes": [], "lugares": ["Casa do Pão de Queijo", "Marilda Café", "Genaro - jazz burger café"]}`
- ` 10.8s` **LLM, passo 4** (1.0 s) pediu: `validar_candidatos({"busca_id": "B2"})`
  - ` 10.8s` tool **validar_candidatos** → `{"todos_aprovados": false, "reprovados": ["2373"]}`
- ` 12.2s` **LLM, passo 5** (1.4 s) decidiu: `{"busca_escolhida": "B2", "place_ids": ["1523", "961"], "motivo": "Cafés aprovados na auditoria com perfil jovem/descontraído para lanchar; a busca ampliou o raio para 6 km, então os dois ficam além …`
- ` 12.2s` **GATE** auditou a busca `B2` (seleção ['1523', '961']): **APROVADO**; evidências: ['Casa do Pão de Queijo', 'Genaro - jazz burger café']

### 3. Evidências entregues (Contrato 4, auditadas e gravadas no PostgreSQL)

| # | Lugar | Distância | Score | Fonte no OpenStreetMap | Integridade do score |
|---|---|---:|---:|---|---|
| 1 | **Casa do Pão de Queijo** | 4.35 km | 0.573 | https://www.openstreetmap.org/node/4825889842 | ok |
| 2 | **Genaro - jazz burger café** | 5.68 km | 0.569 | https://www.openstreetmap.org/node/3211680213 | ok |

Notas de fundamentação do primeiro lugar (só fatos vindos do banco):

- Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/4825889842).
- Acessibilidade: wheelchair=não especificado.
- Nível de ruído: não informado.

### 4. Communication → resposta ao usuário

```text
Confira os locais aprovados na validação:

1. Casa do Pão de Queijo
Localização: Endereço não informado
Distância: 4.35 km
Destaques: Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/4825889842). Acessibilidade: wheelchair=não especificado. Nível de ruído: não informado. Características registradas no OpenStreetMap: amenity=cafe, cuisine=coffee_shop
Fonte OSM: https://www.openstreetmap.org/node/4825889842

2. Genaro - jazz burger café
Localização: Endereço não informado
Distância: 5.68 km
Destaques: Estabelecimento verificado e público no OpenStreetMap (https://www.openstreetmap.org/node/3211680213). Acessibilidade: wheelchair=não especificado. Nível de ruído: não informado. Características registradas no OpenStreetMap: amenity=cafe
Fonte OSM: https://www.openstreetmap.org/node/3211680213
```

### 5. Trilha do grafo (`agent_trace`)

| Nó | Próximo | Justificativa |
|---|---|---|
| `nlu_guardrail_agent` | `retrieval` | intent_valid=true: segue para busca |
| `retrieval` | `communication_agent` | evidencias aprovadas pelo gate de auditoria |
| `communication_agent` | `__end__` | fim do fluxo |

Nota do Retrieval: `agente llm: 2 aprovado(s); passos=5; tools=buscar_lugaresx2,listar_categoriasx1,resolver_regiaox1,validar_candidatosx1; reconsultas=0; tokens=14486/556/0; consulta_id=7a9426d8-c1e7-4166-a14e-ef838bd7ad85`


**O que este cenário mostra**

- O pedido exige **"aberto até às 22h"**. O agente fez **duas buscas** (a segunda com outras categorias) e chamou **`validar_candidatos`** na segunda.
- A ferramenta **reprovou o lugar `2373`** (Marilda Café, cujo horário no OSM é `Tu-Fr 12:00-20:00`: fecha antes das 22h) com **evidência**, não com palpite.
- O agente então **escolheu só os 2 aprovados** (`place_ids`) e o gate confirmou. A autocorreção aconteceu **antes** do gate, por isso `reconsultas=0`.
- **Uma ressalva honesta:** os 2 lugares entregues **não têm horário no OSM**. O sistema só reprova com evidência, então eles passaram como "não confirmado", e a resposta ao usuário **não diz** que o "até 22h" não pôde ser confirmado. Também foram entregues a 4,4 e 5,7 km, por causa da ampliação do raio.

---

## Cenários curtos: o NLU decide sozinho e a busca nem acontece

### C. Fora de escopo
> **Pergunta do usuário:** Preciso de um frete com caminhão baú para levar meus móveis da Asa Norte até Taguatinga

#### Resposta ao usuário (Communication)

```text
Não consigo atender a esse pedido porque ele está fora do escopo da busca. Motivo: serviço de transporte de mudança. Tente buscar locais públicos ou estabelecimentos da região.
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
Voce prefere um lugar mais tranquilo ou mais movimentado?
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

**Falta** (também em [`arquitetura_agentes.md`](arquitetura_agentes.md), seção 9): um Communication **com LLM** que avise quando o raio foi ampliado ou quando o horário não foi confirmado; plugar o **NLU Agent no grafo padrão** (hoje ele só roda nesta demonstração; a avaliação usa pedidos já estruturados); e revisar com pessoas os rótulos da avaliação.
