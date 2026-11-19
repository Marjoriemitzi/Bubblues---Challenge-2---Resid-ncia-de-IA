# Baseline: Retrieval determinístico (grafo real) sobre `bubbles-retrieval-osm-v1`

- **Run no Langfuse:** `baseline-retrieval-deterministico-8c9b0df` (18 itens) · https://us.cloud.langfuse.com/project/cmwdi3aqt016pad0kkhqyj0qp/experiments/results?baseline=6527881416e51f02
- **Código medido:** commit `8c9b0df` no branch `feat/integracao-orquestrador`; Retrieval determinístico + Validation (MAX_RETRIES=2); embedding `paraphrase-multilingual-mpnet-base-v2`; política de acessibilidade: `wheelchair=yes` explícito.
- **Entrada:** o `structured_request` revisado do dataset (o NLU é avaliado à parte). **Saída medida:** o que o grafo *entrega* (evidências aprovadas pelo validador).

## Resultado agregado

| Métrica | Valor | n | Leitura |
|---|---:|---:|---|
| P@3 médio | **0.756** | 15 | fração do top-3 entregue com grau ≥ 1 (limite inferior: não rotulado = 0) |
| nDCG@3 médio | **0.628** | 15 | relevância graduada, normalizada pelo melhor top-3 conhecido |
| Ação correta | 1.00 | 18 | **trivial**: a ação vem do `structured_request` do dataset; só prova o roteamento |
| Violações de restrição entregues | 0 | 1 | só 1 item exige cadeira de rodas (TC-01); com `wheelchair=yes` explícito é 0 por construção |
| Entregas fora do raio | 0 | 18 | |
| Evidência completa | 1.00 | 15 | link OSM + integridade matemática |
| Aprovado na 1ª rodada | 1.00 | 15 | nenhuma reconsulta foi necessária |
| Cobertura de rótulos | 1.00 | 15 | **circular**: o pool de rotulagem veio deste mesmo pipeline |
| Latência média | 0.054 s | 18 | só o grafo (NLU/Communication são stubs); modelo já carregado |
| Erros de agente | 0 | 18 | |

## Por caso

| Caso | Ação | P@3 | nDCG@3 | Entregues (top-3) |
|---|---|---:|---:|---|
| TC-01 | recomendar | 1.00 | 0.82 | Tomilla Café, Saboretto Cafés Especiais, Caramella |
| TC-02 | recomendar | 1.00 | 0.52 | Beer Selection, Conic, Barulho |
| TC-03 | recomendar | 0.67 | 0.88 | Biblioteca Nacional de Brasília Leonel de Moura Brizola, Espaço Cultural Canteiro Central, Biblioteca Infantil |
| TC-04 | recomendar | 1.00 | 0.52 | Parque Ana Lídia, Praça Galeria, Praça dos artistas |
| TC-05 | recomendar | 1.00 | 1.00 | Quanto, Melbourne Café & Co., Caramella |
| TC-06 | recomendar | 0.00 | 0.00 | Edifício Financial Center Park, Lanchonete Pimenta de Cheiro, Bloco Q |
| TC-07 | recomendar | 0.67 | 0.65 | Apetit Natural, Churrasgril, A Tribo |
| TC-08 | recomendar | 0.00 | 0.00 | Gaudi Café, Art Café, Grande Café |
| TC-09 | recomendar | 1.00 | 1.00 | Espaço Cultural Canteiro Central, Cursos de Artes, Oficina de Arte |
| TC-10 | recomendar | 0.33 | 0.24 | Parque Ana Lídia, Parquinho de madeira, Parquinho Infantil |
| TC-11 | recomendar | 1.00 | 1.00 | Melbourne Café & Co., Starbucks, Grande Café |
| TC-12 | recomendar | 0.67 | 0.27 | Quadra de tênis, Praça das bicicletas, Quadra poliesportiva |
| TC-13 | recomendar | 1.00 | 1.00 | Sushi San, Sushi San, OMA Japanese Experience |
| TC-14 | recomendar | 1.00 | 0.52 | Área verde, Praça Galeria, Parque Ana Lídia |
| TC-15 | recomendar | 1.00 | 1.00 | Subway, Starbucks, Sabor do Café |
| TC-16 | clarificar | - | - | - |
| TC-17 | abster | - | - | - |
| TC-18 | abster | - | - | - |

## Como ler (limitações)

1. **Os rótulos são de um anotador único (IA), não cego**; a maioria tem confiança baixa e o grau 1 inclui 'não confirmado'. P@3 e nDCG são um **baseline relativo** para comparar versões, não uma medida absoluta de qualidade. Ver `gabarito_osm_v1.md`.
2. **A cobertura de rótulos 1,00 é circular.** O pool foi montado com o top-8 deste pipeline, então tudo o que ele entrega está rotulado. Uma variante (por exemplo, o agente LLM) vai entregar lugares *não rotulados*, que contam como grau 0: o P@3 dela será subestimado até esses lugares serem rotulados. Acompanhe `cobertura_rotulos` ao comparar.
3. **Onde o baseline falha** (P@3 baixo): TC-06 e TC-08 (0,00), TC-10 (0,33). Em TC-08 o pipeline entrega cafés para um pedido de cinema; em TC-10 entrega playgrounds para 'parque pet'. Os melhores lugares (CineCultura, Parque da Cidade, Deck Sul, Jardim Botânico) existem na base e foram rotulados como grau 2, mas **não são entregues**. nDCG baixo em TC-12 (0,27), TC-10 (0,24), TC-02/04/14 (0,52).
4. **Métricas pouco informativas hoje:** `acao_correta`, `violacao_restricao_entregue` (n=1) e `entrega_fora_do_raio` ficam em seus valores ideais. Passam a importar quando o NLU e o agente LLM entrarem no experimento.
5. O `place_id` não é estável entre curadorias; os rótulos e a comparação usam o id do OSM (`node/123`).

Para repetir: `python scripts/avaliacao/rodar_experimento.py --nome <nome-da-variante>` (o nome do run inclui o hash do commit).