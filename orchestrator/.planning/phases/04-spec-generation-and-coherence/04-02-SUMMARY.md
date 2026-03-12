---
phase: 04-spec-generation-and-coherence
plan: 02
subsystem: agents
tags: [spec-generator, spec-reviewer, coherence, odoo-agents, spec-json]

requires:
  - phase: 03-module-discussion
    provides: Agent frontmatter pattern with skills, color, model_tier fields
provides:
  - Spec generator agent that produces spec.json with all 12 sections plus _available_models
  - Spec reviewer agent that presents coherence report with Odoo-specific context
  - Extended agent frontmatter tests covering both new agents
affects: [04-spec-generation-and-coherence, 05-belt-integration]

tech-stack:
  added: []
  patterns: [read-only agent pattern (no Write tool), single-pass spec generation]

key-files:
  created:
    - agents/amil-spec-generator.md
    - agents/amil-spec-reviewer.md
  modified:
    - tests/agent-frontmatter.test.cjs

key-decisions:
  - "Spec generator uses single-pass output (all 12 sections in one Write) to avoid partial spec states"
  - "Spec reviewer is read-only (no Write tool) -- presentation agent that never modifies files"
  - "Spec reviewer covers all 4 coherence checks: many2one_targets, duplicate_models, computed_depends, security_groups"

patterns-established:
  - "Read-only agent pattern: tools list without Write for agents that only present/analyze"
  - "Spec schema coverage: all 12 sections plus _available_models metadata section"

requirements-completed: [SPEC-02, SPEC-03, AGNT-02, AGNT-04]

duration: 2min
completed: 2026-03-05
---

# Phase 4 Plan 2: Spec Generator and Reviewer Agents Summary

**Spec generator agent producing 12-section spec.json and read-only spec reviewer presenting coherence reports with Odoo context**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T19:11:51Z
- **Completed:** 2026-03-05T19:14:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created spec generator agent with full spec.json schema coverage (models, business_rules, computation_chains, workflow, view_hints, reports, notifications, cron_jobs, security, portal, api_endpoints, _available_models)
- Created spec reviewer agent as read-only presentation agent covering all 4 coherence checks with Odoo-specific violation context
- Extended agent frontmatter tests with 10 new test cases; 708 total tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create spec generator and reviewer agent files** - `2ef647a` (feat)
2. **Task 2: Extend agent frontmatter tests for new agents** - `dd4ae32` (test)

## Files Created/Modified
- `agents/amil-spec-generator.md` - Spec generation agent producing complete spec.json from module context
- `agents/amil-spec-reviewer.md` - Read-only coherence report presenter with Odoo context
- `tests/agent-frontmatter.test.cjs` - Extended with SPEC-GEN and SPEC-REV test suites

## Decisions Made
- Spec generator uses single-pass output to avoid partial spec states
- Spec reviewer is strictly read-only (no Write tool) to prevent accidental modifications
- Field type reference table included in spec generator for Odoo-correct field selection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Spec generator and reviewer agents ready for integration into plan-module pipeline
- Coherence checker (Plan 01) provides the report format that reviewer agent consumes
- Ready for Plan 03 (if exists) or Phase 5 belt integration

---
*Phase: 04-spec-generation-and-coherence*
*Completed: 2026-03-05*
