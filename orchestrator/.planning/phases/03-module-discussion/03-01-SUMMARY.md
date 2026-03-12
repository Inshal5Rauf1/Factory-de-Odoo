---
phase: 03-module-discussion
plan: 01
subsystem: data, testing
tags: [json, question-templates, module-types, tdd, node-test]

requires:
  - phase: 02-prd-decomposition
    provides: decomposition.json with module list and types
provides:
  - module-questions.json with 10 type-specific question templates (98 total questions)
  - discuss-module.test.cjs test scaffold covering DISC-01 through DISC-05 and AGNT-01
  - Type detection function for 9 known uni_* prefixes
affects: [03-module-discussion plans 02-04, discuss-module workflow, questioner agent]

tech-stack:
  added: []
  patterns: [question-template-json-schema, module-type-detection-lookup]

key-files:
  created:
    - amil/references/module-questions.json
    - tests/discuss-module.test.cjs
  modified: []

key-decisions:
  - "10 questions per domain type, 8 for generic -- maximizes coverage within 8-12 range"
  - "Question IDs follow {type}_{short_name} pattern for uniqueness and readability"
  - "Type detection uses exact match first, then prefix+underscore match for sub-modules"

patterns-established:
  - "Question template schema: {id, question, options, default, context} per question, context_hints per type"
  - "Type detection: lookup table with 9 known prefixes, null fallback for unknown modules"

requirements-completed: [DISC-02, DISC-03]

duration: 5min
completed: 2026-03-05
---

# Phase 3 Plan 1: Question Templates and Test Scaffold Summary

**10 module-type question templates (98 questions total) with Wave 0 test scaffold covering all Phase 3 requirements**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-05T18:28:56Z
- **Completed:** 2026-03-05T18:34:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created module-questions.json with domain-specific Odoo questions for all 10 module types (core, student, fee, exam, faculty, hr, timetable, notification, portal, generic)
- Created comprehensive test scaffold (21 tests across 6 describe blocks) covering DISC-01 through DISC-05 and AGNT-01
- Type detection function validates all 9 known uni_* prefixes with prefix+underscore sub-module matching

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffold for Phase 3 (Wave 0)** - `2668f65` (test)
2. **Task 2: Create module-questions.json with all 10 type templates** - `f468b67` (feat)

## Files Created/Modified
- `tests/discuss-module.test.cjs` - Test scaffold with 6 test groups: TMPL schema, TYPE detection, CMD command, WF workflow, AGNT questioner, AGNT researcher
- `amil/references/module-questions.json` - 10 question templates with id/question/options/default/context fields and context_hints per type

## Decisions Made
- Used 10 questions per domain type and 8 for generic to maximize coverage within the 8-12 constraint
- Question IDs follow `{type}_{short_name}` convention (e.g., `fee_field_type`, `exam_grading_scale`)
- Each type gets 3 context_hints to guide the questioner agent on what to check in config.json and decomposition.json

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- module-questions.json ready for consumption by the discuss-module workflow (Plan 02)
- Test scaffold ready to validate all remaining Phase 3 artifacts (command, workflow, agents)
- 16 of 21 tests pass; 5 remaining failures await command/workflow/agent file creation in Plans 02-04

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 03-module-discussion*
*Completed: 2026-03-05*
