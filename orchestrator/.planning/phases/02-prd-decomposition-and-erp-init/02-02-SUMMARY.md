---
phase: 02-prd-decomposition-and-erp-init
plan: "02"
subsystem: new-erp-command
tags: [command, workflow, agents, prd-analysis]
dependency_graph:
  requires: [02-01]
  provides: [new-erp-command, erp-decomposer-agent, module-researcher-agent, new-erp-workflow]
  affects: [02-03]
tech_stack:
  added: []
  patterns: [slash-command, workflow, parallel-task-agents, config-collection]
key_files:
  created:
    - commands/amil/new-erp.md
    - agents/amil-erp-decomposer.md
    - agents/amil-module-researcher.md
    - amil/workflows/new-erp.md
  modified: []
decisions:
  - "Skills follow amil-*-workflow naming convention per test suite"
  - "Agents include anti-heredoc instruction and commented hooks pattern per project conventions"
metrics:
  duration: 4min
  completed: "2026-03-05"
---

# Phase 2 Plan 02: New-ERP Command and Workflow Summary

/amil:new-erp slash command with 7-question config collection (Stage A) and 4 parallel PRD analysis agents (Stage B), including 2 dedicated agent files with exact JSON schemas.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Create new-erp command and 2 agent files | c61abdc, 1d05c00 | commands/amil/new-erp.md, agents/amil-erp-decomposer.md, agents/amil-module-researcher.md |
| 2 | Create new-erp workflow with Stage A and Stage B | 50d8531 | amil/workflows/new-erp.md |

## What Was Built

### Command Entry Point
- `commands/amil/new-erp.md` -- slash command with frontmatter matching existing pattern, references workflow via execution_context

### Agent Files
- `agents/amil-erp-decomposer.md` -- Module Boundary Analyzer that outputs module-boundaries.json with uni_* prefixed modules
- `agents/amil-module-researcher.md` -- OCA Registry Checker that outputs oca-analysis.json with build_new/extend/skip recommendations

### Workflow
- `amil/workflows/new-erp.md` (260 lines) -- Complete workflow with:
  - Stage A: 7 config questions (version, multi-company, localization, existing modules, LMS, notifications, deployment) each writing to config.json immediately
  - Stage B: PRD check, 4 parallel Task() agents (2 dedicated + 2 inline), output validation
  - Stage C: Placeholder comment for merge step (Plan 03)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing required agent frontmatter fields**
- **Found during:** Task 1 verification
- **Issue:** Agent files lacked `tools`, `color`, `skills`, commented hooks pattern, and anti-heredoc instruction required by agent-frontmatter.test.cjs
- **Fix:** Added all required fields matching existing agent conventions
- **Files modified:** agents/amil-erp-decomposer.md, agents/amil-module-researcher.md
- **Commit:** 1d05c00

**2. [Rule 1 - Bug] Skill naming convention mismatch**
- **Found during:** Task 1 verification
- **Issue:** Skills must match `amil-*-workflow` pattern per test suite
- **Fix:** Renamed skills to amil-erp-decomposer-workflow and amil-module-researcher-workflow
- **Commit:** 1d05c00

## Verification

- All agent-frontmatter.test.cjs tests pass (0 failures for our agents)
- Command file contains `amil:new-erp` and references workflow
- Workflow contains Stage A (7 questions), Stage B (4 agents), Stage C placeholder
- Both agents contain exact JSON output schemas
- Workflow exceeds 150 line minimum (260 lines)
