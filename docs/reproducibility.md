# Reproducibility guide

How to run SwimStats Chile locally with a **working but empty** database, or with **real competition data**.

## Prerequisites

| Tool | Version | Notes |
|------|---------|--------|
| Python | 3.12+ | Backend scripts and tests |
| Node.js | 20+ | Frontend dev server |
| Docker | optional | Postgres + API via Compose |
| `docker compose` or `docker-compose` | optional | Manjaro often uses `docker-compose` from `pacman -S docker-compose` |

If Docker says `permission denied` on `/var/run/docker.sock`, run `newgrp docker` or log out/in after being added to the `docker` group.

---

## Case A — UI + API with empty database

Goal: browse the app locally; lists show **“No se encontraron …”**, not **“Error de comunicación”**.

### What you get

- PostgreSQL with `core.*` tables created
- FastAPI responding on port 8000
- Frontend on port 5173
- **No athletes, clubs, or results** until you load data (Case B)

### Why “Error de comunicación” happens

| Symptom | Cause |
|---------|--------|
| Error de comunicación | API returns **500** (often missing schema) or frontend cannot reach API |
| No se encontraron atletas | API returns **200** with `"data": []` — schema OK, no rows |

Fresh Docker Postgres does **not** apply migrations automatically.

Re-running init on an **already initialized** DB fails with errors like `relation "source" already exists`. That is expected — use `./ci/scripts/populate-db.sh --skip-init` to load data only, or reset with `docker-compose down -v` for a clean slate.

If a previous init failed partway (e.g. `schema "core" does not exist` on migration 006), tables may have been created under `public` instead of `core`. **Reset and re-run:**

```bash
docker-compose down -v          # deletes pgdata volume
docker-compose up -d
./ci/scripts/populate-db.sh --empty
```

### Steps

**1. Start Postgres + API**

```bash
cd /path/to/swimming-chile
docker-compose up -d
```

**2. Apply schema + migrations (pick one)**

```bash
./ci/scripts/populate-db.sh --empty
# Or Compose one-shot init container:
# docker-compose --profile init up --build
# Or legacy:
# ./ci/scripts/init-db.sh
```

**3. Start frontend**

```bash
cd frontend
cp .env.example .env    # VITE_API_URL=http://localhost:8000
npm ci
npm run dev
```

Open http://localhost:5173

**4. Verify**

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/athletes?page=1
# Expect JSON with "data": [] and meta, not Internal Server Error
```

### Without Docker (local Postgres)

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt

# Create DB once in psql: CREATE DATABASE natacion_chile;

DB_HOST=localhost DB_PORT=5432 DB_NAME=natacion_chile DB_USER=postgres PGPASSWORD=yourpass ./ci/scripts/populate-db.sh --empty

cd backend
cp .env.example .env   # set DATABASE_URL or DB_*
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Then start the frontend as in step 3 above.

---

## Case B — Populate the database

Goal: see **real athletes, clubs, competitions, and rankings** in the UI.

Data is **not** shipped in git (PDFs, CSVs, and batch summaries stay local). You have three practical options.

### Option B1 — Point frontend at a deployed API (fastest)

If you already have Railway/production with loaded data:

```bash
# frontend/.env
VITE_API_URL=https://your-api.up.railway.app
```

Restart `npm run dev`. No local Postgres load required.

Ensure the remote API allows your origin in `ALLOWED_ORIGINS` (or use the deployed frontend URL).

### Option B2 — Restore a PostgreSQL dump

If you have a `.sql` or custom-format dump from staging/production:

```bash
docker compose up -d db   # or docker-compose

# Plain SQL dump example:
docker compose exec -T db psql -U postgres -d natacion_chile < your_dump.sql

# Or pg_restore for custom format — see PostgreSQL docs for your dump type.
```

Then run the frontend against `http://localhost:8000` as in Case A.

### Option B3 — Run the ingestion pipeline (full local load)

**Quick smoke load (~5 FCHMN PDFs) — one command:**

```bash
docker-compose up -d
./ci/scripts/populate-db.sh
# Or entirely in Docker (needs network for FCHMN scrape):
docker-compose --profile populate up --build
```

Script: [`ci/scripts/populate-db.sh`](../ci/scripts/populate-db.sh)

| Flag | Effect |
|------|--------|
| `--empty` | Schema only (no scrape/load) |
| `--skip-init` | Skip schema step even if missing (load only) |
| `--resume-load` | Skip scrape/validate; freeze + load existing batch for `--run-id` |
| `--force` | Re-run load even if athletes exist |
| `--limit N` | PDFs to scrape (default 5) |

**Full historical load (~62 documents)** still requires manual curation, freeze, and checklist — not a single command. See [FCHMN validation runbook](../backend/docs/fchmn_results_validation.md).

If validation reports `requires_review` for some PDFs (e.g. OCR name quirks), the smoke script still loads **validated** documents only and skips the rest. Use `--resume-load` to finish freeze + load without re-downloading.

This is the **intended production path** for large loads: public PDFs → manifest → parse → validate → load.

---

## Quick reference

| Goal | Command / config |
|------|------------------|
| Empty working stack | `docker-compose up -d` → `./ci/scripts/populate-db.sh --empty` |
| Populated smoke DB | `./ci/scripts/populate-db.sh` or `docker-compose --profile populate up --build` |
| Check API | `curl http://127.0.0.1:8000/api/athletes?page=1` |
| Use prod data in UI | `VITE_API_URL=<deployed API>` in `frontend/.env` |
| Load data locally | Pipeline in Option B3 + pre-load checklist |
| CI tests (no DB) | `./ci/scripts/backend-test.sh` |

## Related docs

- [Backend README](../backend/README.md)
- [Pre-load checklist](../backend/docs/pre_load_checklist.md)
- [FCHMN validation runbook](../backend/docs/fchmn_results_validation.md)
- [Data artifacts policy](../backend/docs/data_artifacts.md)
- [CI README](../ci/README.md)
