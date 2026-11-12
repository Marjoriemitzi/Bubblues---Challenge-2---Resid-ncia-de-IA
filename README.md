# Bubbles — Challenge 2 (Residência em IA)

> **"Como ajudar pessoas a criar vínculos significativos por meio de encontros presenciais de forma segura?"**  
> *Grupo 10 — TIC-IA / Residência em Inteligência Artificial*

---

## 📌 Visão Geral do Projeto

O **Bubbles** é uma plataforma inteligente projetada para combater a solidão e o isolamento social entre adultos e idosos. O sistema conecta pessoas desconhecidas com alta compatibilidade psicossocial, viabilizando encontros presenciais em pequenos grupos de **3 a 8 pessoas** em locais públicos e comerciais seguros e verificados da comunidade (como cafés tranquilos, centros culturais, livrarias e parques urbanos).

A solução elimina a sobrecarga cognitiva e as barreiras logísticas de marcar encontros:

- **Interpretação de Intenção e "Vibe":** Modelos de Linguagem (LLMs) interpretam solicitações em linguagem natural livre (ex.: *"quero um café calmo para conversar sobre livros"*), extraindo preferências, necessidades psicossociais e restrições de horários e acessibilidade sem a exigência de formulários cansativos.
- **Recomendação e Ranqueamento Híbrido:** Combina busca vetorial semântica (`pgvector`) com filtros geoespaciais em tempo real (`PostGIS`), aplicando uma fórmula de score ponderado por afinidade temática, proximidade física, perfil dos usuários e reputação comunitária ($0.4 \times \text{Google} + 0.6 \times \text{Usuários do App}$).
- **Segurança e Espaços Públicos Verificados:** Todas as recomendações são ancoradas em dados reais de estabelecimentos ativos e verificados (OpenStreetMap / PostGIS), com guardrails ativos de abstenção correta para consultas inviáveis ou fora do escopo social.

---

## 🚀 Entregável da Semana 3: Comparação Experimental LLM x RAG

Na **Semana 3**, realizamos um estudo comparativo rigoroso e reprodutível avaliando **4 arquiteturas distintas** sobre o conjunto oficial de 18 casos de teste com personas de Brasília:

1. **Teste 1: LLM Pura (Zero-Shot / Sem RAG):** Alucinação severa no DF (apenas 37.5% de existência de locais) e 0.0% de abstenção.
2. **Teste 2: RAG Sem LLM (Retrieval-Only):** 100% de fundamentação e latência de 22 ms, mas resposta fria e 50.0% de falha em guardrails semânticos (frete).
3. **Teste 3: RAG Clássico (Naive RAG):** Fluência textual, mas sofre com alucinação de atributos e 0.0% de abstenção em pedidos absurdos.
4. **Teste 4: RAG Modular Avançado (Bubbles):** Combina NLU estruturada, guardrails precoces, PostGIS/pgvector, score multi-fatorial calibrado, LLM empática e validador pós-geração.

### Tabela Resumo dos 4 Testes

| Configuração Arquitetural | Precision@3 | Locais Existem | Fundamentação | Abstenção Correta | Latência Média | Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **1. LLM Pura (Zero-Shot)** | 16.7% | 37.5% | 0.0% | 0.0% | 1.463 ms | Reprovado |
| **2. RAG Sem LLM (Retrieval Puro)** | 64.6% | 100.0% | 100.0% | 50.0% | **22 ms** | Incompleto |
| **3. RAG Clássico (Naive RAG)** | 79.2%* | 100.0% | 100.0%* | 0.0% | 1.258 ms | Inseguro |
| **4A. RAG Bubbles (Semana 2)** | 64.6% | 100.0% | 100.0% | 100.0% | 686 ms | Homologado |
| **4B. RAG Bubbles Otimizado (Semana 3) ★** | **75.0%** | **100.0%** | **100.0%** | **100.0%** | **693 ms** | **ESCOLHIDO** |
| **4C. RAG Bubbles Refinado (Semana 3)** | **77.1%** | **100.0%** | **100.0%** | **100.0%** | 693 ms | Homologado |

> **Ganho de Métricas na Semana 3:** A calibração dos pesos ($w_v=0.45, w_d=0.15, w_r=0.15, w_c=0.25$) elevou a **Precision@3 de 64.6% para 75.0% (+10.4 p.p.)** e até **77.1% (+12.5 p.p.)**, com **100% de locais que existem e 100% de abstenção correta**.

### Documentos e Links Rápidos
- 📄 **Relatório Técnico Completo da Semana 3:** [`docs/relatorio/relatorio_semana3_llm_x_rag.md`](file:///Users/aluno2/Documents/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/relatorio/relatorio_semana3_llm_x_rag.md)
- 📊 **Dashboard Interativo da Semana 3:** [`docs/avaliacao/dashboard_semana3.html`](file:///Users/aluno2/Documents/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/avaliacao/dashboard_semana3.html)
- 💾 **Dados Brutos do Benchmark (JSON):** [`docs/avaliacao/resultados_semana3_llm_rag.json`](file:///Users/aluno2/Documents/Bubblues---Challenge-2---Resid-ncia-de-IA/docs/avaliacao/resultados_semana3_llm_rag.json)
- ⚙️ **Script do Benchmark Automatizado:** [`scripts/benchmark_semana3_llm_rag.js`](file:///Users/aluno2/Documents/Bubblues---Challenge-2---Resid-ncia-de-IA/scripts/benchmark_semana3_llm_rag.js)
- 📈 **Script de Plotagem de Gráficos:** [`scripts/plot_metricas_semana3.py`](file:///Users/aluno2/Documents/Bubblues---Challenge-2---Resid-ncia-de-IA/scripts/plot_metricas_semana3.py)

```bash
# Como rodar os testes da Semana 3
npm run test:semana3
npm run plot:semana3
```

---

## 👥 Integrantes da Equipe

| Foto | Nome | GitHub |
| :---: | :--- | :--- |
| <img src="https://github.com/Marjoriemitzi.png" width="60" height="60" style="border-radius: 50%;" alt="Marjorie Mitzi" /> | **Marjorie Mitzi** | [@Marjoriemitzi](https://github.com/Marjoriemitzi) |
| <img src="https://github.com/Ruan-Carvalho.png" width="60" height="60" style="border-radius: 50%;" alt="Ruan Carvalho" /> | **Ruan Carvalho** | [@Ruan-Carvalho](https://github.com/Ruan-Carvalho) |
| <img src="https://github.com/sammiess2.png" width="60" height="60" style="border-radius: 50%;" alt="Samara" /> | **Samara** | [@sammiess2](https://github.com/sammiess2) |
| <img src="https://github.com/yanrdgs-dev.png" width="60" height="60" style="border-radius: 50%;" alt="Yan Santos" /> | **Yan Santos** | [@yanrdgs-dev](https://github.com/yanrdgs-dev) |
| <img src="https://github.com/wincsSI.png" width="60" height="60" style="border-radius: 50%;" alt="Wingrid Silva" /> | **Wingrid Silva** | [@wincsSI](https://github.com/wincsSI) |
