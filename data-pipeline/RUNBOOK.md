# RUNBOOK — Pipeline de Dados de Brasília

## 1. Objetivo

Este documento apresenta as instruções para executar o pipeline de coleta, transformação, armazenamento, validação e curadoria de estabelecimentos e locais de interesse do Distrito Federal, utilizando dados do OpenStreetMap.

O objetivo é disponibilizar uma base organizada, limpa e georreferenciada para futuras consultas e recomendações de lugares.

## 2. Tecnologias utilizadas

- Python
- Requests
- Pandas
- Psycopg
- Shapely
- Python-dotenv
- PostgreSQL
- PostGIS
- OpenStreetMap — Overpass API

## 3. Estrutura do projeto

```text
pipeline do google/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── .venv/
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── extract.py
├── transform.py
├── load.py
├── search_places.py
├── busca.py
├── score.py
├── gerar_embeddings.py
├── docker-compose.yml
├── db/
├── tests/
├── validar_limite.py
├── curadoria.sql
└── RUNBOOK.md
```

### Diretórios e arquivos

- `data/raw/`: armazena os dados brutos coletados do OpenStreetMap.
- `data/processed/`: armazena os dados transformados e arquivos de validação.
- `.venv/`: ambiente virtual Python.
- `.env`: configurações locais de conexão com o banco de dados.
- `.env.example`: modelo de configuração para outros usuários.
- `.gitignore`: define arquivos e diretórios que não devem ser enviados ao Git.
- `requirements.txt`: lista as dependências necessárias para executar o projeto.
- `curadoria.sql`: realiza a curadoria e unificação dos registros.
- `RUNBOOK.md`: documenta os procedimentos de execução do pipeline.

**Importante:** o arquivo `.env` e o ambiente `.venv` não devem ser enviados ao GitHub.

## 4. Preparação do ambiente

É necessário ter Python, PostgreSQL e PostGIS instalados.

Abra o terminal na pasta principal do projeto.

### 4.1. Criar o ambiente virtual

```powershell
python -m venv .venv
```

### 4.2. Ativar o ambiente virtual

```powershell
.venv\Scripts\Activate.ps1
```

### 4.3. Instalar as dependências

Com o ambiente virtual ativado, execute:

```powershell
pip install -r requirements.txt
```

### 4.4. Bibliotecas utilizadas

- `requests`: realiza requisições à API do OpenStreetMap.
- `pandas`: manipula e transforma os dados coletados.
- `psycopg`: conecta o Python ao PostgreSQL.
- `shapely`: processa geometrias e auxilia na validação do limite geográfico.
- `python-dotenv`: carrega as configurações armazenadas no arquivo `.env`.

## 5. Configuração do banco de dados

O projeto utiliza PostgreSQL com as extensões PostGIS (dados geográficos) e pgvector (embeddings). O esquema completo está em `db/schema.sql`.

### 5.1. Subir o banco com Docker (recomendado)

Depois de criar o `.env` (seção 5.4), executar em `data-pipeline/`:

```bash
docker compose up -d --build
```

A imagem definida em `db/Dockerfile` traz PostGIS e pgvector. O `db/schema.sql` é aplicado automaticamente apenas na criação do volume. Para atualizar um volume já existente, executar:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/schema.sql
```

### 5.2. Banco instalado localmente

É necessário ter PostGIS e pgvector instalados no servidor. Criar o banco `pipeline_brasilia` e executar `db/schema.sql` no Query Tool do pgAdmin.

O script pode ser executado novamente com segurança e atualiza bancos criados por versões anteriores deste documento.

### 5.3. Tabelas

- `estabelecimentos`: registros originais da carga, incluindo as etiquetas OSM em `tags`.
- `places`: lugares após a curadoria, com identificadores de origem, `tags`, `embedding` (768 dimensões) e as notas opcionais `nota_google` e `nota_app`.
- `evidencias_busca`: um registro por consulta executada.

### 5.4. Configuração de conexão

Os scripts utilizam variáveis de ambiente armazenadas no arquivo `.env`.

O arquivo `.env.example` apresenta o modelo de configuração:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pipeline_brasilia
DB_USER=postgres
DB_PASSWORD=
```

Para executar o projeto, cada usuário deve criar seu próprio arquivo `.env`, preencher as configurações locais e informar a senha do PostgreSQL.

O arquivo `.env` verdadeiro não deve ser compartilhado nem enviado ao GitHub.

## 6. Execução do pipeline

Os scripts devem ser executados na seguinte ordem:

### 6.1. Extração

```powershell
python extract.py
```

Realiza a coleta de estabelecimentos e locais de interesse do Distrito Federal por meio da API Overpass do OpenStreetMap.

Os dados brutos são armazenados em `data/raw/`.

A coleta considera locais identificados por nome e pertencentes às categorias selecionadas no projeto.

### 6.2. Transformação

```powershell
python transform.py
```

Realiza a limpeza e padronização dos dados coletados.

Entre as operações estão:

- Padronização dos campos.
- Organização das categorias.
- Remoção de registros sem coordenadas.
- Remoção de duplicatas com o mesmo identificador OSM.
- Preparação dos dados para armazenamento.

O resultado é salvo em:

`data/processed/estabelecimentos.csv`

### 6.3. Carga

```powershell
python load.py
```

Carrega os dados transformados para a tabela `estabelecimentos` no PostgreSQL.

Durante a carga, as coordenadas são utilizadas para construir geometrias espaciais com PostGIS.

O script limpa os registros anteriores da tabela `estabelecimentos` antes de inserir os dados processados.

Essa operação permite executar novamente a carga sem acumular registros duplicados. A execução depende da existência do arquivo CSV gerado na etapa de transformação.

### 6.4. Curadoria dos dados

Após executar a carga dos dados na tabela `estabelecimentos`, executar o arquivo `curadoria.sql` no banco `pipeline_brasilia`, utilizando o Query Tool do pgAdmin.

O script realiza:

- Limpeza da tabela `places`.
- Agrupamento dos sete pares de registros revisados.
- Preservação dos identificadores originais.
- Inserção dos lugares curados na tabela `places`.

Resultado esperado:

- 4.526 lugares curados.
- 4.533 registros de origem preservados.
- 7 lugares resultantes da unificação de pares de registros.

### 6.5. Geração dos embeddings

A curadoria recria a tabela `places` e apaga os embeddings, portanto esta etapa deve ser repetida depois de cada curadoria.

```bash
pip install -r requirements-embeddings.txt
python gerar_embeddings.py
```

O modelo local `paraphrase-multilingual-mpnet-base-v2` (768 dimensões) é baixado na primeira execução. Somente lugares com embedding são considerados pela busca.

## 7. Validação geográfica

O projeto utiliza o limite geográfico do Distrito Federal obtido no OpenStreetMap.

O arquivo de limite é coletado durante a etapa de extração.

Para realizar a validação, executar:

```powershell
python validar_limite.py
```

O script utiliza a biblioteca Shapely para reconstruir e validar a geometria do limite.

A validação também verifica se os pontos coletados estão dentro do polígono reconstruído.

### Resultado da verificação realizada

- Registros analisados: 4.533.
- Registros dentro do limite reconstruído: 4.532.
- Registros fora do limite reconstruído: 1.

O registro identificado foi Praça das Árvores Vermelhas, em Santa Maria (DF).

Ele foi mantido na base enquanto a divergência do limite é investigada.

## 8. Curadoria dos dados

A tabela `places` representa a versão curada dos registros originais, mantendo a rastreabilidade dos elementos do OpenStreetMap.

### 8.1. Regra de deduplicação

Foi realizada uma análise de possíveis duplicatas considerando nome, categoria, distância e tipo de elemento do OpenStreetMap.

A distância de até 50 metros foi utilizada para identificar candidatos à revisão.

Para evitar unir locais diferentes, foram selecionados manualmente sete pares que atendiam aos seguintes critérios:

- Mesmo nome.
- Mesma categoria.
- Tipos OSM diferentes.
- Distância de até 3 metros.
- Análise individual dos registros.

Os sete pares foram unificados na tabela `places`.

Os identificadores originais foram preservados na coluna `osm_ids_origem`, permitindo rastrear a procedência dos dados.

### 8.2. Preservação da origem

A coluna `osm_ids_origem` armazena os identificadores dos elementos originais em formato JSONB.

A coluna `quantidade_origens` registra quantos elementos foram reunidos em cada lugar curado.

Dessa forma, mesmo após a unificação, é possível identificar os registros que deram origem a cada lugar.

## 9. Índice espacial

O arquivo `db/schema.sql` cria um índice espacial GiST sobre `geom::geography` na tabela `places`.

Esse índice auxilia na eficiência das consultas espaciais, especialmente na busca de lugares próximos a uma coordenada.

## 10. Consulta de lugares próximos

O arquivo `search_places.py` permite consultar lugares próximos de uma localização.

A função recebe:

- Latitude.
- Longitude.
- Raio de busca em metros.
- Categorias desejadas (opcional).

A consulta utiliza funções do PostGIS:

- `ST_DWithin`: identifica lugares dentro de determinado raio.
- `ST_Distance`: calcula a distância entre os pontos.
- `geography`: permite calcular distâncias considerando medidas em metros.

Os resultados são ordenados pela distância.

As consultas são realizadas sobre a tabela curada `places`, utilizando os registros após o processo de unificação.

### 10.1. Busca híbrida com evidência

O arquivo `busca.py` devolve o top-k com a decomposição do score e grava um registro em `evidencias_busca`.

```bash
python busca.py "café calmo e acessível" --lat -15.7942 --lon -47.8825 --raio 2000 --tipo cafe -k 3 --etiqueta wheelchair=yes
```

Em código, `buscar(conexao, latitude, longitude, embedding_consulta, raio_m, tipos, k, etiquetas_desejadas, texto_consulta)` recebe o vetor da consulta já calculado.

| Fator | Peso | Valor (entre 0 e 1) |
|---|---:|---|
| `similaridade` | 0,40 | Cosseno entre consulta e lugar; negativos viram 0 |
| `distancia` | 0,25 | `1 / (1 + km / 5)` |
| `reputacao` | 0,15 | `(0,4 × Google + 0,6 × App) / 5` |
| `compatibilidade` | 0,20 | Média das etiquetas pedidas: atende = 1, contraria = 0, ausente = 0,5 |

- **Sem dado:** o fator vale 0,5 e o registro traz `"origem": "sem_dado"`.
- **Ordenação:** maior score, depois menor distância, depois `osm_type` e `osm_id`.
- **Ampliação:** com menos de k candidatos, o raio é dobrado uma única vez. O registro informa `solicitado_m`, `final_m` e `ampliado`.
- **Status:** `completo`, `parcial` ou `sem_resultado`.

Cada resultado do registro contém o local, o link do OSM, as etiquetas usadas e os fatores com valor, peso, contribuição e origem.

### 10.2. Testes

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/test_score.py` não precisa de banco. `tests/test_busca.py` precisa do banco no ar, usa um schema temporário em cada teste e é pulado quando não há conexão.

## 11. Validação da base curada

Após a curadoria, foram realizadas consultas SQL para verificar a quantidade de registros e a preservação das origens.

### 11.1. Conferir a quantidade de lugares e origens

```sql
SELECT
    COUNT(*) AS total_places,
    SUM(quantidade_origens) AS total_origens,
    COUNT(*) FILTER (
        WHERE quantidade_origens > 1
    ) AS lugares_unificados
FROM places;
```

Resultado esperado:

- `total_places`: 4.526.
- `total_origens`: 4.533.
- `lugares_unificados`: 7.

### 11.2. Conferir a quantidade por categoria

```sql
SELECT
    categoria,
    COUNT(*) AS quantidade
FROM places
GROUP BY categoria
ORDER BY quantidade DESC;
```

### 11.3. Conferir os lugares unificados

```sql
SELECT
    nome,
    osm_id,
    osm_type,
    osm_ids_origem,
    quantidade_origens
FROM places
WHERE quantidade_origens > 1
ORDER BY nome;
```

### 11.4. Conferir os registros originais

```sql
SELECT COUNT(*) AS total_estabelecimentos
FROM estabelecimentos;
```

Resultado esperado: 4.533 registros.

## 12. Resultados finais

A coleta, transformação e curadoria apresentaram os seguintes resultados:

| Indicador | Resultado |
|---|---:|
| Registros originais | 4.533 |
| Registros na tabela curada | 4.526 |
| Lugares unificados | 7 |
| Categorias identificadas | 31 |
| Registros sem nome | 0 |
| Registros sem coordenadas | 0 |

A soma das origens preservadas na tabela `places` corresponde aos 4.533 registros da tabela original.

## 13. Observações importantes

- A fonte dos dados é o OpenStreetMap, por meio da API Overpass.
- A base contém locais identificados por nome.
- Os dados podem sofrer alterações conforme as atualizações do OpenStreetMap.
- As geometrias armazenadas nesta versão são pontos representativos dos locais, inclusive para elementos originalmente representados como áreas.
- A deduplicação foi realizada de maneira conservadora, com revisão individual dos sete pares selecionados.
- A tabela original `estabelecimentos` foi preservada para manter os registros anteriores à curadoria.
- A tabela `places` representa a versão curada da base.
- A execução da curadoria deve ocorrer após cada nova carga para atualizar a tabela `places`.

## 14. Resultado esperado

Ao seguir as etapas deste documento, é possível reproduzir a coleta, transformação e carga dos dados, além de executar a validação geográfica, a curadoria e as consultas espaciais.

A tabela `places` representa a versão organizada dos dados, mantendo a rastreabilidade dos elementos originais do OpenStreetMap.

O pipeline disponibiliza uma base georreferenciada e organizada para utilização nas próximas etapas do projeto de recomendação de lugares.
