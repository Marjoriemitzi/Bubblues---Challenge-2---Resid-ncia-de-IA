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

-- Regioes do DF (RAs, bairros, quadras) para converter "Asa Sul" em coordenadas.
-- Carregada por load_regioes.py a partir do OSM. Sem FK: independe da curadoria de places.
CREATE TABLE IF NOT EXISTS regioes (
    regiao_id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    nome_normalizado TEXT NOT NULL,
    tipo VARCHAR(40) NOT NULL,        -- ex.: place=suburb, admin_level=8
    prioridade SMALLINT NOT NULL,     -- menor = preferida quando o nome se repete
    osm_id BIGINT NOT NULL,
    osm_type VARCHAR(20) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    UNIQUE (osm_type, osm_id)
);

CREATE INDEX IF NOT EXISTS idx_regioes_nome ON regioes (nome_normalizado);

-- Contrato 4 (evidence_record) e trilha de auditoria do Validation_Agent: uma linha por candidato
-- auditado. Candidatos aprovados so entram quando o top inteiro foi aprovado (ou seja, entregue).
-- consulta_id liga ao registro da busca em evidencias_busca (sem FK: curadoria apaga places, nao isto).
CREATE TABLE IF NOT EXISTS evidencias_auditoria (
    evidence_id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL,           -- request_id do orquestrador
    consulta_id UUID,                 -- evidencias_busca.consulta_id
    place_id TEXT NOT NULL,
    place_name TEXT NOT NULL,
    osm_id BIGINT,
    osm_type VARCHAR(20),
    aprovado BOOLEAN NOT NULL,
    rnf01_passed BOOLEAN NOT NULL,
    constraints_passed BOOLEAN NOT NULL,
    math_integrity_passed BOOLEAN NOT NULL,
    score_total DOUBLE PRECISION,
    motivos_rejeicao JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL,          -- EvidenceRecord (Contrato 4) como JSON
    criada_em TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidencias_auditoria_query ON evidencias_auditoria (query_id);
CREATE INDEX IF NOT EXISTS idx_evidencias_auditoria_consulta ON evidencias_auditoria (consulta_id);
