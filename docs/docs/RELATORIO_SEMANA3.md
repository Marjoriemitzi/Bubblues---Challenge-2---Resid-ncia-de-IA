# Relatório de Testes: LLM vs RAG (Semana 3)
**Responsável:** Marjorie Mitzi
**Branch de Referência:** `feat/pipeline-agente`

## 1. Objetivo e Metodologia
Este relatório apresenta 4 testes comparativos entre LLM e RAG utilizando o **Pipeline Agêntico** desenvolvido (P3). A base vetorial (`banco_inicial.db`) foi populada via extração web (Tavily), estruturada por Tabela de Regras e vetorizada com o modelo `paraphrase-multilingual-mpnet-base-v2` (768 dimensões).

Foram testados 4 cenários (pedidos válidos, fora de escopo e impossíveis) para avaliar a variação de Alucinação, Taxa de Abstenção e Qualidade da Busca.

## 2. Os 4 Testes: O que muda e por que muda?

### Teste 1: LLM Pura (Sem RAG)
* **Como funciona:** O usuário consulta direto uma LLM, sem acesso ao banco.
* **O que muda:** A alucinação é altíssima. A IA sugere locais baseada em probabilidade de texto da internet.
* **Por que muda:** Sem *grounding* geográfico, o sistema inventa endereços e sugere locais fechados, oferecendo zero segurança física e operacional para o produto.

### Teste 2: RAG Puro (Busca Vetorial Direta, Sem LLM)
* **Como funciona:** A pergunta vira vetor e busca no banco (Similaridade de Cosseno).
* **O que muda (Scores Obtidos):**
  * *Pedido de Café:* Top 1 - Sebinho Livraria (0.59) -> Correto
  * *Pedido de Caminhada:* Top 1 - Parque da Cidade (0.53) -> Correto
  * *Pedido de Frete de Caminhão:* Top 1 - Parque da Cidade (0.24) -> **Falha**
  * *Pedido de Pista de Gelo:* Top 1 - Ernesto Cafés (0.39) -> **Falha**
* **Por que muda:** A alucinação cai para 0%, mas a **Abstenção também é 0%**. A matemática de vetores sempre encontra um "vizinho mais próximo", sendo incapaz de barrar pedidos absurdos.

### Teste 3: RAG + LLM na Saída (Gerador)
* **Como funciona:** O RAG busca no banco, e a LLM formata a resposta no final.
* **O que muda:** A linguagem fica empática e adequada ao usuário.
* **Por que muda:** Resolve a secura do RAG puro, mas herda a sua falha: se o usuário pedir algo longo e confuso, o RAG busca o vetor errado antes mesmo da LLM poder atuar.

### Teste 4: LLM (NLU na Entrada) + RAG (Híbrido) - Arquitetura Proposta
* **Como funciona:** Uma chamada rápida de LLM interpreta e barra pedidos impossíveis ANTES da busca vetorial.
* **O que muda:** Alcançamos **100% de Abstenção Correta** (barra fretes/pistas de gelo) e **0% de Alucinação**.
* **Por que muda:** A união da interpretação semântica (LLM) atuando como *guardrail* de entrada com a precisão matemática (RAG) da base local cobre as falhas individuais de ambas as tecnologias.

## 3. Conclusão e Escolha para o Produto
Com base nos testes empíricos, a melhor abordagem para o **Bubbles** é a do **Teste 4 (RAG Híbrido)**. Essa escolha justifica-se pela eliminação de falsos-positivos perigosos e garantia de que o RAG só será acionado para intenções genuínas de socialização e passeios.

## 4. Links do Projeto
* **Repositório:** [Inserir Link do Repositório]
* **Artefatos:** Scripts de `1_extrator_agente.py` a `5_experimento_marjorie.py` disponíveis na branch `feat/pipeline-agente`.
