BEGIN;

TRUNCATE TABLE places RESTART IDENTITY;

WITH pares AS (
    SELECT *
    FROM (VALUES
        ('node', 13619139462::BIGINT, 'way', 1485544122::BIGINT),
        ('way', 261459957, 'relation', 20713921),
        ('node', 13302210885, 'way', 962311488),
        ('node', 6969915037, 'relation', 4431149),
        ('node', 12630356563, 'way', 1364023401),
        ('node', 10557735290, 'way', 1276439230),
        ('node', 13302210886, 'way', 1026441722)
    ) AS p(tipo_secundario, id_secundario, tipo_principal, id_principal)
),

mapeamento AS (
    SELECT
        e.*,
        COALESCE(p.tipo_principal, e.osm_type) AS grupo_tipo,
        COALESCE(p.id_principal, e.osm_id) AS grupo_id
    FROM estabelecimentos e
    LEFT JOIN pares p
        ON e.osm_type = p.tipo_secundario
        AND e.osm_id = p.id_secundario
),

grupos AS (
    SELECT
        grupo_tipo,
        grupo_id,
        jsonb_agg(
            jsonb_build_object(
                'osm_id', osm_id,
                'osm_type', osm_type
            )
        ) AS origens,
        COUNT(*) AS quantidade
    FROM mapeamento
    GROUP BY grupo_tipo, grupo_id
),

principais AS (
    SELECT DISTINCT ON (grupo_tipo, grupo_id)
        *
    FROM mapeamento
    ORDER BY
        grupo_tipo,
        grupo_id,
        (osm_type = grupo_tipo AND osm_id = grupo_id) DESC
)

INSERT INTO places (
    nome,
    categoria,
    tipo_categoria,
    cidade,
    latitude,
    longitude,
    geom,
    osm_id,
    osm_type,
    osm_ids_origem,
    quantidade_origens,
    tags
)
SELECT
    p.nome,
    p.categoria,
    p.tipo_categoria,
    p.cidade,
    p.latitude,
    p.longitude,
    p.geom,
    p.osm_id,
    p.osm_type,
    g.origens,
    g.quantidade,
    p.tags
FROM principais p
JOIN grupos g
    ON p.grupo_tipo = g.grupo_tipo
    AND p.grupo_id = g.grupo_id;

COMMIT;