"""Busca hibrida de lugares (PostGIS + pgvector) com registro de evidencia."""

import argparse
import json
import math
import os
import uuid
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from observabilidade import atributos, atualizar, coordenada_anonima, finalizar, observacao
from score import (
    PESOS,
    calcular_score,
    chave_ordenacao,
    etiquetas_usadas,
    link_osm,
    validar_evidencia,
)

DIMENSAO_EMBEDDING = 768
FATOR_AMPLIACAO_RAIO = 2.0

SQL_CANDIDATOS = """
    SELECT
        p.place_id, p.nome, p.categoria, p.tipo_categoria,
        p.latitude, p.longitude, p.osm_id, p.osm_type,
        p.tags, p.nota_google, p.nota_app,
        ST_Distance(p.geom::geography, o.ponto) AS distancia_m,
        1 - (p.embedding <=> %(vetor)s::vector) AS similaridade
    FROM places p
    CROSS JOIN (
        SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography AS ponto
    ) o
    WHERE p.embedding IS NOT NULL
      AND (%(tipos)s::text[] IS NULL OR p.categoria = ANY(%(tipos)s::text[]))
      AND ST_DWithin(p.geom::geography, o.ponto, %(raio)s)
"""


def conectar():
    """Abre uma conexao em autocommit com as configuracoes do .env."""
    load_dotenv()
    senha = os.getenv("DB_PASSWORD")
    if not senha:
        raise RuntimeError("Configure DB_PASSWORD no arquivo .env")
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "pipeline_brasilia"),
        user=os.getenv("DB_USER", "postgres"),
        password=senha,
        autocommit=True,
    )


def vetor_para_texto(vetor):
    return "[" + ",".join(repr(float(v)) for v in vetor) + "]"


def _validar_parametros(latitude, longitude, embedding, raio_m, k):
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude invalida.")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude invalida.")
    if raio_m <= 0:
        raise ValueError("O raio deve ser maior que zero.")
    if k < 1:
        raise ValueError("k deve ser pelo menos 1.")
    if len(embedding) != DIMENSAO_EMBEDDING:
        raise ValueError(f"O embedding deve ter {DIMENSAO_EMBEDDING} dimensoes.")
    if not all(math.isfinite(v) for v in embedding):
        raise ValueError("O embedding contem valores nao finitos.")
    if not any(embedding):
        raise ValueError("O embedding nao pode ser o vetor nulo: o cosseno e indefinido.")


def _candidatos(conexao, latitude, longitude, vetor, tipos, raio_m):
    with observacao(
        "fetch-candidates",
        "retriever",
        input={"tipos": tipos, "raio_m": raio_m},
        metadata={"fonte": "postgis+pgvector"},
    ) as obs:
        with conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                SQL_CANDIDATOS,
                {"lat": latitude, "lon": longitude, "vetor": vetor, "tipos": tipos, "raio": raio_m},
            )
            linhas = cursor.fetchall()
        atualizar(
            obs,
            output=[
                {"place_id": l["place_id"], "nome": l["nome"], "similaridade": l["similaridade"],
                 "distancia_m": l["distancia_m"]}
                for l in linhas[:20]
            ],
            metadata={"total_candidatos": str(len(linhas))},
        )
        return linhas


def _pontuar(linha, etiquetas_desejadas):
    fatores, total = calcular_score(
        linha["similaridade"],
        linha["distancia_m"],
        linha["nota_google"],
        linha["nota_app"],
        linha["tags"],
        etiquetas_desejadas,
    )
    return {"linha": linha, "fatores": fatores, "total": total}


def _resultado(posicao, pontuado, etiquetas_desejadas):
    linha = pontuado["linha"]
    return {
        "posicao": posicao,
        "local": {
            "place_id": linha["place_id"],
            "nome": linha["nome"],
            "categoria": linha["categoria"],
            "latitude": linha["latitude"],
            "longitude": linha["longitude"],
            "distancia_m": linha["distancia_m"],
        },
        "osm_url": link_osm(linha["osm_type"], linha["osm_id"]),
        "etiquetas_usadas": etiquetas_usadas(
            linha["tipo_categoria"], linha["categoria"], linha["tags"], etiquetas_desejadas
        ),
        "fatores": pontuado["fatores"],
        "score_total": pontuado["total"],
    }


def _status(quantidade, k):
    if quantidade == 0:
        return "sem_resultado"
    return "completo" if quantidade >= k else "parcial"


def buscar(
    conexao,
    latitude,
    longitude,
    embedding_consulta,
    raio_m=1000,
    tipos=None,
    k=3,
    etiquetas_desejadas=None,
    texto_consulta=None,
):
    """Busca hibrida rastreada no Langfuse (trace `hybrid-search`). Ver `_buscar`."""
    # Input explicito: sem a conexao e sem o vetor de 768 floats; localizacao arredondada.
    entrada = {
        "consulta": texto_consulta,
        "latitude": coordenada_anonima(latitude),
        "longitude": coordenada_anonima(longitude),
        "raio_m": raio_m,
        "tipos": tipos,
        "k": k,
        "etiquetas_desejadas": etiquetas_desejadas or {},
    }
    with observacao("hybrid-search", "chain", input=entrada) as obs:
        registro = _buscar(
            conexao, latitude, longitude, embedding_consulta,
            raio_m, tipos, k, etiquetas_desejadas, texto_consulta,
        )
        atualizar(
            obs,
            output={
                "status": registro["status"],
                "recomendacoes": [
                    {"posicao": r["posicao"], "nome": r["local"]["nome"], "score_total": r["score_total"]}
                    for r in registro["resultados"]
                ],
            },
            metadata={
                "consulta_id": registro["consulta_id"],
                "raio_final_m": str(registro["raio"]["final_m"]),
                "raio_ampliado": str(registro["raio"]["ampliado"]),
                "total_candidatos": str(registro["total_candidatos"]),
            },
        )
        return registro


def _buscar(
    conexao,
    latitude,
    longitude,
    embedding_consulta,
    raio_m=1000,
    tipos=None,
    k=3,
    etiquetas_desejadas=None,
    texto_consulta=None,
):
    """Devolve o top-k com decomposicao e grava (e confirma) o registro de evidencia.

    `tipos` filtra por `places.categoria` (ex.: ["cafe", "park"]). Se houver menos
    de k candidatos, o raio e ampliado uma unica vez.
    """
    _validar_parametros(latitude, longitude, embedding_consulta, raio_m, k)
    tipos = [t.strip().lower() for t in tipos] if tipos else None
    etiquetas_desejadas = etiquetas_desejadas or {}
    vetor = vetor_para_texto(embedding_consulta)

    raio_final = raio_m
    linhas = _candidatos(conexao, latitude, longitude, vetor, tipos, raio_final)
    ampliado = len(linhas) < k
    if ampliado:
        raio_final = raio_m * FATOR_AMPLIACAO_RAIO
        linhas = _candidatos(conexao, latitude, longitude, vetor, tipos, raio_final)

    with observacao("rank-candidates", input={"candidatos": len(linhas), "k": k, "pesos": PESOS}) as obs:
        pontuados = sorted(
            (_pontuar(linha, etiquetas_desejadas) for linha in linhas),
            key=lambda p: chave_ordenacao(
                p["total"], p["linha"]["distancia_m"], p["linha"]["osm_type"], p["linha"]["osm_id"]
            ),
        )
        resultados = [
            _resultado(posicao, pontuado, etiquetas_desejadas)
            for posicao, pontuado in enumerate(pontuados[:k], start=1)
        ]
        atualizar(obs, output=[
            {"posicao": r["posicao"], "nome": r["local"]["nome"], "fatores": r["fatores"],
             "score_total": r["score_total"]}
            for r in resultados
        ])

    registro = {
        "consulta_id": str(uuid.uuid4()),
        "criada_em": datetime.now(timezone.utc).isoformat(),
        "consulta": {
            "texto": texto_consulta,
            "latitude": latitude,
            "longitude": longitude,
            "tipos": tipos,
            "k": k,
            "etiquetas_desejadas": etiquetas_desejadas,
        },
        "raio": {"solicitado_m": raio_m, "final_m": raio_final, "ampliado": ampliado},
        "status": _status(len(resultados), k),
        "total_candidatos": len(linhas),
        "pesos": PESOS,
        "resultados": resultados,
    }
    validar_evidencia(registro)
    _registrar_evidencia(conexao, registro)
    return registro


def _registrar_evidencia(conexao, registro):
    with observacao("persist-evidence", input={"consulta_id": registro["consulta_id"]}):
        conexao.execute(
            "INSERT INTO evidencias_busca (consulta_id, criada_em, registro) VALUES (%s, %s, %s)",
            (registro["consulta_id"], registro["criada_em"], Jsonb(registro)),
        )
        conexao.commit()


def main():
    parser = argparse.ArgumentParser(description="Executa uma busca e imprime a evidencia.")
    parser.add_argument("texto")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--raio", type=float, default=1000)
    parser.add_argument("--tipo", action="append", help="Pode ser repetido.")
    parser.add_argument("-k", type=int, default=3)
    parser.add_argument("--etiqueta", action="append", default=[], metavar="CHAVE=VALOR")
    args = parser.parse_args()

    from gerar_embeddings import gerar_embedding_consulta

    # Um trace por pedido: embedding da consulta + busca hibrida sob a mesma raiz.
    try:
        with atributos(trace_name="place-search", tags=["busca", "pgvector", "postgis"]), observacao(
            "place-search",
            "chain",
            input={"consulta": args.texto, "raio_m": args.raio, "tipos": args.tipo, "k": args.k},
        ) as raiz:
            with conectar() as conexao:
                registro = buscar(
                    conexao,
                    args.lat,
                    args.lon,
                    gerar_embedding_consulta(args.texto),
                    raio_m=args.raio,
                    tipos=args.tipo,
                    k=args.k,
                    etiquetas_desejadas=dict(e.split("=", 1) for e in args.etiqueta),
                    texto_consulta=args.texto,
                )
            atualizar(raiz, output={
                "status": registro["status"],
                "locais": [r["local"]["nome"] for r in registro["resultados"]],
            })
    finally:
        finalizar()  # CLI de vida curta: sem flush os traces se perdem.
    print(json.dumps(registro, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
