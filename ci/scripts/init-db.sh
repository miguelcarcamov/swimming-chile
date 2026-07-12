#!/usr/bin/env bash
# Apply backend/sql/schema.sql, migrations, and reference seed rows.
#
# Usage (Docker Compose db service, from repo root):
#   ./ci/scripts/init-db.sh
#
# Usage (direct psql, e.g. inside populate container):
#   USE_DOCKER=0 DB_HOST=db SQL_DIR=/app/sql ./ci/scripts/init-db.sh
#
# Idempotent seed: default_sources.sql uses INSERT ... WHERE NOT EXISTS.
# Re-applying schema.sql on an existing DB will error on duplicate tables — use
# populate-db.sh (detects existing schema) or docker-compose down -v to reset.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# shellcheck source=ci/scripts/lib/postgres.sh
source "$ROOT/ci/scripts/lib/postgres.sh"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-natacion_chile}"
DB_USER="${DB_USER:-postgres}"
SQL_DIR="${SQL_DIR:-$ROOT/backend/sql}"

run_psql_via_compose() {
  $COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 "$@"
}

run_psql_file_via_compose() {
  local file="$1"
  echo "Applying $(basename "$file")..."
  run_psql_via_compose < "$file"
}

COMPOSE="$(compose_cmd)"
if [[ "${USE_DOCKER:-}" != "0" && -z "${USE_DOCKER:-}" && -n "$COMPOSE" ]] && $COMPOSE ps -q db >/dev/null 2>&1; then
  USE_DOCKER=1
  echo "Using Docker Compose db service ($COMPOSE)"
elif [[ "${USE_DOCKER:-}" == "0" ]]; then
  echo "Using direct psql at ${DB_HOST}:${DB_PORT}/${DB_NAME}"
else
  echo "Using Postgres at ${DB_HOST}:${DB_PORT}/${DB_NAME}"
fi

if [[ -n "${USE_DOCKER:-}" && "${USE_DOCKER:-}" != "0" ]]; then
  run_psql_via_compose -c "CREATE SCHEMA IF NOT EXISTS core;"
  run_psql_file_via_compose "$SQL_DIR/schema.sql"
  while IFS= read -r migration; do
    run_psql_file_via_compose "$migration"
  done < <(find "$SQL_DIR/migrations" -name '*.sql' | sort)
  if [[ -f "$SQL_DIR/seed/default_sources.sql" ]]; then
    run_psql_file_via_compose "$SQL_DIR/seed/default_sources.sql"
  fi
else
  apply_schema_and_migrations "$SQL_DIR"
fi

echo ""
echo "Schema ready. Verify:"
if [[ -n "${USE_DOCKER:-}" && "${USE_DOCKER:-}" != "0" ]]; then
  run_psql_via_compose -c '\dt core.*'
else
  run_psql -c '\dt core.*'
fi

echo ""
echo "Next: start frontend (npm run dev) and open http://localhost:5173"
echo "Expect empty lists, not 'Error de comunicación'. See docs/reproducibility.md"
