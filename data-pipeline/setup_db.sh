#!/usr/bin/env bash
# Sobe o PostgreSQL (PostGIS + pgvector) e popula com o OSM do DF, de ponta a ponta.
#
#   ./setup_db.sh              sobe o banco e so popula o que estiver vazio (seguro, idempotente)
#   ./setup_db.sh --recriar    refaz carga + curadoria + embeddings (APAGA places e estabelecimentos)
#   ./setup_db.sh --reextrair  baixa o OSM de novo (Overpass) antes de popular
#
# Requer: docker, python3 e um .env com DB_PASSWORD (copie de .env.example).
set -euo pipefail
cd "$(dirname "$0")"

RECRIAR=0; REEXTRAIR=0
for arg in "$@"; do
  case "$arg" in
    --recriar) RECRIAR=1 ;;
    --reextrair) REEXTRAIR=1; RECRIAR=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Opcao desconhecida: $arg" >&2; exit 2 ;;
  esac
done

[ -f .env ] || { echo "Falta data-pipeline/.env (copie .env.example e defina DB_PASSWORD)." >&2; exit 1; }
set -a; . ./.env; set +a
: "${DB_PASSWORD:?Defina DB_PASSWORD no .env}"
DB_USER="${DB_USER:-postgres}"; DB_NAME="${DB_NAME:-pipeline_brasilia}"

PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo ">> Criando .venv e instalando dependencias"
  "$PY" -m venv .venv
  .venv/bin/pip install -q -r requirements.txt -r requirements-embeddings.txt
fi
PY=.venv/bin/python

psql_db() { docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" "$@"; }
contar() { psql_db -tAc "SELECT count(*) FROM $1" 2>/dev/null | tr -d '[:space:]' || echo 0; }

echo ">> Subindo o banco (docker compose)"
docker compose up -d --build db
until [ "$(docker inspect -f '{{.State.Health.Status}}' bubbles-db 2>/dev/null)" = "healthy" ]; do sleep 2; done
# Aplica o schema tambem em volumes ja existentes (e idempotente).
psql_db -q < db/schema.sql >/dev/null

if [ "$REEXTRAIR" = 1 ] || [ ! -s data/raw/estabelecimentos.json ]; then
  echo ">> Extraindo OSM do DF (Overpass API)"; "$PY" extract.py
fi
if [ ! -s data/processed/estabelecimentos.csv ] || [ "$REEXTRAIR" = 1 ]; then
  echo ">> Transformando"; "$PY" transform.py
fi

if [ "$RECRIAR" = 1 ] || [ "$(contar estabelecimentos)" = 0 ]; then
  echo ">> Carregando estabelecimentos"; "$PY" load.py
fi
if [ "$RECRIAR" = 1 ] || [ "$(contar places)" = 0 ]; then
  echo ">> Curadoria (recria places e apaga embeddings)"; psql_db -q < curadoria.sql >/dev/null
fi
if [ "$(psql_db -tAc 'SELECT count(*) FROM places WHERE embedding IS NULL' | tr -d '[:space:]')" != 0 ]; then
  echo ">> Gerando embeddings (baixa o modelo na primeira vez)"; "$PY" gerar_embeddings.py
fi

echo ">> Resumo"
psql_db -c "SELECT (SELECT count(*) FROM estabelecimentos) AS estabelecimentos,
                   count(*) AS places, count(embedding) AS com_embedding,
                   count(*) FILTER (WHERE tags->>'wheelchair'='yes') AS wheelchair_yes
            FROM places"
echo ">> Pronto. Teste com: .venv/bin/python -m pytest"
