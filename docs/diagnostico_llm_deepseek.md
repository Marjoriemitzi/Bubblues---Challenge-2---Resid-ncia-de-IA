# Diagnóstico do LLM (DeepSeek) para o agente de Retrieval

Gerado por `scripts/diagnostico_llm.py` em 19/11/2026: um loop **real** de tool use (banco PostgreSQL e embedding reais)
com as ferramentas do Retrieval (`resolver_regiao`, `listar_categorias`, `buscar_lugares`, `validar_candidatos`), pedido
"café calmo na Asa Sul, acessível, 5 km". Cada configuração fez 4 chamadas de ferramenta, sem nenhum erro de tool.

## Modelos que a chave enxerga

`deepseek-flash` e `deepseek-v4-pro`. O `deepseek-chat` (usado pelo NLU nas primeiras rodadas) ainda responde, mas é nome legado.
Nos modelos novos o **thinking vem ligado por padrão**.

## Resultados

| Configuração | Tempo | Tokens (prompt / completion / raciocínio) | Observação |
|---|---:|---|---|
| `deepseek-chat` (legado) | 8,2 s | 8.524 / 313 / 0 | funciona |
| `deepseek-flash`, sem thinking | 9,7 s* | 8.528 / 365 / 0 | |
| **`deepseek-flash` + `strict` (beta)** | **4,7 s** | 8.541 / 361 / 0 | mais rápido; schemas estritos aceitos |
| `deepseek-flash` + thinking | 7,2 s | 8.971 / **777** / 368 | exige devolver `reasoning_content` |
| `deepseek-v4-pro`, sem thinking | **14,7 s** | 8.650 / 341 / 0 | mais lento, sem ganho nesta tarefa |

\* o primeiro run inclui o aquecimento da conexão. Tempos de uma execução cada: servem para ordem de grandeza, não como benchmark.

## O que ficou provado

- **Chamadas em paralelo:** o modelo pediu `resolver_regiao` e `listar_categorias` no mesmo passo; o loop trata várias chamadas por mensagem.
- **`reasoning_content` é obrigatório no modo thinking com tools:** devolver o histórico sem ele deu **HTTP 400**
  (como a documentação afirma). `mensagem_para_dict` preserva o campo.
- **Cache de contexto:** 60 a 85% do prompt veio do cache (`prompt_cache_hit_tokens`), o que barateia o loop (o schema das tools se repete).
- **Os filtros obrigatórios não dependem do modelo:** em todas as execuções o contexto terminou com `wheelchair=yes` e ruído `baixo`,
  aplicados dentro da tool, mesmo o modelo nunca os tendo passado como argumento.
- **No thinking o modelo notou algo que o pipeline determinístico esconde:** que a busca ampliou o raio sozinha ("4 dos aprovados
  estão fora do raio desejado"). O prompt do agente (Fase D) deve dizer: `k = 3` e o que fazer quando `raio_ampliado = true`.

## Recomendação para a Fase D

1. **Começar com `deepseek-flash`, `reasoning_effort="none"` e `DEEPSEEK_STRICT=1`**: o mais rápido e o mais barato, e sem erros de tool.
2. Avaliar thinking só na Fase F, contra o baseline (custa ~2x tokens de saída e mais latência; a vantagem observada foi de consciência
   sobre o raio, não de qualidade de busca).
3. `deepseek-v4-pro` não se justifica para este loop.
4. O padrão do cliente é `deepseek-flash` com thinking desligado. Com isso o NLU mantém a **ação idêntica nos 18 pedidos** de teste e
   14/18 com os mesmos campos-chave (TC-01 `elder_friendly` true→false; TC-03/06/10 trocam uma categoria). O dataset
   `bubbles-retrieval-osm-v1` segue congelado com as saídas do `deepseek-chat`.

## Limites do diagnóstico

Uma execução por configuração; um único pedido; o modelo chamou `buscar_lugares` com `k=8`. Não mede a qualidade do resultado
(isso é a Fase F), só que o loop de tool use funciona e quanto custa.
