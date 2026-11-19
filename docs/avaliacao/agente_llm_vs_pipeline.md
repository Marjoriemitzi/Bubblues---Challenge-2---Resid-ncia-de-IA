# Agente LLM (DeepSeek) vs pipeline determinístico: primeira medição

- **Runs no Langfuse:** pipeline `retrieval-pipeline-gate-588ecd5` e agente `retrieval-agente-llm-79ffef9` (agente **cru**, sem fallback),
  mesmo dataset `bubbles-retrieval-osm-v1`. Agente: https://us.cloud.langfuse.com/project/cmwdi3aqt016pad0kkhqyj0qp/experiments/results?baseline=4b3e57b7858782ba
- **Configuração do agente:** `deepseek-flash`, thinking desligado, sem `strict`, até 6 passos, 4 buscas, 60 s.
- **Comparação justa:** os dois runs recalculados com o **mesmo gabarito v1.1** (`scripts/avaliacao/recalcular_scores.py`), já que o agente entregou
  3 lugares fora do pool original e eles foram rotulados.

## Resultado (15 casos a recomendar)

| | Pipeline | Agente LLM |
|---|---:|---:|
| P@3 | **0,756** | 0,689 |
| nDCG@3 | 0,628 | **0,639** |
| Violações de restrição entregues | 0 | 0 |
| Erros de agente / fallbacks | 0 / - | 0 / 0 |
| Aprovado na 1ª rodada | 100% | 100% |
| Latência média | 0,06 s | **14 s** (típica 4 a 6 s; 3 picos de 20/65/100 s) |
| Tokens por pedido (prompt / saída) | - | ~9.300 / ~360 |
| Passos de LLM por pedido | - | 3,7 |

**Leitura honesta: empate dentro do ruído.** Com n = 15, rótulos de anotador único (IA) e a convenção "1 = não confirmado", a diferença de 0,07 em P@3 e de
0,01 em nDCG@3 não permite dizer que um é melhor.

## Onde o agente ajudou (os casos que o pipeline errava por não entender o pedido)

- **TC-08 (cinema alternativo):** o pipeline entregava 3 cafés (nDCG 0); o agente colocou o **CineCultura Liberty Mall em 1º** (nDCG 1,00).
- **TC-10 (parque pet):** P@3 0,33 → 0,67: saiu de playgrounds para parque/praça.
- **TC-01:** nDCG 0,82 → 0,88; **TC-12:** 0,27 → 0,36. No pedido de restaurante vegano rodado à parte, o agente entregou Buriti Zen Vegano, Apetit
  Natural e A Tribo, e deixou o Churrasgril de fora.

## Onde o agente piorou (e por quê)

- **TC-15 ("aberto até às 22h"): P@3 1,00 → 0,33.** Entregou Entre Eixos (OSM abre 9h-17h) e Melbourne (fecha 17h30), embora `opening_hours` estivesse
  nas tags que a tool devolve. **Duas lacunas:** o modelo não comparou o horário com o pedido, **e o validador também não barra** ("aberto até Xh" só é
  verificado para a madrugada). Atenção: o pipeline pode ter o mesmo problema, mas seus 3 lugares não têm horário no OSM, então ficam em "não confirmado" (grau 1);
  a diferença nesse caso é em parte **assimetria de evidência**, não só de qualidade.
- **TC-13 (sushi):** incluiu o Ashram Zen Lounge (cozinha indiana) em 3º: P@3 1,00 → 0,67.
- **TC-02 (jogos, final de tarde):** incluiu o Melbourne, que fecha 17h30.
- Nos outros casos empatou (TC-04, 05, 06, 07, 09, 11, 14) ou variou pouco.

## Custo e latência

O agente é ~230x mais lento que o pipeline (14 s vs 0,06 s em média; ~5 s no caso típico) e consome ~9,6 mil tokens por pedido, 60 a 85% vindos do cache.
Os 3 picos (20/65/100 s) tinham a mesma estrutura de passos dos itens rápidos: foram lentidão da API, não do agente. **Isso expôs um bug no cliente:** o prazo total
só era checado entre tentativas, então uma requisição lenta podia ultrapassar os 60 s. Corrigido: cada requisição recebe `min(timeout, tempo restante)`.

## O que falta para o agente valer a pena (hipóteses para a Fase F)

1. **Validador: verificar horário** ("até Xh", "às Xh", "domingo de manhã") contra `opening_hours`. Beneficia o pipeline e o agente.
2. **Prompt:** mandar o modelo conferir `tags.opening_hours` e `cuisine` dos candidatos antes de escolher.
3. **Reformular a consulta** quando os candidatos são semanticamente fracos (o agente só buscou 2x em 1 dos 15 casos).
4. Testar **thinking** e **strict** (diagnóstico: strict foi o mais rápido; thinking dobra os tokens de saída).
5. Medir com o **fallback ligado** (o agente nunca pior que o pipeline) e com mais casos/rótulos revisados por humano.

## Limitações

n = 15; um run por configuração (o modelo tem pequena variação mesmo com temperatura 0); rótulos de anotador único (IA, não cego), a maioria com confiança baixa;
latência sensível à API do provedor.

---

## Atualização: validador de horário (`orchestrator/horario.py`)

O validador passou a conferir o `opening_hours` do OSM contra o pedido ("até 22h", "às 03:30", faixas, turnos, dias da semana), **só reprovando com
evidência** (horário ausente, ilegível ou pedido sem horário nunca reprova). O parser entende 97% dos 466 horários reais da base; o resto é texto livre
ou formato exótico e vira "não confirmado".

Runs com o gabarito **v1.2** (164 rótulos; mais 6 lugares que o agente passou a entregar foram rotulados):

| Run | P@3 | nDCG@3 | cobertura |
|---|---:|---:|---:|
| pipeline, sem validador de horário | 0,756 | 0,628 | 1,00 |
| pipeline, com validador de horário | 0,756 | 0,628 | 1,00 |
| agente LLM, sem validador de horário | 0,689 | 0,639 | 1,00 |
| agente LLM, com validador de horário | **0,733** | **0,687** | 1,00 |

- **Pipeline: nada muda**, como esperado. Só ~10% dos lugares têm `opening_hours` no OSM e os candidatos do pipeline não tinham horário que violasse o pedido.
- **Agente: o TC-15 ("aberto até às 22h") foi de P@3 0,33 para 1,00.** O agente chamou `validar_candidatos`, viu que Entre Eixos (fecha 17h) e Melbourne
  (fecha 17h30) eram reprovados, e **buscou de novo por conta própria** (2 buscas, 2 validações, `reconsultas = 0` porque ele se corrigiu antes do gate).
- **Atenção ao que NÃO é efeito do validador:** TC-13 (+0,33), TC-10 (-0,33) e TC-02 variaram porque o LLM fez escolhas diferentes na repetição (a lista entregue mudou em 5
  dos 15 itens entre as duas execuções; 2 deles, TC-06 e TC-15, por causa do validador, e 3, TC-02, TC-10 e TC-13, sem relação com horário, mesmo com temperatura 0). **Um run por configuração não separa efeito de variância.** O ganho atribuível ao validador é o
  do TC-15 (+0,67 de P@3 em um caso = +0,044 na média); o resto da diferença é ruído.
- **TC-06 ("sábado à noite"):** o agente trocou os 3 food courts de prédios comerciais por praças (`park`). Rotulei as praças com grau 0 (não têm evidência de
  gastronomia nem feirinha, o núcleo do pedido). Sensível ao anotador: com a convenção "1 = parcial" o TC-06 viraria 1,00.
- **Bug achado na rodada:** o TC-06 levou 98,8 s mesmo com o prazo de 60 s. O DeepSeek manda linhas de keep-alive enquanto a requisição espera na fila, o que zera o timeout
  de leitura do SDK, então `timeout` não é prazo total. Agora a requisição roda numa thread daemon e o cliente **para de esperar** quando o prazo acaba
  (teste: uma resposta que demoraria 5 s é cortada em ~0,3 s). Esse run foi feito **antes** dessa correção.

## Próximos passos sugeridos (Fase F)

Repetir cada configuração (3 a 5 execuções) para medir a variância do agente antes de comparar; só então avaliar prompt, thinking/strict e fallback ligado.
