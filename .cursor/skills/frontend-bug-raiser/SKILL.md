---
name: frontend-bug-raiser
description: Scans the SwimStats Chile frontend for bugs, contract mismatches, and UX gaps, then opens GitHub issues. Use when the user asks to audit the frontend, raise UI bugs, or file frontend improvement issues.
disable-model-invocation: true
---

# Frontend bug raiser

## Goal

Find **actionable** frontend issues and create GitHub issues. Do not implement fixes unless the user asks separately.

## Scope

- `frontend/src/` — components, pages, hooks, services
- `frontend/docs/api_contracts.md` — contract drift vs backend
- `frontend/package.json` — missing scripts, dependency risks

## Process

1. Compare API clients and Zod schemas against `frontend/docs/api_contracts.md`.
2. Check for inconsistent `VITE_API_URL` defaults across services.
3. Run `npm run lint` and `npm run build` in `frontend/` when possible.
4. Note missing tests (no Vitest today), a11y gaps, error/loading states.
5. Deduplicate against open GitHub issues.
6. Create issues with `gh issue create`.

## Issue template

```markdown
**Area:** frontend / (ui|api-contract|tooling|a11y)
**Severity:** critical|high|medium|low

## Problem

## Evidence
(file paths, contract field mismatch, build/lint output)

## Suggested fix

## Acceptance criteria
- [ ] ...
```

## Labels

Use `frontend` plus `bug` or `enhancement`.

## Guardrails

- Contract-first: mismatches with FastAPI responses are bugs, not “backend problems”, unless the contract doc is wrong.
- Do not open duplicate issues already in the audit backlog (#6–#8).
