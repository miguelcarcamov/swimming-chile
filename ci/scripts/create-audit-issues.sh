#!/usr/bin/env bash
# Create GitHub issues from the 2026-07-11 audit backlog.
# Prerequisites: gh auth login
# Usage: ./ci/scripts/create-audit-issues.sh [--dry-run]

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

REPO="${GITHUB_REPOSITORY:-miguelcarcamov/swimming-chile}"

create_issue() {
  local title="$1"
  local body="$2"
  local labels="${3:-enhancement}"

  if $DRY_RUN; then
    echo "---"
    echo "TITLE: $title"
    echo "LABELS: $labels"
    echo "$body"
    return
  fi

  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --label "$labels" \
    --body "$body"
}

# Ensure labels exist (ignore errors if already present)
if ! $DRY_RUN; then
  for label in "enhancement" "infrastructure" "backend" "frontend" "documentation" "performance" "testing"; do
    gh label create "$label" --repo "$REPO" --force 2>/dev/null || true
  done
fi

create_issue \
  "[INF-02] Document Python setup and fix onboarding for new clones" \
  "**Audit:** INF-02 (High)

Fresh clones fail \`pytest\` until \`pip install -r backend/requirements.txt\` is run manually.

**Acceptance criteria**
- [ ] README or backend README documents venv + pip install
- [ ] Optional Makefile targets: \`make install\`, \`make test\`
- [ ] CI documents same steps in \`ci/README.md\`

**Refs:** \`docs/audit/2026-07-11-project-audit.md\`" \
  "documentation,infrastructure"

create_issue \
  "[API-01] Add PostgreSQL connection pooling for FastAPI" \
  "**Audit:** API-01 (High)

Each API request opens a new connection via \`get_db_connection()\` in \`backend/api/database.py\`.

**Acceptance criteria**
- [ ] Shared pool or connection manager
- [ ] Graceful shutdown on app exit
- [ ] Contract tests still pass

**Refs:** \`backend/api/database.py\`, audit API-01" \
  "backend,performance"

create_issue \
  "[API-02] Evaluate async DB access for FastAPI routers" \
  "**Audit:** API-02 (High)

Sync \`psycopg\` in async FastAPI can block the event loop under concurrent load.

**Options**
- Migrate to \`asyncpg\` with async route handlers
- Or run sync queries in a thread pool with documented limits

**Acceptance criteria**
- [ ] Decision documented in backend README or ADR
- [ ] Load test or benchmark note for chosen approach" \
  "backend,performance"

create_issue \
  "[API-03] Add DB readiness check to health endpoint" \
  "**Audit:** API-03 (Medium)

\`/api/health\` returns OK without verifying PostgreSQL connectivity.

**Acceptance criteria**
- [ ] \`/api/health/ready\` or extended health checks DB with timeout
- [ ] Railway/deploy docs mention which endpoint to use for probes" \
  "backend,infrastructure"

create_issue \
  "[API-04] Optimize rankings query (avoid duplicate CTE execution)" \
  "**Audit:** API-04 (Medium)

\`list_rankings\` in \`backend/api/routers/rankings.py\` runs the same heavy CTE for COUNT and SELECT.

**Acceptance criteria**
- [ ] Single pass or cached intermediate result for pagination
- [ ] Contract tests unchanged" \
  "backend,performance"

create_issue \
  "[FE-01] Add frontend test runner (Vitest) and initial contract tests" \
  "**Audit:** FE-01 (High)

\`frontend/package.json\` has lint/build but no \`test\` script or test files.

**Acceptance criteria**
- [ ] Vitest configured
- [ ] At least one test for Zod schemas or API fetcher contract violation
- [ ] CI job runs \`npm test\`" \
  "frontend,testing"

create_issue \
  "[FE-02] Unify VITE_API_URL default across frontend API clients" \
  "**Audit:** FE-02 (Medium)

\`fetcher.ts\` defaults to \`/api\`; feature \`*Service.ts\` files default to \`http://127.0.0.1:8000\`.

**Acceptance criteria**
- [ ] Single shared config module for API base URL
- [ ] \`.env.example\` documents dev vs proxy setup" \
  "frontend"

create_issue \
  "[FE-03] Generate TypeScript types from FastAPI OpenAPI spec" \
  "**Audit:** FE-03 (Medium)

README plans OpenAPI-based TS generation; frontend still uses hand-written Zod schemas.

**Acceptance criteria**
- [ ] Script to fetch \`/openapi.json\` and generate types
- [ ] Document workflow in \`frontend/docs/api_contracts.md\`" \
  "frontend,documentation"

create_issue \
  "[PIPE-02] Add optional pytest coverage reporting in CI" \
  "**Audit:** PIPE-02 (Medium)

No coverage metrics in CI today.

**Acceptance criteria**
- [ ] \`pytest-cov\` in dev requirements
- [ ] CI uploads or summarizes coverage (no fail on threshold initially)" \
  "testing,backend"

create_issue \
  "[INF-06] Enable Dependabot for Python and npm dependencies" \
  "**Audit:** INF-06 (Low)

Automate dependency update PRs for \`backend/requirements.txt\` and \`frontend/package-lock.json\`.

**Acceptance criteria**
- [ ] \`.github/dependabot.yml\` configured
- [ ] Weekly schedule for pip and npm" \
  "infrastructure"

create_issue \
  "[DOC-02] Add English summary of implementation plan" \
  "**Audit:** DOC-02 (Medium)

\`docs/plans/implementation_plan.md\` is Spanish-only.

**Acceptance criteria**
- [ ] \`docs/plans/implementation_plan.en.md\` or bilingual sections
- [ ] Linked from root README" \
  "documentation"

echo "Done. $( $DRY_RUN && echo 'Dry run — no issues created.' || echo 'Issues created on GitHub.' )"
