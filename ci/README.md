# Continuous Integration

This folder holds CI scripts and documentation. GitHub Actions workflows live in [`.github/workflows/`](../.github/workflows/) and call scripts from here.

## Workflows

| Workflow | Trigger | What it runs |
|----------|---------|--------------|
| `ci.yml` | push/PR to `main` | Backend pytest (contract tests), frontend lint + build |

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
