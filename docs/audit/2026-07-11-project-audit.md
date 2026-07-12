# Project Audit — 2026-07-11

Audit of **SwimStats Chile** covering infrastructure, backend pipeline, API, frontend, and reproducibility. Findings are prioritized for GitHub backlog creation.

## Executive summary

The backend data pipeline is mature: decoupled stages, strong contract tests (113+ collected), traceability, and identity curation gates. The FastAPI layer and React frontend are functional but younger. The main gaps are **no CI until now**, **no containerized dev environment**, **sync DB access in FastAPI**, **no frontend tests**, and **mixed ES/EN documentation**.

---

## Infrastructure and DX

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| INF-01 | Critical | No GitHub Actions CI; regressions rely on manual pytest | Added `.github/workflows/ci.yml` + `ci/scripts/` |
| INF-02 | High | Fresh clone fails pytest without `pip install -r backend/requirements.txt` | Document in README; add `Makefile` or dev container |
| INF-03 | High | No Dockerfile / docker-compose for reproducible dev | Added `backend/Dockerfile`, `docker-compose.yml` |
| INF-04 | Medium | No pinned Python version in repo | Added `.python-version` (3.12) |
| INF-05 | Medium | `openspec/config.yaml` references Windows venv path | Update to cross-platform `python -m pytest` |
| INF-06 | Low | No Dependabot/Renovate for dependency updates | Enable GitHub Dependabot |

---

## Backend pipeline

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| PIPE-01 | Low | 19 CLI scripts; good separation per AGENTS.md | Keep; consider thin orchestration wrapper only |
| PIPE-02 | Medium | No coverage reporting in CI | Add `pytest-cov` optional job |
| PIPE-03 | Medium | Large PDF parsing scripts; hard to profile in CI | Keep golden fixtures; add perf budget doc |
| PIPE-04 | Low | PII/staging paths correctly gitignored | Document in onboarding |

**Strengths:** Idempotent load design, manifest freezing, `requires_review` isolation, 23 test modules covering parser, batch runner, audits, and API contracts.

---

## API layer (FastAPI)

| ID | Severity | Finding | Location | Recommendation |
|----|----------|---------|----------|----------------|
| API-01 | High | New DB connection per request; no pool | `backend/api/database.py` | Add connection pool or migrate to async driver |
| API-02 | High | Sync `psycopg` blocks FastAPI event loop under load | All routers | Use `asyncpg` + async routes, or run sync in thread pool |
| API-03 | Medium | `/api/health` does not check DB connectivity | `backend/api/main.py` | Add `/api/health/ready` with DB ping |
| API-04 | Medium | Rankings CTE executed twice (count + page) | `backend/api/routers/rankings.py` | Materialize once or use window count |
| API-05 | Medium | `filter-options` runs 6 sequential queries | `rankings.py` | Combine or cache with TTL |
| API-06 | Low | Raw SQL in routers; no shared query layer | Routers | Acceptable for now; extract if duplication grows |
| API-07 | Low | No rate limiting or auth on public API | `main.py` | Plan when exposing beyond portfolio |

**Strengths:** Clear router split, contract tests, CORS via env, membership schema fallback in athletes router.

---

## Frontend

| ID | Severity | Finding | Location | Recommendation |
|----|----------|---------|----------|----------------|
| FE-01 | High | No test runner or tests | `frontend/package.json` | Add Vitest + component/contract tests |
| FE-02 | Medium | Inconsistent default API base URL | `fetcher.ts` vs `*Service.ts` | Unify on one env default |
| FE-03 | Medium | No OpenAPI-generated types (planned in README) | — | Add `openapi-typescript` from FastAPI `/openapi.json` |
| FE-04 | Low | No E2E tests | — | Playwright when API stable |
| FE-05 | Low | Spanish error in fetcher on contract violation | `fetcher.ts` | i18n or English for OSS |

**Strengths:** Contract-first Zod validation, TanStack Query, Tailwind v4, feature-based structure.

---

## Documentation and conventions

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| DOC-01 | Medium | AGENTS.md Spanish-only for global OSS | Added `conventions/AGENTS.en.md` |
| DOC-02 | Medium | Implementation plan Spanish-only | Translate or add EN summary in `docs/plans/` |
| DOC-03 | Low | Root README English; backend docs mixed | Gradual EN for contributor-facing docs |

---

## Security and data

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| SEC-01 | Low | Default DB password in code fallback | Dev-only; ensure production uses `DATABASE_URL` |
| SEC-02 | Low | PII paths gitignored correctly | Keep checklist in `data_artifacts.md` |
| SEC-03 | Info | Future user accounts schema exists | See `user_accounts_future.md`; no auth on API yet |

---

## Reproducibility checklist

| Item | Status |
|------|--------|
| `backend/requirements.txt` | Present |
| `backend/pyproject.toml` | Added (metadata + tool config) |
| `.python-version` | Added |
| `backend/Dockerfile` | Added |
| `docker-compose.yml` | Added (API + Postgres) |
| `frontend/package-lock.json` | Required for CI `npm ci` |
| `.env.example` files | Present (backend + frontend) |

---

## Suggested implementation order

1. Merge CI + conventions + reproducibility (this PR).
2. Fix API-01/API-02 (connection pooling / async).
3. FE-01 + FE-02 (frontend tests + API URL consistency).
4. API-03 (readiness probe for deploys).
5. OpenAPI codegen (FE-03).
6. Coverage and Dependabot (PIPE-02, INF-06).

---

## Verification performed

- Repository structure and docs review
- `pytest --collect-only`: 113 tests, 7 collection errors without deps (missing `pandas`)
- No `.github/workflows/` before this audit
- `gh auth status`: not logged in — issues created via script for manual run
