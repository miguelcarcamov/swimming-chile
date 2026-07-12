#!/usr/bin/env bash
# Initialize schema and optionally run the FCHMN smoke pipeline (scrape → load).
#
# Host (from repo root):
#   ./ci/scripts/populate-db.sh --empty          # schema only (same as init-db.sh)
#   ./ci/scripts/populate-db.sh                  # schema + smoke load (~5 PDFs)
#   ./ci/scripts/populate-db.sh --skip-init      # load only (schema already applied)
#   ./ci/scripts/populate-db.sh --force          # re-run load even if athletes exist
#   ./ci/scripts/populate-db.sh --limit 10
#
# Docker Compose (populate profile):
#   docker-compose --profile populate up --build
#
# Requires: Python venv on host OR backend Docker image (--inside-container).

set -euo pipefail

MODE="smoke"          # smoke | empty
SKIP_INIT=0
FORCE=0
RESUME_LOAD=0
LIMIT="${POPULATE_LIMIT:-5}"
RUN_ID="${POPULATE_RUN_ID:-local_smoke}"
INSIDE_CONTAINER=0
FCHMN_URL="${FCHMN_URL:-https://fchmn.cl/resultados/}"

if [[ "${POPULATE_INSIDE_CONTAINER:-}" == "1" ]]; then
  INSIDE_CONTAINER=1
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-natacion_chile}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
export PGPASSWORD="${PGPASSWORD:-$DB_PASSWORD}"

usage() {
  sed -n '2,20p' "$0"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --empty) MODE="empty"; shift ;;
    --smoke) MODE="smoke"; shift ;;
    --skip-init) SKIP_INIT=1; shift ;;
    --resume-load) RESUME_LOAD=1; SKIP_INIT=1; shift ;;
    --force) FORCE=1; shift ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --inside-container) INSIDE_CONTAINER=1; DB_HOST="${DB_HOST:-db}"; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
done

CI_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$INSIDE_CONTAINER" -eq 1 ]]; then
  ROOT="/app"
  CI_SCRIPTS="/ci/scripts"
  BACKEND_SCRIPT_DIR="scripts"
  SQL_DIR="$ROOT/sql"
  DATA_RAW="$ROOT/data/raw"
  CLUB_ALIAS="$ROOT/data/reference/club_alias.csv"
else
  ROOT="$(cd "$CI_SCRIPT_DIR/../.." && pwd)"
  CI_SCRIPTS="$ROOT/ci/scripts"
  BACKEND_SCRIPT_DIR="backend/scripts"
  SQL_DIR="$ROOT/backend/sql"
  DATA_RAW="$ROOT/backend/data/raw"
  CLUB_ALIAS="$ROOT/backend/data/reference/club_alias.csv"
fi
cd "$ROOT"

# shellcheck source=ci/scripts/lib/postgres.sh
source "$CI_SCRIPTS/lib/postgres.sh"

MANIFEST_DIR="$DATA_RAW/manifests"
SUMMARY_DIR="$DATA_RAW/batch_summaries"
PDF_DIR="$DATA_RAW/results_pdf/fchmn_auto"
CSV_DIR="$DATA_RAW/results_csv/fchmn_auto"

resolve_python() {
  if [[ "$INSIDE_CONTAINER" -eq 1 ]]; then
    echo "python"
  elif [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
    echo "$ROOT/backend/.venv/bin/python"
  else
    echo "python3"
  fi
}

PYTHON="$(resolve_python)"

if [[ "$MODE" != "empty" ]] && ! "$PYTHON" -c "import pandas, pdfplumber, psycopg" 2>/dev/null; then
  echo "Missing Python deps. Run:" >&2
  echo "  python -m venv backend/.venv && source backend/.venv/bin/activate && pip install -r backend/requirements.txt" >&2
  exit 1
fi

run_psql() {
  PGPASSWORD="$(postgres_password)" psql \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    "$@"
}

athlete_count() {
  run_psql -tAc "SELECT COUNT(*) FROM core.athlete;" 2>/dev/null | tr -d '[:space:]' || echo "0"
}

init_schema() {
  if [[ "$INSIDE_CONTAINER" -eq 1 ]]; then
    USE_DOCKER=0 DB_HOST="$DB_HOST" SQL_DIR="$SQL_DIR" "$CI_SCRIPTS/init-db.sh"
  else
    "$CI_SCRIPTS/init-db.sh"
  fi
}

read_batch_state() {
  local summary="$1"
  "$PYTHON" -c "import json; print(json.load(open('$summary')).get('state', ''))"
}

read_batch_validated_count() {
  local summary="$1"
  "$PYTHON" -c "import json; print(json.load(open('$summary')).get('state_counts', {}).get('validated', 0))"
}

run_smoke_pipeline() {
  mkdir -p "$MANIFEST_DIR" "$SUMMARY_DIR" "$PDF_DIR" "$CSV_DIR"

  local manifest="$MANIFEST_DIR/fchmn_results_validation_${RUN_ID}.jsonl"
  local download_summary="$SUMMARY_DIR/fchmn_results_validation_${RUN_ID}_download.json"
  local batch_summary="$SUMMARY_DIR/fchmn_results_validation_${RUN_ID}_batch.json"
  local frozen="$MANIFEST_DIR/${RUN_ID}_frozen.jsonl"
  local load_summary="$SUMMARY_DIR/${RUN_ID}_load.json"

  if [[ "$RESUME_LOAD" -eq 0 ]]; then
    echo "==> 1/4 Discover, download, validate (limit=$LIMIT)"
    local validation_rc=0
    "$PYTHON" "$BACKEND_SCRIPT_DIR/run_fchmn_results_validation.py" \
      --url "$FCHMN_URL" \
      --run-id "$RUN_ID" \
      --limit "$LIMIT" \
      --manifest-dir "$MANIFEST_DIR" \
      --summary-dir "$SUMMARY_DIR" \
      --pdf-dir "$PDF_DIR" \
      --out-dir-root "$CSV_DIR" \
      --json || validation_rc=$?

    local batch_state validated_count
    batch_state="$(read_batch_state "$batch_summary")"
    validated_count="$(read_batch_validated_count "$batch_summary")"

    if [[ "${validated_count:-0}" -eq 0 ]]; then
      echo "No validated documents (batch state: '$batch_state'). Not loading." >&2
      echo "Review: $batch_summary" >&2
      exit 1
    fi

    if [[ "$batch_state" != "validated" ]]; then
      echo "Note: batch state is '$batch_state' — loading $validated_count validated doc(s); requires_review docs are skipped."
      if [[ "$validation_rc" -ne 0 ]]; then
        echo "Validation exited with code $validation_rc (expected when some docs need review)."
      fi
    fi
  else
    if [[ ! -f "$batch_summary" ]]; then
      echo "Missing batch summary: $batch_summary" >&2
      echo "Run validation first or omit --resume-load." >&2
      exit 1
    fi
    local validated_count
    validated_count="$(read_batch_validated_count "$batch_summary")"
    if [[ "${validated_count:-0}" -eq 0 ]]; then
      echo "No validated documents in $batch_summary" >&2
      exit 1
    fi
    echo "==> Resuming from existing batch ($validated_count validated doc(s))"
  fi

  echo "==> 2/4 Freeze manifest"
  ensure_default_sources_if_missing "$SQL_DIR"
  "$PYTHON" "$BACKEND_SCRIPT_DIR/freeze_validated_manifest.py" \
    --batch-summary "$batch_summary" \
    --manifest "$frozen" \
    --competition-scope fchmn_local \
    --governing-body-code fchmn \
    --governing-body-name FCHMN \
    --allow-all-validated \
    --json

  echo "==> 3/4 Load to PostgreSQL (explicit --load)"
  local load_args=(
    "$BACKEND_SCRIPT_DIR/run_results_batch.py"
    --manifest "$frozen"
    --competition-scope fchmn_local
    --load
    --host "$DB_HOST"
    --port "$DB_PORT"
    --dbname "$DB_NAME"
    --user "$DB_USER"
    --password "$DB_PASSWORD"
    --summary-json "$load_summary"
    --json
  )
  if [[ -f "$CLUB_ALIAS" ]]; then
    load_args+=(--club-alias-csv "$CLUB_ALIAS")
  fi
  "$PYTHON" "${load_args[@]}"

  echo "==> 4/4 Done"
  echo "Athletes in core.athlete: $(athlete_count)"
  echo "Load summary: $load_summary"
}

# --- main ---

if [[ "$SKIP_INIT" -eq 0 ]]; then
  if schema_tables_present; then
    echo "==> Schema already present (core.source); skipping init"
    ensure_default_sources_if_missing "$SQL_DIR"
  else
    echo "==> Initializing schema..."
    init_schema
  fi
else
  echo "==> Skipping schema init (--skip-init)"
  ensure_default_sources_if_missing "$SQL_DIR"
fi

if [[ "$MODE" == "empty" ]]; then
  echo "Empty database ready (schema only)."
  echo "Verify: curl http://127.0.0.1:8000/api/athletes?page=1"
  exit 0
fi

existing="$(athlete_count)"
if [[ "$existing" != "0" && "$FORCE" -eq 0 ]]; then
  echo "Database already has $existing athletes. Use --force to re-run smoke load."
  exit 0
fi

echo "==> Running smoke pipeline (FCHMN, limit=$LIMIT)..."
run_smoke_pipeline

echo ""
echo "Next:"
echo "  curl http://127.0.0.1:8000/api/athletes?page=1"
echo "  cd frontend && npm run dev   # http://localhost:5173"
