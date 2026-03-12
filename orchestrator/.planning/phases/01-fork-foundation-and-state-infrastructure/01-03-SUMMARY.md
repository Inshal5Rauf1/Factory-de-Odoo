---
phase: 01-fork-foundation-and-state-infrastructure
plan: 03
subsystem: infra
tags: [state-machine, dependency-graph, toposort, cycle-detection, module-lifecycle]

requires:
  - phase: 01-01
    provides: "amil CLI entry point and renamed tool infrastructure"
provides:
  - "Module lifecycle state machine (planned->spec_approved->generated->checked->shipped)"
  - "Topological sort for module generation order"
  - "Circular dependency detection with cycle path reporting"
  - "Tier grouping by dependency depth (foundation/core/operations/communication)"
  - "Generation blocking based on dependency statuses"
  - "Per-module artifact directory creation"
affects: [01-02, 02, 03, 04, 05]

tech-stack:
  added: []
  patterns: [DFS topological sort, atomic JSON writes with .bak backup, immutable state transitions]

key-files:
  created:
    - amil/bin/lib/module-status.cjs
    - amil/bin/lib/dependency-graph.cjs
    - tests/module-status.test.cjs
    - tests/dependency-graph.test.cjs
  modified:
    - amil/bin/amil-tools.cjs

key-decisions:
  - "Inline atomicWriteJSON in module-status.cjs rather than importing from shared module (keeps modules independent)"
  - "Tier labels mapped by depth index: 0=foundation, 1=core, 2=operations, 3+=communication"
  - "Generation blocking requires deps at 'generated' or beyond (generated, checked, shipped)"
  - "readStatusFile exported from module-status for cross-module use by dependency-graph"

patterns-established:
  - "Module status state machine: VALID_TRANSITIONS map defines all allowed status changes"
  - "Atomic JSON persistence: write .tmp then rename, with .bak backup of previous state"
  - "DFS toposort with visiting set for O(V+E) cycle detection"
  - "Tier assignment by max dependency depth rather than manual tier labels"

requirements-completed: [STAT-01, STAT-02, STAT-03, STAT-04, DEPG-01, DEPG-02, DEPG-03, DEPG-04, DEPG-05, TEST-02]

duration: 4min
completed: 2026-03-05
---

# Phase 1 Plan 3: Module Status and Dependency Graph Summary

**Module lifecycle state machine with DFS topological sort, cycle detection, tier grouping by dependency depth, and generation blocking**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T16:47:16Z
- **Completed:** 2026-03-05T16:51:15Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Module status state machine enforcing planned->spec_approved->generated->checked->shipped lifecycle with all valid/invalid transitions tested
- DFS-based topological sort with O(V+E) circular dependency detection reporting full cycle paths
- Tier grouping by dependency depth (foundation/core/operations/communication) and generation blocking that prevents modules from generating before their dependencies are ready
- 33 new tests (18 module-status + 15 dependency-graph), full suite at 589 tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Module status state machine with tests** - `6c293db` (feat)
2. **Task 2: Dependency graph with toposort, cycle detection, tiers, and CLI dispatch** - `7d7b84c` (feat)

_Note: TDD tasks -- tests written first (RED), then implementation (GREEN)._

## Files Created/Modified
- `amil/bin/lib/module-status.cjs` - Module lifecycle state machine with tier computation (205 LOC)
- `amil/bin/lib/dependency-graph.cjs` - Topological sort, cycle detection, tier grouping, generation blocking (201 LOC)
- `tests/module-status.test.cjs` - 18 tests for status transitions, init, tier computation, atomic writes (250 LOC)
- `tests/dependency-graph.test.cjs` - 15 tests for toposort, cycles, tiers, generation blocking (253 LOC)
- `amil/bin/amil-tools.cjs` - Added module-status and dep-graph CLI dispatch

## Decisions Made
- Inline atomicWriteJSON in module-status.cjs rather than importing from shared module -- keeps modules independent and avoids circular dependency with core.cjs
- readStatusFile exported from module-status.cjs so dependency-graph.cjs can read module statuses for generation blocking checks
- Tier labels assigned by depth index (0=foundation, 1=core, 2=operations, 3+=communication) rather than manual assignment
- Generation blocking checks that deps are at "generated", "checked", or "shipped" status

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Module status and dependency graph engines ready for use by all subsequent phases
- CLI subcommands registered: module-status (read, get, init, transition, tiers) and dep-graph (build, order, tiers, can-generate)
- Cross-module dependency: dependency-graph.cjs imports readStatusFile from module-status.cjs

---
*Phase: 01-fork-foundation-and-state-infrastructure*
*Completed: 2026-03-05*
