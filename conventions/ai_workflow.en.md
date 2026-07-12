# AI Working Methodology

This document lets you resume the project in a new conversation without relying on chat history. It summarizes the agreed working style for SwimStats Chile.

## Sources of truth

- **Architecture and usage**: `backend/README.md`
- **Roadmap**: `docs/plans/implementation_plan.md`
- **Operational agent rules**: `AGENTS.md` / `conventions/AGENTS.en.md`
- **Artifact policy**: `backend/docs/data_artifacts.md`
- **Parser contracts**: `backend/docs/parser_contracts.md`
- **Batch runner contract**: `backend/docs/batch_runner_contract.md`
- **Automated validation**: `backend/docs/fchmn_results_validation.md`
- **Pre-load / full reload checklist**: `backend/docs/pre_load_checklist.md`
- **Current data model**: `backend/docs/schema.md`
- **Traceability and idempotency**: `backend/docs/traceability_idempotency.md`
- **Decision log**: `backend/docs/CHANGELOG.md`

## Core principle

AI-assisted work should advance the real product plan. Each session should push a project phase and explain where, why, and what for.

`AGENTS.md` and this document complement each other:

- `AGENTS.md`: short imperative rules for acting inside the repo.
- `ai_workflow.md`: methodological memory and continuity between conversations.
- Technical contracts live in specific docs. Avoid duplicating long details.

**Current project order:**

1. Harden.
2. Traceability and idempotency.
3. Modularize.
4. Automate with gates (current phase).
5. Curate athlete identity.
6. Expose the data product.

## Mandatory flow per change

1. **Diagnosis**
   - Review `git status`.
   - Read relevant files before proposing changes.
   - Identify the user's local changes and do not overwrite them.
2. **Short proposal**
   - Explain the patch before editing.
   - Keep changes minimal and localized.
3. **Implementation**
   - Follow existing patterns.
   - If regex or parsing changes, add a brief comment.
4. **Verification**
   - Run relevant tests.
   - Run `py_compile` if Python scripts were modified.
5. **Close**
   - Review `git status`.
   - Summarize diagnosis, changes, and verification.
   - Propose a commit message.

## Documentation sync rule

If behavior or a contract changes:

1. Update tests.
2. Update the corresponding technical contract.
3. Update `README.md` if human usage is affected.
4. Update `AGENTS.md` (and `conventions/AGENTS.en.md`) only if an operational rule changes.
5. Record major changes or architectural decisions in `CHANGELOG.md`.

## Operational continuity

This document must not store point-in-time load state, manifests, or next steps — that information goes stale quickly. To resume operational work:

- Use `AGENTS.md` as imperative execution rules.
- Use `docs/plans/implementation_plan.md` as the phased roadmap.
- Use `backend/docs/fchmn_results_validation.md` for current manifest/parser/validation evidence.
- Use `backend/docs/pre_load_checklist.md` before any load or reload.
- Use `backend/docs/CHANGELOG.md` for historical milestones and decisions.

If a conversation needs initial context, it should explicitly ask to read those sources and review `git status` before proposing changes.
