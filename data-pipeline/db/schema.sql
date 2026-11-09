-- Esquema do banco. Idempotente: serve para banco novo (Docker) e para atualizar
-- um banco criado pelos passos manuais antigos do RUNBOOK.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS estabelecimentos (
    osm_id BIGINT,
    osm_type VARCHAR(20),
    nome TEXT,
    tipo_categoria VARCHAR(50),
    categoria VARCHAR(50),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    cidade VARCHAR(100),
    geom GEOMETRY(Point, 4326)
);

ALTER TABLE estabelecimentos
    ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS places (
    place_id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    categoria VARCHAR(50),
    tipo_categoria VARCHAR(50),
    cidade VARCHAR(100),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    osm_id BIGINT NOT NULL,
    osm_type VARCHAR(20) NOT NULL,
    osm_ids_origem JSONB NOT NULL,
    quantidade_origens INTEGER NOT NULL
);

ALTER TABLE places
    ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- 768 dimensoes: paraphrase-multilingual-mpnet-base-v2 (ver gerar_embeddings.py).
    ADD COLUMN IF NOT EXISTS embedding vector(768),
    ADD COLUMN IF NOT EXISTS nota_google NUMERIC(3, 2)
        CHECK (nota_google BETWEEN 0 AND 5),
    ADD COLUMN IF NOT EXISTS nota_app NUMERIC(3, 2)
        CHECK (nota_app BETWEEN 0 AND 5);

-- A busca filtra por ST_DWithin em geography, que nao usa um indice GiST sobre geometry.
CREATE INDEX IF NOT EXISTS idx_places_geography
    ON places USING GIST ((geom::geography));

CREATE INDEX IF NOT EXISTS idx_places_categoria
    ON places (categoria);

-- Sem FK para places: curadoria.sql trunca places, e a evidencia precisa sobreviver.
CREATE TABLE IF NOT EXISTS evidencias_busca (
    consulta_id UUID PRIMARY KEY,
    criada_em TIMESTAMPTZ NOT NULL,
    registro JSONB NOT NULL
);
