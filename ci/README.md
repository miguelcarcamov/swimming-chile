# Continuous Integration

This folder holds CI scripts and documentation. GitHub Actions workflows live in [`.github/workflows/`](../.github/workflows/) and call scripts from here.

## Workflows

| Workflow | Trigger | What it runs |
|----------|---------|--------------|
| `ci.yml` | push/PR to `main` | Backend pytest (contract tests), frontend lint + build |

## Database init (local Docker)

| Goal | Command |
|------|---------|
| Empty DB (schema only) | `./ci/scripts/populate-db.sh --empty` or `docker-compose --profile init up` |
| Smoke sample data (~5 PDFs) | `./ci/scripts/populate-db.sh` or `docker-compose --profile populate up --build` |

Shared helpers: `ci/scripts/lib/postgres.sh`. Schema-only entrypoint: `ci/scripts/init-db.sh` (also used by `populate-db.sh`).

See [docs/reproducibility.md](../docs/reproducibility.md).

## Local parity

Run the same checks locally:

```bash
# Backend (from repo root)
./ci/scripts/backend-test.sh

# Frontend
./ci/scripts/frontend-check.sh
```

## Requirements

- Python 3.12+ with `backend/requirements.txt` installed
- Node.js 20+ with `npm ci` in `frontend/`

Contract tests under `backend/tests/` do not require a live PostgreSQL instance unless explicitly marked as integration tests that connect to a database.
