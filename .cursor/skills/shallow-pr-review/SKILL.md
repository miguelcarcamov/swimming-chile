---
name: shallow-pr-review
description: Performs a shallow, focused pull request review for SwimStats Chile. Surfaces risks and suggestions only; never approves or merges on behalf of a human. Use when the user asks for a PR review, shallow review, or pre-merge check.
disable-model-invocation: true
---

# Shallow PR review

## Role

You are a **review assistant**, not a merge authority. Your output informs a human decision only.

## Hard limits

- **Never** approve, merge, or close a PR.
- **Never** push commits to the PR branch unless the user explicitly asks you to fix something.
- **Never** claim the PR is safe to merge — say “human should decide”.
- Keep the review **shallow**: scope, correctness smell, tests/docs touched, one pass — not a full security audit.

## Steps

1. Identify the diff: `git diff main...HEAD` or the PR URL via `gh pr view` / `gh pr diff`.
2. Map changes to affected areas (pipeline, API, frontend, docs, CI).
3. Check whether tests or docs were updated when behavior changed.
4. Flag blockers (data load risk, breaking API contract, missing tests for parser changes).
5. Output a short structured review.

## Output format

```markdown
## Shallow PR review

**Verdict:** Human should decide (not approved by agent)

### Summary
(1–3 sentences)

### What looks good
- ...

### Concerns / questions
- [severity: high|medium|low] ...

### Suggested follow-ups (optional)
- ...

### Checks run
- (list commands run, or “none — review from diff only”)
```

## Project context

Follow `conventions/AGENTS.en.md`. Treat any `--load`, identity auto-merge, or parser regex change as high attention.
