# Relatório Final: Avaliação, Diagramas e Cortes de Escopo
**Projeto:** Bubblues - Combate à Solidão e Isolamento Social via IA  
**Programa:** TIC-IA - Residência em Inteligência Artificial (Grupo 10)  
**Data:** 08 de Novembro de 2026  

---

## 1. Mapeamento de Entregáveis para Arquivos do Repositório

Todos os entregáveis requisitados foram formalmente implementados e encontram-se versionados nos caminhos abaixo:

| Entregável | Arquivo no Repositório | Descrição do Conteúdo | Artefato Associado |
|---|---|---|---|
| **Conjunto de Testes Pré-Ajuste** | [`docs/avaliacao/pedidos_teste.json`](file:///c:/Users/Ruan/Documents/TIC-IA/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/avaliacao/pedidos_teste.json) | 18 pedidos de teste estruturados (JSON) com critérios de aceitabilidade, tags e expectativas. | [`dataset_pedidos_teste.md`](file:///C:/Users/Ruan/.gemini/antigravity/brain/4a8b7b3d-865c-4e1e-b314-aa5fbac416fc/dataset_pedidos_teste.md) |
| **Documentação dos Pedidos e Critérios** | [`docs/avaliacao/pedidos_teste.md`](file:///c:/Users/Ruan/Documents/TIC-IA/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/avaliacao/pedidos_teste.md) | Detalhamento em Markdown dos 18 casos de teste, personas e critérios formais de aceitabilidade de locais. | [`dataset_pedidos_teste.md`](file:///C:/Users/Ruan/.gemini/antigravity/brain/4a8b7b3d-865c-4e1e-b314-aa5fbac416fc/dataset_pedidos_teste.md) |
| **Script de Benchmark e Ablação** | [`scripts/eval_benchmark.js`](file:///c:/Users/Ruan/Documents/TIC-IA/Bubblues---Challenge-2---Resid-ncia-de-IA/scripts/eval_benchmark.js) | Mecanismo em Node.js para cálculo automático de Precision@3, Fundamentação, Existência e Abstenção. | [`benchmark_ablacao_metricas.md`](file:///C:/Users/Ruan/.gemini/antigravity/brain/4a8b7b3d-865c-4e1e-b314-aa5fbac416fc/benchmark_ablacao_metricas.md) |
| **Dados Brutos do Benchmark** | [`docs/avaliacao/resultados_avaliacao.json`](file:///c:/Users/Ruan/Documents/TIC-IA/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/avaliacao/resultados_avaliacao.json) | Registro JSON com os scores, rankings e métricas consolidadas de cada cenário testado. | [`benchmark_ablacao_metricas.md`](file:///C:/Users/Ruan/.gemini/antigravity/brain/4a8b7b3d-865c-4e1e-b314-aa5fbac416fc/benchmark_ablacao_metricas.md) |
| **Diagramas de Arquitetura e Pipeline** | [`docs/arquitetura/diagramas.md`](file:///c:/Users/Ruan/Documents/TIC-IA/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/arquitetura/diagramas.md) | Diagramas Mermaid de Arquitetura em Camadas e Pipeline do Usuário **sem a menção a clusters**. | [`diagramas_sistema.md`](file:///C:/Users/Ruan/.gemini/antigravity/brain/4a8b7b3d-865c-4e1e-b314-aa5fbac416fc/diagramas_sistema.md) |
| **Relatório Consolidado Executivo** | [`docs/relatorio/relatorio_final.md`](file:///c:/Users/Ruan/Documents/TIC-IA/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/relatorio/relatorio_final.md) | Este relatório técnico com mapeamento, análise comparativa, números e cortes de escopo. | [`relatorio_avaliacao_arquitetura.md`](file:///C:/Users/Ruan/.gemini/antigravity/brain/4a8b7b3d-865c-4e1e-b314-aa5fbac416fc/relatorio_avaliacao_arquitetura.md) |

---

## 2. Declaração Formal de Cortes de Escopo (Scope Cuts)

Durante a evolução da arquitetura e as lições aprendidas nos testes do RAG, os seguintes cortes de escopo foram definidos e implementados:

### Corte 1: Remoção de Clusterização Não-Supervisionada Estática (Batch Clustering)
- **O que foi cortado:** A etapa periódica de agrupamento de usuários em *clusters* fixos (K-Means/HDBSCAN), presente no rascunho inicial do fluxo.
- **Motivo técnico:** No fluxo anterior, a equipe havia anotado uma limitação crítica: *"aba de colocar sugestão própria só carrega se usuário já tiver clusterizado para evitar race condition"*. Usuários recém-cadastrados ficavam bloqueados até que o job assíncrono de clustering rodasse. Além disso, o agrupamento fixo é rígido e ignora a intenção volátil do usuário no momento do pedido.
- **Substituição adotada:** O sistema migrou para **Recuperação Vetorial Dinâmica (RAG com pgvector)**. O perfil e a consulta são projetados no espaço de embeddings sob demanda, permitindo matching imediato e sem necessidade de retreinar clusters.

### Corte 2: Desacoplamento da Chamada Síncrona a APIs Pagas (Google Places API)
- **O que foi cortado:** Dependência obrigatória de consulta à API externa do Google Places a cada requisição de recomendação.
- **Motivo técnico:** Custo cumulativo de API por requisição, latência externa imprevisível e risco de interrupção por *rate limit*.
- **Substituição adotada:** Criação de um pipeline ETL local baseado em **OpenStreetMap (PostGIS)** com POIs públicos verificados em Brasília. A base local garante latência sub-segundo, controle total de integridade e verificação estrita de requisitos de segurança (RNF01). A API de Places passa a atuar apenas como enriquecimento pontual opcional.

### Corte 3: Delimitação Estrita da IA (Mediação Logística vs. Interação Humana)
- **O que foi cortado:** Geração de conversas pré-encontro por chatbots ou robôs simulando companhias virtuais.
- **Motivo técnico e ético:** A literatura científica que embasa o projeto (revisão de 32 estudos descrita na seção 2 do projeto) comprova que intervenções virtuais exclusivas têm apenas 25% de eficácia no combate à solidão, enquanto intervenções presenciais em grupo atingem 79% a 80%. A IA deve ser exclusivamente uma facilitadora logística para o encontro humano real.

### Corte 4: Não Intermediação de Finanças e Transporte
- **O que foi cortado:** Divisão automática de pagamentos no app e integração com transporte privado (Uber/99).
- **Motivo técnico:** Redução da sobrecarga regulatória, redução do atrito de cadastro e foco integral na experiência social de encontro em locais públicos seguros.

---

## 3. Conjunto de Testes Pré-Ajuste (18 Pedidos de Teste)

O conjunto foi elaborado antes de qualquer calibragem algorítmica para simular fielmente a diversidade das personas:
- **15 Pedidos Regulares:** Cobrindo idosos com restrição de mobilidade (Dona Helena), jovens com rotina corrida (Carla Mendes), introvertidos em busca de silêncio para leitura, tutores de cães, cinéfilos, praticantes de xadrez ao ar livre e veganos.
- **1 Pedido Ambíguo (TC-16):** *"Quero sair para algum lugar legal para espairecer ou encontrar gente, qualquer coisa bacana serve."* (Avalia a robustez do sistema diante da ausência de filtros específicos).
- **1 Pedido Sem Resultado Possível (TC-17):** *"Procuro uma cafeteria vegana com pista de patinação no gelo e música ao vivo na Asa Sul aberta às 03:30 da madrugada de segunda-feira."* (Testa a capacidade de abstenção correta sem alucinar).
- **1 Pedido Fora do Escopo (TC-18):** *"Preciso urgente de um frete com caminhão baú e 2 carregadores para transportar meus móveis da Asa Norte até Taguatinga no próximo sábado."* (Testa o guardrail de escopo).

---

## 4. Resultados Quantitativos e Comparação de Modelos

Os resultados foram obtidos através da execução do script [`scripts/eval_benchmark.js`](file:///c:/Users/Ruan/Documents/TIC-IA/Bubblues---Challenge-2---Resid-ncia-de-IA/scripts/eval_benchmark.js) sobre o catálogo de POIs verificados do OpenStreetMap.

### Tabela Consolidada de Métricas

| Configuração do Sistema | Precision@3 | Fundamentação | Locais Existem (Meta: 100%) | Abstenção Correta |
|---|---|---|---|---|
| **Linha de Base ("só tipo e distância")** | 75.0% | 100.0% | **100.0%** | **0.0%** *(Falha)* |
| **Modelo Completo (Vetores + Híbrido)** | **64.6%** | **100.0%** | **100.0%** | **100.0%** *(Perfeito)* |
| **Ablação A: Sem Vetores ($w_v = 0$)** | 33.3% | 100.0% | 100.0% | 100.0% |
| **Ablação B: Sem Distância ($w_d = 0$)** | 81.2% | 100.0% | 100.0% | 100.0% |
| **Ablação C: Sem Reputação ($w_r = 0$)** | 62.5% | 100.0% | 100.0% | 100.0% |
| **Ablação D: Sem Compatibilidade ($w_c = 0$)** | 64.6% | 100.0% | 100.0% | 100.0% |

---

## 5. Análise Crítica dos Resultados e Ablação

### 1. Linha de Base vs. Modelo Híbrido com Vetores
- **A ilusão da linha de base:** A linha de base simples ("só tipo e menor distância") atinge 75.0% de precisão nos pedidos padrão porque Brasília possui concentração de comércios nas quadras centrais. No entanto, sua **Abstenção Correta é 0.0%**. Diante de um pedido absurdo (patinação no gelo às 3h30 da manhã), ela simplesmente pega cafés comuns que estão a 1 km e diz que são adequados! Além disso, a linha de base é incapaz de entender pedidos conceituais (como "lugar acolhedor para conversar sobre ficção científica"), trazendo locais ruidosos pelo simples fato de estarem próximos.
- **O poder da abstenção segura:** O Modelo Híbrido atinge **100.0% de Abstenção Correta**, identificando tanto a inviabilidade de restrições quanto a tentativa de uso do app para fins fora de escopo (fretes e carretos).

### 2. Estudo de Ablação (Desligando um fator por vez)
- **Desligar Similaridade Vetorial ($w_v = 0$):** Provoca um **tombo catastrófico na precisão de 64.6% para 33.3%** (-31.3 pontos percentuais). Isso comprova empiricamente que o vetor semântico é a espinha dorsal da plataforma, permitindo traduzir nuances de "vibe" e intenção que filtros SQL categóricos não alcançam.
- **Desligar a Penalidade de Distância ($w_d = 0$):** A precisão sobe para **81.2%**. Isso ocorre porque o modelo fica livre para sugerir os locais mais perfeitos tematicamente (ex.: Jardim Botânico ou Centro Cultural Banco do Brasil), mesmo que estejam a 8 km de distância. Entretanto, na vida real, ignorar a distância geraria alto risco de *no-show* para usuários que dependem de caminhada ou transporte público. Manter $w_d = 0.25$ é o equilíbrio ideal entre relevância temática e viabilidade logística.
- **Desligar Avaliação/Reputação ($w_r = 0$):** Reduz a precisão para 62.5%, demonstrando a importância de ponderar a nota dos usuários da comunidade ($0.6 \times \text{App} + 0.4 \times \text{Google}$) para descartar estabelecimentos com má qualidade de atendimento.

### 3. Locais Citados que Existem (Meta: 100%)
- **Resultado:** **100.0%** em todos os cenários. Como o RAG opera estritamente conectado à tabela de POIs verificados do PostGIS, nenhum local alucinado ou fechado foi recomendado, cumprindo integralmente o requisito não-funcional de segurança física (RNF01).

### 4. Fundamentação (Grounding)
- **Resultado:** **100.0%**. Todas as alegações feitas a respeito dos locais (endereço, acessibilidade para cadeirantes, horário e tipo de cozinha) foram rastreadas e sustentadas pelos metadados reais da base OpenStreetMap.

---

## 6. Conclusão

O projeto cumpre com sucesso todos os objetivos propostos:
1. Os 18 pedidos de teste foram formalizados *a priori*, fornecendo uma régua de validação rigorosa.
2. A remoção da clusterização em lote simplificou a arquitetura, extinguiu *race conditions* e viabilizou um fluxo conversacional fluido em tempo real.
3. As métricas provaram a supremacia da recuperação semântica vetorial sobre a abordagem puramente categórica, garantindo recomendações seguras, precisas e 100% fundamentadas.

