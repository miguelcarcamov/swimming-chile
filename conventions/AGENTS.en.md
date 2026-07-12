# Project: SwimStats Chile

## Role of this file

`AGENTS.md` (Spanish) and `conventions/AGENTS.en.md` (this file) contain **static operational rules and directives** for AI agents working in this repository. Keep them short, imperative, and execution-oriented.

For working methodology, high-level status, and suggested prompts, read `backend/docs/ai_workflow.md` (Spanish) or `conventions/ai_workflow.en.md` (English).

For historical decisions and prior versions, read `backend/docs/CHANGELOG.md`.

## Primary goal

Build SwimStats Chile as a data platform: extract master competition results from public PDFs, normalize them, curate quality (identities), and load them into PostgreSQL.

## Operational flow (separation of concerns)

The process is strictly decoupled to ensure quality and idempotency:

1. **Scraping** (`scrape_fchmn.py`): Discovers URLs and writes a JSONL manifest. Does not download, parse, or load.
2. **Download** (`download_manifest_pdfs.py`): Downloads PDFs and records hashes. Does not parse or load.
3. **Parsing** (`parse_results_pdf.py`): Converts PDFs (HY-TEK / Swim It Up) to raw CSVs (`club.csv`, `athlete.csv`, `result.csv`, etc.). Does not decide what to load.
4. **Local/OCR curation** (`curate_athlete_names.py`): Resolves OCR variants and consolidates athlete aliases pre-load on CSVs, including manual fuzzy identity decisions reviewed with `decision=merge`.
5. **DB-aware identity audit** (`audit_expected_athlete_identity.py --core-aware-manifest`): Before validate/load, compares the curated manifest against `core.athlete`, `core.athlete_current_club`, and historical clubs. Proposes cross-club name completion only when gender/year match and the source club matches current or historical club; otherwise leaves the case for review.
6. **Decision materialization** (`curate_athlete_names.py`): Applies only human `decision=merge` from reviewed trays. Does not auto-merge DB-aware candidates without review.
7. **Validation** (`run_results_batch.py` without `--load`): Reviews CSVs and applies quality gates. Produces a summary.
8. **Core load** (`run_results_batch.py --load`): Inserts into PostgreSQL only when the validation batch (`manifest.jsonl`) is frozen and `validated`, and `competition_scope` matches.

## Data canon

### event.gender

- `women`
- `men`
- `mixed`

### athlete.gender

- `female`
- `male`

### event.stroke

- `freestyle`
- `backstroke`
- `breaststroke`
- `butterfly`
- `individual_medley`
- `medley_relay`
- `freestyle_relay`

## Critical rules for AI

- **Athlete identity**: Do not treat club as a rigid long-term athlete identity. Athletes can change clubs.
- **Core-aware curation**: For partial vs full names, do not block on `core.athlete.club_id`; use `core.athlete_current_club` and historical clubs as contextual evidence. If the source club is not current/historical, send to review.
- **Contextual age**: `age_at_event` is event-specific. `birth_year_estimated = competition_year - age_at_event`.
- **Generic cleanup only**: The pipeline (`run_pipeline_results.py`) should do only generic cleanup and joins. Fragile heuristics (OCR quirks) belong in the parser or name curation script.
- **Error tolerance**: If `run_results_batch.py` returns `requires_review` for a document, that document must not load to core. One document's failure must not contaminate others in the manifest.
- **Load gate**: `--load` requires an explicit `competition_scope` (e.g. `fchmn_local`). International events (e.g. Sudamericanos) are a separate flow.
- **Passwords**: Never store passwords in auditable summaries, logs, or code.
- **Frontend**: `frontend/` exists as a planned area. Current focus is the data pipeline (backend).

## Working style

1. **Do not rename files unnecessarily.**
2. **Make minimal, localized changes.**
3. **Always explain your diagnosis** and proposed patch before editing code.
4. **If you change a regex or parsing logic**, add a brief comment explaining why.
5. **Preserve compatibility** with PDFs that already pass tests (always run `pytest` or re-validate locally).
6. After changes, review `git status` and propose a commit message.
