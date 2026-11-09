# RUNBOOK — Pipeline de Dados de Brasília

## 1. Objetivo

Este documento descreve como executar o pipeline de coleta, transformação e armazenamento dos estabelecimentos e locais de interesse do Distrito Federal, utilizando dados do OpenStreetMap.

## 2. Tecnologias utilizadas

- Python
- Requests
- Pandas
- PostgreSQL
- PostGIS
- Shapely
- OpenStreetMap (Overpass API)

## 3. Estrutura do projeto


pipeline do google/
├── data/
│   ├── raw/
│   └── processed/
├── extract.py
├── transform.py
├── load.py
├── search_places.py
├── validar_limite.py
└── RUNBOOK.md


## 4. Ambiente

O projeto utiliza um ambiente virtual Python (`.venv`) para instalar e executar as dependências.
## 5. Instalação das dependências

Com o Python instalado, abra o terminal na pasta do projeto e execute:

### Criar o ambiente virtual

```bash
python -m venv .venv
```

### Ativar o ambiente virtual no Windows

```powershell
.venv\Scripts\Activate.ps1
```

### Instalar as bibliotecas

```bash
pip install requests pandas "psycopg[binary]" shapely
```

### Bibliotecas utilizadas

- `requests`: comunicação com a API do OpenStreetMap.
- `pandas`: manipulação e transformação dos dados.
- `psycopg`: conexão com PostgreSQL.
- `shapely`: processamento de geometrias e validação do limite geográfico.