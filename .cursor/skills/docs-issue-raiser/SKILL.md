---
name: docs-issue-raiser
description: Scans SwimStats Chile documentation for gaps, stale content, missing English mirrors, and onboarding holes, then opens GitHub issues. Use when the user asks to audit docs or raise documentation issues.
disable-model-invocation: true
---

# Docs issue raiser

## Goal

Find documentation debt and open GitHub issues. Do not rewrite large docs unless the user asks.

## Scope

- Root `README.md`, `AGENTS.md`
- `conventions/`, `.cursor/`
- `backend/docs/`, `frontend/docs/`
- `docs/plans/`, `docs/audit/`
- `ci/README.md`

## Checks

1. **Onboarding:** Can a new contributor install, test, and run API from docs alone?
2. **Bilingual:** Spanish sources without English mirror in `conventions/`?
3. **Contract sync:** Do parser/batch/API docs match code and tests?
4. **Stale plans:** Does `implementation_plan.md` reflect current phase (Fase 4–6)?
5. **Cross-links:** Broken or missing links between README, backend README, CI, conventions.

## Process

1. Read key docs; spot-check against code (file paths, commands, env vars).
2. Deduplicate against open GitHub issues.
3. Create focused issues — one doc concern per issue.

## Issue template

```markdown
**Area:** documentation / (onboarding|i18n|contract|roadmap)
**Severity:** high|medium|low

## Problem

## Affected files

## Proposed update

## Acceptance criteria
- [ ] ...
```

## Labels

Use `documentation` plus `enhancement`.

## Guardrails

- Do not duplicate technical contracts inside `conventions/` — link instead.
- Flag missing reproducibility steps in README as onboarding issues.
