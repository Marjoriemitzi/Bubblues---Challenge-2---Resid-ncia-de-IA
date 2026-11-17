---
status: accepted
---

# Substituição de Clusterização em Lote por Recuperação Vetorial Dinâmica (RAG)

O desenho inicial do Bubbles previa agrupar Membros periodicamente em clusters fixos não-supervisionados (K-Means/HDBSCAN) antes de permitir recomendações e pareamentos. Decidimos remover completamente a clusterização em lote e adotar Recuperação Vetorial Dinâmica sob demanda combinando `pgvector` (similaridade de cosseno) e `PostGIS` (filtro geoespacial). Essa mudança elimina a condição de corrida (*race condition*) que bloqueava recém-cadastrados até a execução do próximo lote e permite respeitar a Intenção de Encontro momentânea do Membro sem prendê-lo a um rótulo comportamental estático.

## Considered Options

- **Clusterização em lote periódica (K-Means / HDBSCAN)**: Descartada por bloquear novos Membros no onboarding e ignorar variações de humor, turno e intenção a cada busca.
- **Filtro puramente categórico e geográfico (SQL tradicional)**: Descartado após o estudo de ablação demonstrar queda de 31,3 pontos percentuais na precisão (`Precision@3` caindo de 64,6% para 33,3%) ao desligar a similaridade semântica vetorial.
- **Recuperação Vetorial Híbrida em Tempo Real (`pgvector` + `PostGIS`)**: Escolhida por oferecer latência sub-segundo, zero bloqueio inicial e alta sensibilidade semântica à Vibe solicitada.

