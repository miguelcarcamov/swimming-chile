# Shared PostgreSQL helpers for ci/scripts/*.sh
# Source from repo-root-relative scripts; do not execute directly.

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    echo ""
  fi
}

postgres_password() {
  echo "${PGPASSWORD:-${DB_PASSWORD:-postgres}}"
}

run_psql() {
  PGPASSWORD="$(postgres_password)" psql \
    -h "${DB_HOST:-localhost}" \
    -p "${DB_PORT:-5432}" \
    -U "${DB_USER:-postgres}" \
    -d "${DB_NAME:-natacion_chile}" \
    "$@"
}

apply_sql_file_direct() {
  local file="$1"
  echo "Applying $(basename "$file")..."
  run_psql -v ON_ERROR_STOP=1 -f "$file"
}

apply_schema_and_migrations() {
  local sql_dir="$1"
  run_psql -v ON_ERROR_STOP=1 -c "CREATE SCHEMA IF NOT EXISTS core;"
  apply_sql_file_direct "$sql_dir/schema.sql"
  local migration
  while IFS= read -r migration; do
    apply_sql_file_direct "$migration"
  done < <(find "$sql_dir/migrations" -name '*.sql' | sort)
  if [[ -f "$sql_dir/seed/default_sources.sql" ]]; then
    apply_sql_file_direct "$sql_dir/seed/default_sources.sql"
  fi
}

ensure_default_sources_if_missing() {
  local sql_dir="$1"
  local seed="$sql_dir/seed/default_sources.sql"
  if [[ ! -f "$seed" ]]; then
    return 0
  fi
  if run_psql -tAc "SELECT 1 FROM core.source WHERE id = 1 LIMIT 1;" 2>/dev/null | grep -q 1; then
    return 0
  fi
  echo "Seeding default source row (core.source id=1)..."
  apply_sql_file_direct "$seed"
}

schema_tables_present() {
  run_psql -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'core' AND table_name = 'source' LIMIT 1;" \
    2>/dev/null | grep -q 1
}
