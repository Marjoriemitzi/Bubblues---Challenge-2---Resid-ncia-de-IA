# Fase F: avaliação formal do Retrieval (pipeline determinístico vs agente LLM)

- **Dataset:** `bubbles-retrieval-osm-v1` (18 itens; 15 a recomendar entram nas métricas). **Gabarito:** v1.3 (176 rótulos), o mesmo para todos os runs.
- **Execução:** pipeline 1 run (determinístico: deu o mesmo resultado em todas as execuções); cada configuração do agente **3 repetições**, agente **cru** (`fallback=None`), `deepseek-flash`.
  Runs no Langfuse com nome `f-<config>-r<k>`. Reproduzir: `python scripts/avaliacao/rodar_matriz.py <config> --repeticoes 3` e `python scripts/avaliacao/analisar_matriz.py`.
- Os 4 blocos do agente rodaram **em paralelo** (para caber no tempo): a latência medida é aproximada; qualidade e tokens não são afetados.

## Resultado

| Configuração | Runs | P@3 (média ± dp) | faixa P@3 | nDCG@3 (média ± dp) | faixa nDCG@3 | Cobertura | Latência | Tokens (prompt/saída) | Casos vs pipeline (V/E/D)† | Sem entrega |
|---|---:|---|---|---|---|---:|---:|---|---|---:|
| pipeline (determinístico) | 1 | 0.756 ± 0.000 | 0.76–0.76 | 0.621 ± 0.000 | 0.62–0.62 | 1.00 | 0.1 s | 0 / 0 | - | 0.0 |
| agente base (flash, sem thinking) | 3 | 0.741 ± 0.026 | 0.71–0.76 | 0.674 ± 0.011 | 0.66–0.68 | 1.00 | 4.1 s | 9100 / 358 | 4/9/2 | 0.0 |
| agente + strict | 3 | 0.785 ± 0.034 | 0.76–0.82 | 0.697 ± 0.022 | 0.67–0.72 | 1.00 | 4.3 s | 9667 / 397 | 4/9/2 | 0.0 |
| agente + thinking | 3 | 0.741 ± 0.078 | 0.67–0.82 | 0.640 ± 0.054 | 0.58–0.69 | 1.00 | 6.9 s | 13892 / 796 | 4/6/5 | 0.7 |
| agente + prompt v2 (otimista*) | 3 | 0.741 ± 0.013 | 0.73–0.76 | 0.672 ± 0.012 | 0.66–0.68 | 1.00 | 3.9 s | 9027 / 347 | 3/10/2 | 0.0 |

† Casos em que a média das repetições do agente ficou acima / dentro de ±0,05 / abaixo do pipeline em nDCG@3. \* O prompt v2 foi escrito depois de ver as falhas do v1 **nestes mesmos casos**: o resultado dele é otimista.

## O que isso diz

1. **O agente fica no mesmo patamar do pipeline em P@3 e um pouco acima em nDCG@3, e quase todo o ganho vem de um caso.** O TC-08 (cinema alternativo com cafeteria) passa de 0,00 para 0,83–1,00: o pipeline devolve cafés, o agente acha o CineCultura.
   **Sem o TC-08**, as médias ficam assim (P@3 / nDCG@3):

| Configuração | P@3 | nDCG@3 |
|---|---:|---:|
| pipeline (determinístico) | 0.810 | 0.665 |
| agente base (flash, sem thinking) | 0.762 | 0.659 |
| agente + strict | 0.794 | 0.675 |
| agente + thinking | 0.770 | 0.627 |
| agente + prompt v2 (otimista*) | 0.754 | 0.653 |

   Nos outros 14 casos o **pipeline é igual ou um pouco melhor em P@3** (0,81 contra 0,75 a 0,79) e equivalente em nDCG@3 (0,67 contra 0,63 a 0,68).
2. **O ganho de nDCG é consistente entre repetições** (todas as 9 repetições de base, strict e v2 ficam acima do pipeline), mas é **modesto** e depende de um caso e de rótulos de um anotador único.
3. **`strict` foi a melhor configuração do agente** (P@3 0,785 ± 0,034; nDCG 0,697 ± 0,022), mas a diferença para o agente base (0,741 / 0,674) está **dentro do ruído** de 3 repetições. Usa o endpoint beta.
4. **Thinking é pior e mais caro:** ~1,5x os tokens de prompt e ~2,2x os de saída, mais latência, maior variância (P@3 de 0,67 a 0,82) e **falhou em 2 casos de uma repetição** (`AgenteSemDecisao`). Não vale.
5. **O prompt v2 não melhorou o agente** (0,741 / 0,672 contra 0,741 / 0,674), **mesmo sendo otimista**. Mandar "conferir horário e culinária" não trouxe ganho mensurável. **Não adotar.**
6. **Custo:** ~9.100 tokens de prompt e ~360 de saída por pedido (60 a 85% do prompt vem do cache), ~4 s de latência contra 0,1 s do pipeline. Sem preço do provedor não estimo custo em reais.

## Por caso (nDCG@3, média das repetições)

| Caso | pipeline | flash | flash-strict | flash-thinking | flash-prompt2 |
|---|---:|---:|---:|---:|---:|
| TC-01 | 0.82 | 0.88 | 0.88 | 0.82 | 0.88 |
| TC-02 | 0.52 | 0.34 | 0.44 | 0.35 | 0.48 |
| TC-03 | 0.88 | 0.85 | 0.86 | 0.80 | 0.87 |
| TC-04 | 0.52 | 0.52 | 0.52 | 0.52 | 0.52 |
| TC-05 | 1.00 | 1.00 | 1.00 | 0.82 | 0.94 |
| TC-06 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| TC-07 | 0.55 | 0.57 | 0.57 | 0.80 | 0.57 |
| TC-08 | 0.00 | 0.88 | 1.00 | 0.83 | 0.94 |
| TC-09 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| TC-10 | 0.24 | 0.33 | 0.33 | 0.33 | 0.24 |
| TC-11 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| TC-12 | 0.27 | 0.37 | 0.42 | 0.44 | 0.37 |
| TC-13 | 1.00 | 0.84 | 1.00 | 1.00 | 1.00 |
| TC-14 | 0.52 | 0.52 | 0.52 | 0.30 | 0.52 |
| TC-15 | 1.00 | 1.00 | 0.92 | 0.59 | 0.77 |

O agente perde de forma consistente só no **TC-02** (jogos de tabuleiro no final de tarde; o pipeline 0,52 contra 0,34 a 0,48). Perdas menores e pontuais: TC-13 no agente base (0,84) e TC-15/TC-14/TC-05 no thinking (inclui as 2 falhas).
Ganha no TC-08 (grande), TC-10 e TC-12 (pequenos). Nada mudou nos casos que o OSM não consegue responder (TC-06 feirinha noturna: 0,00 em todos).

## Recomendação

- **Manter `RETRIEVAL_MODE=deterministic` como padrão por ora.** Os dados não justificam trocar: no conjunto, o agente é equivalente fora de um caso, custa ~4 s e ~9,5 mil tokens por pedido, e ainda tem falhas que dependem do fallback.
- **Usar `llm` (com fallback) onde o pedido combina tipos de lugar ou conceitos que o embedding não compõe** (como "cinema com cafeteria integrada"). Uma ideia a testar: um roteador que só chama o agente quando os candidatos do pipeline são fracos ou o pedido tem mais de uma categoria.
- **Não adotar thinking nem o prompt v2.** `strict` é opcional (ganho dentro do ruído).

## Limitações (leia antes de citar os números)

- **n = 15 casos** e 3 repetições: diferenças de 0,03 a 0,05 não são distinguíveis de ruído.
- **Rótulos de anotador único (IA), não cego**, em sua maioria de confiança baixa, com a convenção "1 = parcial ou não confirmado". Vale revisão humana, sobretudo nos casos que decidem a comparação (TC-08, TC-02).
- **Viés de pooling:** o gabarito começou com os candidatos do pipeline; os lugares que só os agentes entregaram (21) foram rotulados depois, pelo mesmo anotador. Isso é inevitável com cobertura total, mas os rótulos de "1 = não confirmado" tendem a ser generosos com esses lugares.
- **O prompt v2 foi escrito vendo estes casos** (sem conjunto de validação separado). Num conjunto novo o resultado dele tende a ser pior, não melhor.
- **Sem fallback:** o agente rodou cru; com fallback ligado, as falhas do thinking e qualquer `AgenteSemDecisao` seriam resgatadas pelo pipeline.
- A latência veio de 4 processos em paralelo e de uma API compartilhada.
