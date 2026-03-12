---
phase: 04-spec-generation-and-coherence
plan: 01
subsystem: validation
tags: [coherence, many2one, computed-depends, security-groups, cjs]

requires:
  - phase: 02-planning-engine
    provides: registry.cjs model registry read/write
provides:
  - coherence.cjs library with 4 structural validation checks
  - CLI subcommand `coherence check` for spec validation
  - BASE_ODOO_MODELS set for base model resolution
affects: [04-02, 04-03, 05-belt-integration]

tech-stack:
  added: []
  patterns: [check-function returns {check, status, violations}, spec.models is array not object]

key-files:
  created:
    - amil/bin/lib/coherence.cjs
    - tests/coherence.test.cjs
  modified:
    - amil/bin/amil-tools.cjs

key-decisions:
  - "BASE_ODOO_MODELS includes 20 common models; base.group_* prefix auto-allowed for security"
  - "Spec models is array, registry models is object -- handled consistently in all 4 checks"

patterns-established:
  - "Coherence check pattern: each check returns {check, status, violations} for uniform aggregation"
  - "Relational validation covers Many2one, Many2many, and One2many comodel_name fields"

requirements-completed: [SPEC-05, SPEC-06, TEST-03]

duration: 2min
completed: 2026-03-05
---

# Phase 4 Plan 1: Coherence Checker Summary

**Pure CJS coherence library with 4 structural checks (many2one targets, duplicate models, computed depends, security groups) and CLI integration**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T19:11:45Z
- **Completed:** 2026-03-05T19:14:28Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created coherence.cjs with 4 structural validation checks and runAllChecks aggregation
- Comprehensive test suite with 33 tests covering all checks, edge cases, and CLI integration
- CLI subcommand `coherence check --spec --registry --raw` registered and functional
- Zero regressions across full 698-test suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Create coherence.test.cjs and coherence.cjs library** - `76edc5a` (feat)
2. **Task 2: Register coherence CLI subcommand** - `ccec647` (feat)

## Files Created/Modified
- `amil/bin/lib/coherence.cjs` - 4 structural checks + runAllChecks + cmdCoherenceCheck + BASE_ODOO_MODELS
- `tests/coherence.test.cjs` - 33 unit and CLI integration tests
- `amil/bin/amil-tools.cjs` - Added coherence case block with --spec/--registry flag parsing

## Decisions Made
- BASE_ODOO_MODELS includes 20 common Odoo models (res.partner, res.users, etc.) that pass many2one validation without registry entry
- Security groups with `base.` prefix auto-allowed as Odoo built-in groups
- Spec models treated as array (matching spec.json format), registry models as object (matching registry format)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Coherence checker ready for use by spec generation pipeline
- All 4 checks produce locked JSON output format matching CONTEXT.md specification
- CLI integration tested end-to-end

---
*Phase: 04-spec-generation-and-coherence*
*Completed: 2026-03-05*
