
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

# 1. Carregar configurações do arquivo .env
load_dotenv()

# 2. Localizar arquivo processado
arquivo = Path("data/processed/estabelecimentos.csv")

if not arquivo.exists():
    raise FileNotFoundError(
        "Arquivo CSV não encontrado. Execute primeiro o transform.py."
    )

df = pd.read_csv(arquivo)

if df.empty:
    raise ValueError("O arquivo CSV está vazio.")

# 3. Obter senha do banco
senha = os.getenv("DB_PASSWORD")

if not senha:
    raise RuntimeError("Configure DB_PASSWORD no arquivo .env")

# 4. Conectar ao PostgreSQL e carregar os dados
with psycopg.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "pipeline_brasilia"),
    user=os.getenv("DB_USER", "postgres"),
    password=senha
) as conexao:

    with conexao.cursor() as cursor:

        # Limpar dados anteriores
        cursor.execute("TRUNCATE TABLE estabelecimentos;")

        # Inserir registros em lote
        cursor.executemany("""
            INSERT INTO estabelecimentos (
                osm_id,
                osm_type,
                nome,
                tipo_categoria,
                categoria,
                latitude,
                longitude,
                cidade,
                tags,
                geom
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            )
        """, [
            (
                int(linha["osm_id"]),
                linha["osm_type"],
                linha["nome"],
                linha["tipo_categoria"],
                linha["categoria"],
                float(linha["latitude"]),
                float(linha["longitude"]),
                linha["cidade"],
                linha["tags"],
                float(linha["longitude"]),
                float(linha["latitude"])
            )
            for _, linha in df.iterrows()
        ])

print("Importação concluída!")
print(f"Total de estabelecimentos enviados: {len(df)}")
