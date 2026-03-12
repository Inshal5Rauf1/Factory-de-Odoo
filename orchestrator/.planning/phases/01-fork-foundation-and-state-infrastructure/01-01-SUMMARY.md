---
phase: 01-fork-foundation-and-state-infrastructure
plan: 01
subsystem: infra
tags: [cli, rename, fork, installer, claude-code]

requires: []
provides:
  - "amil directory structure and CLI entry point"
  - "amil-tools.cjs renamed CLI with all internal references updated"
  - "32 slash commands with /amil: prefix"
  - "12 agent definitions with amil- prefix"
  - "Claude-Code-only install.js with amil and Python checks"
  - "CLAUDE.md project context document"
affects: [01-02, 01-03, 02, 03, 04, 05]

tech-stack:
  added: []
  patterns: [amil-* naming convention, .amil/ config directory]

key-files:
  created:
    - amil/bin/install.js
    - CLAUDE.md
  modified:
    - amil/bin/amil-tools.cjs
    - amil/bin/lib/core.cjs
    - amil/bin/lib/config.cjs
    - tests/helpers.cjs
    - package.json

key-decisions:
  - "Renamed all gsd- prefixes to amil- for full identity separation"
  - "Changed config directory from .gsd/ to .amil/"
  - "Rewrote install.js from 2464 to 407 lines, Claude-Code-only"
  - "Updated branch templates from gsd/ to amil/ prefix"

patterns-established:
  - "amil-* prefix: all agent names, hook names, and CLI references use this prefix"
  - "/amil: command prefix: all slash commands use this namespace"
  - "Claude-Code-only: no multi-runtime support in install or config paths"

requirements-completed: [FORK-01, FORK-02, FORK-03, FORK-04, FORK-05, FORK-06, FORK-07, FORK-08, FORK-09, FORK-10, TEST-05]

duration: 8min
completed: 2026-03-05
---

# Phase 1 Plan 1: Fork Rename and Identity Summary

**Complete rename of Amil fork to amil identity with zero old references, all 535 tests passing, and Claude-Code-only installer**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-05T16:35:24Z
- **Completed:** 2026-03-05T16:43:30Z
- **Tasks:** 2
- **Files modified:** 164

## Accomplishments
- Renamed entire codebase from get-shit-done/gsd to amil identity (directories, files, internal references)
- Zero remaining old references across all .cjs, .md, .js, .json files
- All 535 tests pass after rename
- Rewrote install.js from 2464 lines to 407 lines, Claude-Code-only with amil and Python 3.8+ checks
- Created CLAUDE.md documenting amil architecture, commands, rules, and development workflow

## Task Commits

Each task was committed atomically:

1. **Task 1: Rename directory structure and all internal references** - `b1b1021` (feat)
2. **Task 2: Rewrite install.js and CLAUDE.md** - `aaf6da7` (feat)

## Files Created/Modified
- `amil/bin/amil-tools.cjs` - Renamed CLI entry point
- `amil/bin/lib/core.cjs` - MODEL_PROFILES with amil-* keys
- `amil/bin/lib/config.cjs` - .amil/ config directory paths
- `amil/bin/install.js` - New Claude-Code-only installer (407 LOC)
- `commands/amil/` - 32 command files with /amil: prefix
- `agents/amil-*.md` - 12 renamed agent definitions
- `hooks/amil-*.js` - 3 renamed hook files
- `tests/helpers.cjs` - Updated TOOLS_PATH and temp dir prefix
- `package.json` - amil name, description, keywords
- `CLAUDE.md` - Odoo ERP orchestrator context document

## Decisions Made
- Renamed config directory from ~/.gsd/ to ~/.amil/ for full identity separation
- Updated git branch templates from gsd/ to amil/ prefix
- Stripped all multi-runtime support (OpenCode, Gemini, Codex) from install.js
- Set package version to 1.0.0 (fresh fork identity)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed double-rename issue during sed replacement**
- **Found during:** Task 1 (Layer 4 internal reference updates)
- **Issue:** Sequential sed replacements caused "odoo-amil" double-prefixes when gsd-tools matched inside already-renamed amil-tools
- **Fix:** Added a cleanup pass to replace odoo-amil with amil, then switched to perl negative lookbehind for remaining replacements
- **Files modified:** All .cjs, .md, .js, .json files
- **Verification:** grep confirmed zero odoo-amil matches
- **Committed in:** b1b1021 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Auto-fix was necessary to prevent broken references. No scope creep.

## Issues Encountered
- CLAUDE.md was in .gitignore; required `git add -f` to commit
- Pre-existing test failure (config-get model_profile expected 'balanced' but ~/.gsd/defaults.json had 'quality') self-resolved after renaming config dir to .amil/

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- amil identity fully established as foundation for all Phase 1 work
- All subsequent plans can use /amil: commands and amil-tools.cjs paths
- install.js ready for amil integration when belt is available (Phase 5)

---
*Phase: 01-fork-foundation-and-state-infrastructure*
*Completed: 2026-03-05*
