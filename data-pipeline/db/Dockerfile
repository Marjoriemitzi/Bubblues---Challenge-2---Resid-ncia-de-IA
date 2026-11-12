# A imagem oficial do pgvector nao traz o PostGIS, e a do PostGIS nao traz o pgvector.
# A base e a do pgvector porque a postgis/postgis:16 usa Debian bullseye, cujo
# repositorio do PostgreSQL (PGDG) foi descontinuado.
FROM pgvector/pgvector:0.8.1-pg16-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-postgis-3 \
    && rm -rf /var/lib/apt/lists/*
