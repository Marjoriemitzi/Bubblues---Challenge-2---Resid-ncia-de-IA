
import os
import psycopg
from dotenv import load_dotenv

# Carregar configurações do arquivo .env
load_dotenv()


def buscar_lugares(latitude, longitude, raio=1000, categorias=None):

    # Validar parâmetros
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude inválida.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude inválida.")

    if raio <= 0:
        raise ValueError("O raio deve ser maior que zero.")

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

            cursor.execute("""
                SELECT
                    nome,
                    categoria,
                    ROUND(
                        ST_Distance(
                            geom::geography,
                            ST_SetSRID(
                                ST_MakePoint(%s, %s), 4326
                            )::geography
                        )::numeric
                    ) AS distancia_metros

                FROM places

                WHERE (
                    %s::text[] IS NULL
                    OR categoria = ANY(%s::text[])
                )

                AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(
                        ST_MakePoint(%s, %s), 4326
                    )::geography,
                    %s
                )

                ORDER BY distancia_metros;
            """, (
                longitude,
                latitude,
                categorias,
                categorias,
                longitude,
                latitude,
                raio
            ))

            resultados = cursor.fetchall()

    return resultados


# Executar teste somente quando este arquivo for executado diretamente
if __name__ == "__main__":

    lugares = buscar_lugares(
        -15.7942,
        -47.8825,
        1000
    )

    print(f"Total de lugares encontrados: {len(lugares)}")

    for lugar in lugares[:10]:
        print(lugar)
