# Relatório: banco, busca híbrida e registro de evidência

**Branch:** `feat/busca`, criada a partir de `feat/pipeline-dados`
**Data da execução:** 09/11/2026

## 1. Resumo

O critério de pronto foi atendido: **a busca devolve o top-k com a decomposição do score, e o registro de evidência sai completo**, sobre a base real de 4.526 lugares do Distrito Federal.

| Verificação | Resultado |
|---|---|
| Imagem Docker com PostgreSQL 16, PostGIS 3.7 e pgvector 0.8.1 | Construída e saudável |
| Testes automatizados (`pytest`) | **36 de 36 aprovados**, nenhum pulado |
| Pipeline real: registros originais / lugares curados / unificados | 4.533 / 4.526 / 7 |
| Lugares com embedding de 768 dimensões | 4.526 de 4.526 |
| Integridade na base inteira: maior erro entre soma das contribuições e total | 0 |
| Integridade na base inteira: faixa dos valores dos fatores | 0 a 1 |

Os resultados têm limitações importantes de dados, descritas na seção 6.

## 2. O que já existia

Antes de começar, as branches `main` e `feat/pipeline-dados` foram comparadas. A `feat/pipeline-dados` já parte da `main`, então serviu de base.

| Item da tarefa | Situação encontrada |
|---|---|
| PostGIS e tabela `places` | Já existiam, com instalação manual pelo pgAdmin |
| Imagem Docker e pgvector | Não existiam |
| Coluna de vetor | Não existia |
| Etiquetas OSM | Eram coletadas, mas descartadas em `transform.py` |
| Busca por raio e categoria | Existia em `search_places.py`, sem score nem evidência |
| Pesos do score | Definidos na documentação e em `scripts/eval_benchmark.js` |

## 3. O que foi feito

### 3.1. Banco

- `data-pipeline/db/Dockerfile` e `data-pipeline/docker-compose.yml` sobem o banco com as duas extensões.
- `data-pipeline/db/schema.sql` cria o esquema e pode ser reexecutado, inclusive em bancos antigos.
- Colunas adicionadas a `places`: `tags`, `embedding vector(768)`, `nota_google` e `nota_app`.
- Tabela nova `evidencias_busca`, com um registro por consulta. Ela não tem chave estrangeira para `places`, porque a curadoria recria essa tabela e a evidência precisa continuar existindo.

### 3.2. Pipeline

`transform.py`, `load.py` e `curadoria.sql` agora preservam as etiquetas OSM, necessárias para a evidência e para o fator de compatibilidade.

`gerar_embeddings.py` gera os vetores com o modelo local `paraphrase-multilingual-mpnet-base-v2`, a partir de nome, categoria e etiquetas descritivas.

### 3.3. Função de busca (`busca.py` e `score.py`)

A função `buscar()` segue estes passos:

1. Valida os parâmetros, recusando, por exemplo, vetor nulo ou dimensão errada.
2. Filtra por raio (`ST_DWithin`), tipo (`categoria`) e existência de embedding.
3. Calcula o cosseno com pgvector e a distância com PostGIS.
4. Se houver menos de k candidatos, dobra o raio **uma única vez**.
5. Calcula e ordena o score, valida a evidência e a grava.

| Fator | Peso | Valor (entre 0 e 1) |
|---|---:|---|
| `similaridade` | 0,40 | Cosseno entre consulta e lugar; negativos viram 0 |
| `distancia` | 0,25 | `1 / (1 + km / 5)`, mesma curva do benchmark |
| `reputacao` | 0,15 | `(0,4 × Google + 0,6 × App) / 5` |
| `compatibilidade` | 0,20 | Média das etiquetas pedidas: atende = 1, contraria = 0, ausente = 0,5 |

- **Fator sem dado:** vale 0,5 e aparece com `"origem": "sem_dado"`.
- **Desempate:** maior score, depois menor distância, depois `osm_type` e `osm_id`. O `place_id` não é usado porque muda a cada curadoria.
- **Status:** `completo`, `parcial` ou `sem_resultado`.

### 3.4. Decisões tomadas durante a tarefa

| Decisão | Escolha | Motivo |
|---|---|---|
| Dimensão do vetor | 768, modelo local | Sem custo de API e adequado ao português |
| Reputação sem dado | Mantém os 4 fatores, com valor neutro marcado | Preserva a fórmula documentada sem inventar notas |
| Embeddings reais | Incluídos na tarefa | Sem eles, a busca não devolve nada na base real |
| Índice HNSW | Não criado | O filtro de raio vem antes e a base é pequena; o cálculo exato não perde resultados |

## 4. Como foi testado

1. **Testes sem banco** (`tests/test_score.py`, 18 testes): verificam a soma das contribuições e a faixa dos valores em combinações de entradas extremas, e confirmam que 12 tipos de corrupção do registro são recusados.
2. **Testes com banco real** (`tests/test_busca.py`, 18 testes): cada um usa um schema temporário e cobre raio, tipo, cosseno, desempate, ampliação única, ausência de resultado e gravação da evidência.
3. **Pipeline de ponta a ponta:** coleta no OpenStreetMap, transformação, carga, curadoria e geração de embeddings, que levou cerca de 23 minutos em CPU de 4 núcleos.
4. **Buscas reais:** cinco cenários, cada um executado duas vezes para confirmar resultados idênticos e conferir o registro gravado.
5. **Integridade na base inteira:** uma consulta pontuou todos os 4.526 lugares.

**Erro encontrado nos testes:** a primeira versão do `Dockerfile` partia de `postgis/postgis:16-3.5`, baseada em Debian bullseye, cujo repositório do PostgreSQL foi descontinuado. A base passou a ser `pgvector/pgvector:0.8.1-pg16-bookworm`, com o PostGIS instalado sobre ela.

## 5. Resultados das buscas reais

Ponto de origem: Asa Sul (-15,8200; -47,9100), exceto no cenário sem resultado. Cada busca levou entre 10 e 58 ms, sem contar a geração do vetor da consulta.

| Cenário | Raio pedido → final | Status | Candidatos | Primeiro resultado | Score |
|---|---|---|---:|---|---:|
| Café calmo e acessível | 1,5 km | completo | 12 | Uai Bezinha! | 0,6487 |
| Parque para caminhar | 3 km | completo | 26 | Praça dos Cogumelos | 0,6645 |
| Restaurante japonês | 2 km | completo | 106 | OMA Japanese Experience | 0,7775 |
| Cinema alternativo | 1 km → 2 km | parcial | 1 | Cine Brasília | 0,6099 |
| Zoológico em área sem nenhum | 0,5 km → 1 km | sem_resultado | 0 | Nenhum | Não se aplica |

### Decomposição do cenário "restaurante japonês"

| # | Local | Distância | Similaridade | Distância | Reputação | Compatibilidade | Total |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | OMA Japanese Experience | 943 m | 0,292 | 0,210 | 0,075 | 0,200 | 0,7775 |
| 2 | New Koto | 820 m | 0,280 | 0,215 | 0,075 | 0,200 | 0,7699 |
| 3 | Koji | 1.587 m | 0,265 | 0,190 | 0,075 | 0,200 | 0,7296 |

As colunas de fatores mostram a contribuição de cada um (valor × peso).

### Exemplo de registro de evidência

Registro real, com valores arredondados para 4 casas e somente o primeiro resultado:

```json
{
  "consulta_id": "e790f212-3765-4c00-a748-340fd4e31aee",
  "criada_em": "2026-11-09T13:04:23.237465+00:00",
  "consulta": {
    "texto": "restaurante japonês com sushi para confraternizar",
    "latitude": -15.82,
    "longitude": -47.91,
    "tipos": ["restaurant"],
    "k": 3,
    "etiquetas_desejadas": { "cuisine": "japanese" }
  },
  "raio": { "solicitado_m": 2000, "final_m": 2000, "ampliado": false },
  "status": "completo",
  "total_candidatos": 106,
  "pesos": { "similaridade": 0.4, "distancia": 0.25, "reputacao": 0.15, "compatibilidade": 0.2 },
  "resultados": [
    {
      "posicao": 1,
      "local": {
        "place_id": 656,
        "nome": "OMA Japanese Experience",
        "categoria": "restaurant",
        "latitude": -15.8276,
        "longitude": -47.906,
        "distancia_m": 942.562
      },
      "osm_url": "https://www.openstreetmap.org/node/2691239353",
      "etiquetas_usadas": { "amenity": "restaurant", "cuisine": "japanese;sushi" },
      "fatores": [
        { "nome": "similaridade", "valor": 0.7303, "peso": 0.4, "contribuicao": 0.2921, "origem": "pgvector_cosseno" },
        { "nome": "distancia", "valor": 0.8414, "peso": 0.25, "contribuicao": 0.2103, "origem": "postgis" },
        { "nome": "reputacao", "valor": 0.5, "peso": 0.15, "contribuicao": 0.075, "origem": "sem_dado" },
        { "nome": "compatibilidade", "valor": 1.0, "peso": 0.2, "contribuicao": 0.2, "origem": "etiquetas_osm" }
      ],
      "score_total": 0.7775
    }
  ]
}
```

## 6. Limitações

- **A reputação ainda não influencia o ranking.** Nenhum dos 4.526 lugares tem nota, então o fator soma 0,075 para todos.
- **Acessibilidade quase não tem dado.** Só 206 lugares (4,6%) têm a etiqueta `wheelchair`, e 1.046 (23,1%) têm `cuisine`. No cenário "café acessível", nenhum dos três primeiros tem essa etiqueta, portanto **a acessibilidade deles não está confirmada**.
- **Etiqueta ausente não elimina um lugar.** Isso evita descartar locais só porque o OSM é incompleto, mas uma restrição obrigatória, como acessibilidade para uma pessoa com mobilidade reduzida, ainda precisa de um filtro próprio.
- **A qualidade do ranking real não foi medida.** As métricas do relatório final (Precision@3 de 64,6%) vêm de `scripts/eval_benchmark.js`, que usa 25 locais escritos à mão e vetores de 16 dimensões. Esse benchmark não usa esta busca nem a base real.

## 7. Como reproduzir

Em `data-pipeline/`, com o `.env` preenchido:

```bash
docker compose up -d --build
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt -r requirements-embeddings.txt
.venv/bin/pytest

.venv/bin/python extract.py
.venv/bin/python transform.py
.venv/bin/python load.py
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < curadoria.sql
.venv/bin/python gerar_embeddings.py

.venv/bin/python busca.py "restaurante japonês com sushi" --lat -15.82 --lon -47.91 --raio 2000 --tipo restaurant -k 3 --etiqueta cuisine=japanese
```

## 8. Próximos passos sugeridos

1. Ligar o benchmark à busca real, para medir a qualidade do ranking com a base do OSM.
2. Definir a fonte das notas do Google e do app, para ativar o fator de reputação.
3. Decidir quais restrições devem ser filtros obrigatórios.
4. Avaliar a remoção de `search_places.py`, que foi substituído por `busca.py`.
