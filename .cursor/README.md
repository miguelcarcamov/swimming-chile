# Cursor configuration

Project-specific rules and agent skills for SwimStats Chile.

## Rules (`.cursor/rules/`)

| Rule | Scope | Source |
|------|-------|--------|
| `swimstats-conventions.mdc` | Always | [`conventions/AGENTS.en.md`](../conventions/AGENTS.en.md) |
| `backend-pipeline.mdc` | `backend/**` | Pipeline + API guardrails |
| `frontend-contracts.mdc` | `frontend/**` | Contract-first UI |

Full convention text lives in [`conventions/`](../conventions/) (English) and [`AGENTS.md`](../AGENTS.md) (Spanish). Update both languages when operational rules change.

## Agent skills (`.cursor/skills/`)

Invoke explicitly in Cursor chat (e.g. “use the shallow PR review skill”).

| Skill | Purpose |
|-------|---------|
| `shallow-pr-review` | Small, focused PR review — **human always decides merge** |
| `backend-bug-raiser` | Scan backend for bugs/gaps; open GitHub issues |
| `frontend-bug-raiser` | Scan frontend for bugs/gaps; open GitHub issues |
| `docs-issue-raiser` | Scan docs for gaps/stale content; open GitHub issues |

## Related docs

- [CI](../ci/README.md)
- [AI workflow (EN)](../conventions/ai_workflow.en.md)
- [Project audit](../docs/audit/2026-07-11-project-audit.md)
