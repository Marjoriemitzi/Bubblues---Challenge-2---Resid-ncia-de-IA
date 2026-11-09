

import os
import pandas as pd
import psycopg
from dotenv import load_dotenv

# Carrega as configurações do arquivo .env
load_dotenv()

arquivo = "data/processed/estabelecimentos.csv"

df = pd.read_csv(arquivo)

senha = os.getenv("DB_PASSWORD")

if not senha:
    raise RuntimeError("Configure DB_PASSWORD no arquivo .env")

with psycopg.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "pipeline_brasilia"),
    user=os.getenv("DB_USER", "postgres"),
    password=senha
) as conexao:

    with conexao.cursor() as cursor:

        # Limpa os dados anteriores antes de uma nova carga
        cursor.execute("TRUNCATE TABLE estabelecimentos;")

        # Insere os registros em lote
        cursor.executemany("""
            INSERT INTO estabelecimentos (
                osm_id, osm_type, nome, tipo_categoria,
                categoria, latitude, longitude, cidade, geom
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            )
        """, [
            (
                int(linha["osm_id"]),
                linha["osm_type"],
                linha["nome"],
                linha["tipo_categoria"],
                linha["categoria"],
                linha["latitude"],
                linha["longitude"],
                linha["cidade"],
                linha["longitude"],
                linha["latitude"]
            )
            for _, linha in df.iterrows()
        ])

print(f"Importação concluída! {len(df)} estabelecimentos enviados.")
