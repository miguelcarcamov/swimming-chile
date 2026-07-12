---
name: backend-bug-raiser
description: Scans the SwimStats Chile backend for bugs, gaps, and quality issues, then opens GitHub issues with evidence. Use when the user asks to audit the backend, raise backend bugs, or file backend improvement issues.
disable-model-invocation: true
---

# Backend bug raiser

## Goal

Find **actionable** backend issues (bugs, missing tests, perf smells, contract drift) and create GitHub issues. Do not fix code unless the user asks separately.

## Scope

- `backend/scripts/` — pipeline CLI
- `backend/natacion_chile/` — domain
- `backend/api/` — FastAPI
- `backend/tests/` — coverage gaps
- `backend/sql/` — schema/migrations

## Process

1. Read recent changes: `git log -10 --oneline`, scan high-traffic modules.
2. Run `python -m pytest backend/tests -q` if dependencies are available.
3. Look for: missing error handling, load-gate bypass, SQL injection patterns (raw f-strings with user input), sync DB blocking, duplicate logic, undocumented behavior vs `backend/docs/*`.
4. Deduplicate against [open issues](https://github.com/miguelcarcamov/swimming-chile/issues).
5. Create issues with `gh issue create` — one concern per issue.

## Issue template

```markdown
**Area:** backend / (pipeline|api|tests|sql)
**Severity:** critical|high|medium|low

## Problem
(concrete description + file paths)

## Evidence
(code snippet, test failure, or observation)

## Suggested fix
(short, optional)

## Acceptance criteria
- [ ] ...
```

## Labels

Use `backend` plus `bug` or `enhancement` as appropriate. Create labels if missing.

## Guardrails

- Do not open issues for intentional design documented in `AGENTS.md`.
- Do not include secrets or PII in issue bodies.
- Prefer 3–8 high-quality issues over a long noisy list.
