#!/usr/bin/env bash
# Create frontend performance backlog issues on GitHub.
# Usage: ./ci/scripts/create-frontend-perf-issues.sh [--dry-run]

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

REPO="${GITHUB_REPOSITORY:-miguelcarcamov/swimming-chile}"

create_issue() {
  local title="$1"
  local body="$2"
  local labels="${3:-frontend,performance}"

  if $DRY_RUN; then
    echo "---"
    echo "TITLE: $title"
    echo "LABELS: $labels"
    echo "$body"
    return
  fi

  gh issue create --repo "$REPO" --title "$title" --label "$labels" --body "$body"
}

if ! $DRY_RUN; then
  gh label create performance --repo "$REPO" --force 2>/dev/null || true
fi

create_issue \
  "[FE-PERF-01] Lazy-load frontend routes to reduce initial bundle" \
  "**Audit:** Frontend performance

Production build shipped a single ~512 KB JS chunk because all pages were eagerly imported in \`frontend/src/app/router.tsx\`, including the large \`RelaysPage\`.

**Acceptance criteria**
- [ ] Route-level \`React.lazy\` + \`Suspense\` for feature pages
- [ ] Main chunk under ~350 KB gzip target (excluding lazy routes)
- [ ] Relays and profile pages load on demand

**Status:** Implemented in working tree — main bundle ~314 KB after code-splitting.

**Refs:** \`docs/audit/2026-07-11-project-audit.md\`"

create_issue \
  "[FE-PERF-02] Rankings page: render one layout (mobile or desktop)" \
  "**Problem:** \`RankingsPage\` mapped every row twice (mobile cards + desktop table), doubling DOM/React work.

**Acceptance criteria**
- [ ] Only one rankings layout rendered per viewport
- [ ] No duplicate \`.map()\` over the same dataset

**Status:** Implemented via \`useMediaQuery\` + conditional render.

**Refs:** \`frontend/src/features/rankings/pages/RankingsPage.tsx\`"

create_issue \
  "[FE-PERF-03] Memoize club attendance matrix derivations" \
  "**Problem:** \`ClubProfilePage\` recomputed O(athletes × competitions) attendance totals on every render and rebuilt per-row \`Map\` instances.

**Acceptance criteria**
- [ ] \`useMemo\` for trend points, footer totals, and athlete lookup maps
- [ ] Filter/year changes do not repeat full nested loops unnecessarily

**Status:** Implemented in \`ClubProfilePage.tsx\`.

**Refs:** \`frontend/src/features/clubs/pages/ClubProfilePage.tsx\`"

create_issue \
  "[FE-PERF-04] Competition profile: debounce search + paginate large result payloads" \
  "**Problem:** Competition detail loads all events/results in one API response; search re-groups on every keystroke.

**Done (working tree)**
- [x] 300 ms debounce before filtering grouped events

**Remaining**
- [ ] API pagination or event-level endpoints for large competitions
- [ ] Optional virtualized result tables when expanded categories are large

**Refs:** \`frontend/src/features/competitions/pages/CompetitionProfilePage.tsx\`, \`backend/api/routers/competitions.py\`"

create_issue \
  "[FE-PERF-05] Keep previous page data during pagination (React Query)" \
  "**Problem:** Paginated list pages flashed full loading state on page change.

**Acceptance criteria**
- [ ] \`placeholderData: (prev) => prev\` on paginated queries (athletes, clubs, competitions, rankings, club roster)

**Status:** Implemented on main paginated routes.

**Refs:** TanStack Query v5 paginated list pages"

create_issue \
  "[API-05] Cache or combine rankings filter-options queries" \
  "**Audit:** API-05 (Medium)

\`GET /api/rankings/filter-options\` runs 6 sequential SQL queries in \`backend/api/routers/rankings.py\`.

**Acceptance criteria**
- [ ] Fewer round-trips (combined query or materialized view)
- [ ] Optional HTTP/cache TTL; frontend already uses 30 min \`staleTime\`

**Related:** #5 (rankings CTE duplicate execution)"

echo "Done."
