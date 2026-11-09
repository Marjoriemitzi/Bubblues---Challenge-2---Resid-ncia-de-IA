# Bubblues — Challenge 2 (Residência em IA)

> **"Como ajudar pessoas a criar vínculos significativos por meio de encontros presenciais de forma segura?"**  
> *Grupo 10 — TIC-IA / Residência em Inteligência Artificial*

Este repositório contém a modelagem, a arquitetura de software, o conjunto de testes pré-ajuste e o benchmark de avaliação do ecossistema de Inteligência Artificial do projeto **Bubblues**.

---

## 📌 Visão Geral do Projeto

O **Bubblues** conecta pessoas com alta compatibilidade psicossocial em pequenos grupos (3 a 4 participantes) para encontros presenciais em espaços públicos e comerciais verificados (cafés calmos, centros culturais, parques abertos).

A IA remove a sobrecarga cognitiva e o atrito de decisão na escolha de locais seguros, garantindo:
- **100% de locais reais e verificados** (PostGIS + OpenStreetMap);
- **Recuperação Vetorial Híbrida** (`pgvector` + similaridade semântica de intenção e "vibe");
- **Score multi-fatorial de recomendação** com reputação comunitária ($0.4 \times \text{Google} + 0.6 \times \text{Usuários}$);
- **Guardrails de escopo e abstenção ativa** para consultas inviáveis ou fora do domínio.

---

## 📂 Estrutura do Repositório e Entregáveis

```text
├── docs/
│   ├── arquitetura/
│   │   └── diagramas.md               # Diagramas Mermaid de Arquitetura e Pipeline (sem clusters)
│   ├── avaliacao/
│   │   ├── pedidos_teste.json         # 18 pedidos de teste estruturados (JSON)
│   │   ├── pedidos_teste.md           # Documentação dos testes, personas e critérios de aceitabilidade
│   │   └── resultados_avaliacao.json  # Resultados brutos consolidados do benchmark
│   ├── docs/
│   │   ├── definicao_projec.md        # Documento fundacional do Grupo 10 (problema, personas, RF/RNF)
│   │   └── perguntas_usuario.md       # Questionário psicossocial de onboarding do usuário
│   ├── img/                           # Diagramas e rascunhos visuais originais
│   └── relatorio/
│       └── relatorio_final.md         # Relatório técnico consolidado e cortes de escopo
├── scripts/
│   └── eval_benchmark.js              # Script executável do benchmark e estudo de ablação
├── package.json                       # Configuração e scripts de execução Node.js
└── README.md                          # Este documento
```

---

## 🚀 Como Executar o Benchmark de Avaliação

O benchmark é totalmente independente e pode ser executado com Node.js:

```bash
# Execução direta via Node:
node scripts/eval_benchmark.js

# Ou via npm test:
npm test
```

O script calcula automaticamente:
1. **Precision@3** para todas as consultas válidas;
2. **Fundamentação (Grounding)** dos atributos gerados;
3. **Existência Real dos Locais** (meta de 100% contra a base PostGIS);
4. **Abstenção Correta** para consultas impossíveis ou fora de escopo;
5. **Comparação** entre a Linha de Base ("só tipo e distância") e o Modelo Híbrido com Vetores;
6. **Estudo de Ablação** desligando um fator do score de cada vez ($w_v=0$, $w_d=0$, $w_r=0$, $w_c=0$).

---

## 📊 Resumo dos Resultados

| Cenário | Precision@3 | Fundamentação | Locais Existem (Meta: 100%) | Abstenção Correta |
|---|---|---|---|---|
| **Linha de Base ("só tipo e distância")** | 75.0% | 100.0% | **100.0%** | **0.0%** *(Falha)* |
| **Modelo Completo (Vetores + Híbrido)** | **64.6%** | **100.0%** | **100.0%** | **100.0%** *(Perfeito)* |
| **Ablação A: Sem Vetores ($w_v = 0$)** | 33.3% | 100.0% | 100.0% | 100.0% |
| **Ablação B: Sem Distância ($w_d = 0$)** | 81.2% | 100.0% | 100.0% | 100.0% |
| **Ablação C: Sem Reputação ($w_r = 0$)** | 62.5% | 100.0% | 100.0% | 100.0% |
| **Ablação D: Sem Compatibilidade ($w_c = 0$)** | 64.6% | 100.0% | 100.0% | 100.0% |

---

## 📐 Documentação e Links Relevantes

- **Diagramas de Arquitetura & Pipeline (sem clusters):** [`docs/arquitetura/diagramas.md`](docs/arquitetura/diagramas.md)
- **Especificação dos Pedidos de Teste e Critérios de Aceitação:** [`docs/avaliacao/pedidos_teste.md`](docs/avaliacao/pedidos_teste.md)
- **Relatório Técnico Consolidado e Cortes de Escopo:** [`docs/relatorio/relatorio_final.md`](docs/relatorio/relatorio_final.md)
- **Definição de Projeto Inicial do Grupo 10:** [`docs/docs/definicao_projec.md`](docs/docs/definicao_projec.md)
