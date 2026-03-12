# Amil Rebrand — Design Specification

**Date:** 2026-03-12
**Approach:** Big Bang (single pass)
**Scope:** Total rebrand — directories, filenames, internal references, commands, agents, Python package

---

## 1. Brand Change

All user-facing and internal references to `gsd`, `odoo-gsd`, and `odoo-gen` become `amil`.

**Not renamed:** Odoo platform references (`odoo_version`, `Odoo 19.0`, `odoo:19`, `odoo.com`, etc.) — these refer to the Odoo software, not the Amil brand.

---

## 2. Command Inventory (46 total)

### 2.1 Existing Commands — Rename Only (34)

| Current | New |
|---|---|
| `gsd:new-project` | `amil:new-project` |
| `gsd:new-milestone` | `amil:new-milestone` |
| `gsd:complete-milestone` | `amil:complete-milestone` |
| `gsd:plan-phase` | `amil:plan-phase` |
| `gsd:execute-phase` | `amil:execute-phase` |
| `gsd:research-phase` | `amil:research-phase` |
| `gsd:discuss-phase` | `amil:discuss-phase` |
| `gsd:validate-phase` | `amil:validate-phase` |
| `gsd:add-phase` | `amil:add-phase` |
| `gsd:insert-phase` | `amil:insert-phase` |
| `gsd:remove-phase` | `amil:remove-phase` |
| `gsd:quick` | `amil:quick` |
| `gsd:verify-work` | `amil:verify-work` |
| `gsd:add-tests` | `amil:add-tests` |
| `gsd:progress` | `amil:progress` |
| `gsd:health` | `amil:health` |
| `gsd:audit-milestone` | `amil:audit-milestone` |
| `gsd:plan-milestone-gaps` | `amil:plan-milestone-gaps` |
| `gsd:pause-work` | `amil:pause-work` |
| `gsd:resume-work` | `amil:resume-work` |
| `gsd:add-todo` | `amil:add-todo` |
| `gsd:check-todos` | `amil:check-todos` |
| `gsd:debug` | `amil:debug` |
| `gsd:map-codebase` | `amil:map-codebase` |
| `gsd:reapply-patches` | `amil:reapply-patches` |
| `gsd:update` | `amil:update` |
| `gsd:set-profile` | `amil:set-profile` |
| `gsd:settings` | `amil:settings` |
| `gsd:help` | `amil:help` |
| `gsd:list-phase-assumptions` | `amil:list-phase-assumptions` |
| `odoo-gsd:new-erp` | `amil:new-erp` |
| `odoo-gsd:plan-module` | `amil:plan-module` |
| `odoo-gsd:generate-module` | `amil:generate-module` |
| `odoo-gsd:discuss-module` | `amil:discuss-module` |

### 2.2 Stub Completions (5)

| Current | New | Objective |
|---|---|---|
| `run-prd` | `amil:run-prd` | Full PRD-to-ERP generation cycle. One iteration of the autonomous pipeline for Ralph Loop integration. Reads module_status.json + ERP_CYCLE_LOG.md, applies priority table, executes highest-priority action, logs result, runs coherence check, handles errors with retry/block logic. |
| `batch-discuss` | `amil:batch-discuss` | Auto-detect underspecified modules (discussion score < 70) and run questioner agent in batches of 5. Updates CONTEXT.md and discussion scores. |
| `live-uat` | `amil:live-uat` | Interactive browser-based UAT. Verify Docker instance running, guide user through key flows per module, record pass/fail, generate UAT report. |
| `coherence-report` | `amil:coherence-report` | Full cross-module coherence analysis. Run all 4 checks (Many2one targets, duplicate models, computed depends, security groups) across entire model_registry.json. Report violations by severity and module pair. |
| `gsd:cleanup` | `amil:cleanup` | Archive completed milestone phase directories to `.planning/archive/{milestone}/`. Preserve ROADMAP.md references, update STATE.md. |

### 2.3 New Commands — From Pipeline (7)

| New Command | Objective | Delegates To |
|---|---|---|
| `amil:validate-module` | Run pylint-odoo + Docker installation/test validation on a generated module. Produce structured validation report. | `amil-validator` pipeline agent |
| `amil:search-modules` | Semantically search OCA/GitHub for existing Odoo modules matching a natural language description. Rank by relevance, offer gap analysis. | `amil-search` pipeline agent |
| `amil:research-module` | Research Odoo patterns, OCA conventions, and existing solutions before designing a module. Compile research report. | `amil-module-researcher` agent + knowledge base |
| `amil:extend-module` | Fork existing module, generate companion `_ext` module with delta code using `_inherit` and xpath patterns. | `amil-extend` pipeline agent |
| `amil:index-modules` | Build/update local ChromaDB index of OCA modules. Crawl GitHub repos, extract manifests + READMEs, embed, store. | `python -m amil_utils index-oca` CLI |
| `amil:module-history` | Show generation history — timeline of modules with status, file counts, coherence results. | Pure state reading from `.planning/` |
| `amil:phases` | Show generation phases and overall ERP project progress. Phase-by-phase completion percentages. | Pure state reading from ROADMAP.md + module_status.json |

### 2.4 Deleted Commands (7)

| Command | Reason |
|---|---|
| `gsd:join-discord` | Not relevant to Amil |
| `odoo-gen:new` | Covered by `amil:generate-module` |
| `odoo-gen:plan` | Covered by `amil:plan-module` |
| `odoo-gen:config` | Covered by `amil:settings` |
| `odoo-gen:status` | Covered by `amil:progress` |
| `odoo-gen:resume` | Covered by `amil:resume-work` |
| `odoo-gen:help` | Covered by `amil:help` |

---

## 3. Directory & File Renames

### 3.1 Directory Renames

| Current | New |
|---|---|
| `orchestrator/odoo-gsd/` | `orchestrator/amil/` |
| `orchestrator/commands/odoo-gsd/` | `orchestrator/commands/amil/` |

### 3.2 Orchestrator Agent Renames (19 files)

| Current | New |
|---|---|
| `agents/odoo-gsd-belt-executor.md` | `agents/amil-belt-executor.md` |
| `agents/odoo-gsd-belt-verifier.md` | `agents/amil-belt-verifier.md` |
| `agents/odoo-gsd-codebase-mapper.md` | `agents/amil-codebase-mapper.md` |
| `agents/odoo-gsd-debugger.md` | `agents/amil-debugger.md` |
| `agents/odoo-gsd-erp-decomposer.md` | `agents/amil-erp-decomposer.md` |
| `agents/odoo-gsd-executor.md` | `agents/amil-executor.md` |
| `agents/odoo-gsd-integration-checker.md` | `agents/amil-integration-checker.md` |
| `agents/odoo-gsd-module-questioner.md` | `agents/amil-module-questioner.md` |
| `agents/odoo-gsd-module-researcher.md` | `agents/amil-module-researcher.md` |
| `agents/odoo-gsd-nyquist-auditor.md` | `agents/amil-nyquist-auditor.md` |
| `agents/odoo-gsd-phase-researcher.md` | `agents/amil-phase-researcher.md` |
| `agents/odoo-gsd-plan-checker.md` | `agents/amil-plan-checker.md` |
| `agents/odoo-gsd-planner.md` | `agents/amil-planner.md` |
| `agents/odoo-gsd-project-researcher.md` | `agents/amil-project-researcher.md` |
| `agents/odoo-gsd-research-synthesizer.md` | `agents/amil-research-synthesizer.md` |
| `agents/odoo-gsd-roadmapper.md` | `agents/amil-roadmapper.md` |
| `agents/odoo-gsd-spec-generator.md` | `agents/amil-spec-generator.md` |
| `agents/odoo-gsd-spec-reviewer.md` | `agents/amil-spec-reviewer.md` |
| `agents/odoo-gsd-verifier.md` | `agents/amil-verifier.md` |

### 3.3 Pipeline Agent Renames (9 files)

| Current | New |
|---|---|
| `pipeline/agents/odoo-scaffold.md` | `pipeline/agents/amil-scaffold.md` |
| `pipeline/agents/odoo-validator.md` | `pipeline/agents/amil-validator.md` |
| `pipeline/agents/odoo-model-gen.md` | `pipeline/agents/amil-model-gen.md` |
| `pipeline/agents/odoo-view-gen.md` | `pipeline/agents/amil-view-gen.md` |
| `pipeline/agents/odoo-security-gen.md` | `pipeline/agents/amil-security-gen.md` |
| `pipeline/agents/odoo-test-gen.md` | `pipeline/agents/amil-test-gen.md` |
| `pipeline/agents/odoo-search.md` | `pipeline/agents/amil-search.md` |
| `pipeline/agents/odoo-extend.md` | `pipeline/agents/amil-extend.md` |
| `pipeline/agents/odoo-logic-writer.md` | `pipeline/agents/amil-logic-writer.md` |

### 3.4 Hook Renames (3 files)

| Current | New |
|---|---|
| `hooks/odoo-gsd-check-update.js` | `hooks/amil-check-update.js` |
| `hooks/odoo-gsd-context-monitor.js` | `hooks/amil-context-monitor.js` |
| `hooks/odoo-gsd-statusline.js` | `hooks/amil-statusline.js` |

### 3.5 Other File Renames

| Current | New |
|---|---|
| `orchestrator/ODOO_GSD_PRD.md` | `orchestrator/AMIL_PRD.md` |
| `orchestrator/odoo-gsd/bin/odoo-gsd-tools.cjs` | `orchestrator/amil/bin/amil-tools.cjs` |
| `pipeline/bin/odoo-gen-utils` | `pipeline/bin/amil-utils` |

### 3.6 Python Package Rename

| Current | New |
|---|---|
| `pipeline/python/src/odoo_gen_utils/` | `pipeline/python/src/amil_utils/` |
| All `import odoo_gen_utils` | `import amil_utils` |
| All `from odoo_gen_utils` | `from amil_utils` |
| `pyproject.toml` package name | `amil_utils` |

---

## 4. Pipeline Cleanup

### 4.1 Deletions

| Path | Files | Reason |
|---|---|---|
| `pipeline/commands/` | 13 | No user-facing pipeline commands |
| `pipeline/workflows/` | 4 | Logic absorbed into orchestrator |

### 4.2 Workflow Absorption

| Pipeline Workflow | Absorbed Into |
|---|---|
| `scaffold.md` (367 lines) | `amil:generate-module` workflow — quick mode path |
| `spec.md` (592 lines) | `amil:plan-module` workflow — tiered question logic |
| `generate.md` (392 lines) | `amil:generate-module` workflow — rendering details |
| `help.md` (108 lines) | `amil:help` workflow — rebuilt with `amil:` listing |

---

## 5. String Replacement Patterns

Applied in this order (most specific first to avoid double-replacement):

| # | Pattern | Replacement |
|---|---|---|
| 1 | `odoo-gsd-tools.cjs` | `amil-tools.cjs` |
| 2 | `odoo_gen_utils` | `amil_utils` |
| 3 | `odoo-gen-utils` (hyphenated package name) | `amil-utils` |
| 4 | `odoo-gen-manifest.json` | `amil-manifest.json` |
| 5 | `ODOO_GSD_PRD` | `AMIL_PRD` |
| 6 | `ODOO_GSD` | `AMIL` |
| 7 | `ODOO_GEN_PATH` | `AMIL_GEN_PATH` |
| 8 | `odoo-gsd-` (agent/hook prefix) | `amil-` |
| 9 | `odoo-gsd:` (command prefix) | `amil:` |
| 10 | `odoo-gsd` (directory/package) | `amil` |
| 11 | `odoo-gen:` (pipeline command prefix) | `amil:` |
| 12 | `odoo-gen` (pipeline package, standalone) | `amil` |
| 13 | `odoo-scaffold` | `amil-scaffold` |
| 14 | `odoo-validator` | `amil-validator` |
| 15 | `odoo-model-gen` | `amil-model-gen` |
| 16 | `odoo-view-gen` | `amil-view-gen` |
| 17 | `odoo-security-gen` | `amil-security-gen` |
| 18 | `odoo-test-gen` | `amil-test-gen` |
| 19 | `odoo-search` (agent) | `amil-search` |
| 20 | `odoo-extend` (agent) | `amil-extend` |
| 21 | `odoo-logic-writer` | `amil-logic-writer` |
| 22 | `gsd:` (command prefix) | `amil:` |
| 23 | `\bGSD\b` (standalone uppercase, word-boundary) | `Amil` |

**Exclusions:**
- **Odoo platform:** `odoo_version`, `odoo:19`, `Odoo 17.0`, `Odoo 18.0`, `Odoo 19.0`, `odoo.com`, `pylint-odoo`, `odoo-dev.sh`, `verify-odoo-dev.py`
- **Auto-generated directories:** `.venv/`, `node_modules/`, `__pycache__/`, `*.egg-info/` — never modify auto-generated files
- **This spec document:** `docs/superpowers/specs/2026-03-12-amil-rebrand-design.md` — preserves rebrand history with "before" column names intact
- **Other historical docs:** `docs/superpowers/plans/` — leave as-is

### 5.1 Files Requiring Special Attention

| File | Notes |
|---|---|
| `orchestrator/package.json` | Package name `"odoo-gsd"` → `"amil"`, bin entry, files array, coverage path. GitHub URLs (`glittercowboy/odoo-gsd`) should be updated to the new repo URL or removed. |
| `orchestrator/bin/install.js` | 133+ `odoo-gsd`/`gsd` references including Codex agent config, skill generation, command conversion. Heavy file — verify after replacement. |
| `CLAUDE.md` (root) | Brand references in prose and path documentation |
| `orchestrator/CLAUDE.md` | Full command reference table, directory structure docs — rebuild after rename |
| `pipeline/CLAUDE.md` | `odoo-gen:` command table, architecture section — rebuild after rename |
| `pipeline/install.sh` | Creates `~/.claude/odoo-gen/` directories, writes manifest file — all paths need updating |
| `pipeline/pyproject.toml` | Package name, CLI entry point, project metadata |
| `.planning/STATE.md`, `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md` | Active state files — rename all brand references |
| `.planning/phases/*/` | Historical phase artifacts — rename brand references for consistency |
| `orchestrator/.github/` | `FUNDING.yml`, `CODEOWNERS`, `bug_report.yml` — update or remove upstream `glittercowboy` references |
| `reapply-patches.md` | Missing `name:` frontmatter — add `name: amil:reapply-patches` during rebrand |

---

## 6. Testing Strategy

1. Run orchestrator tests (`npm test`) — verify all existing tests pass after rename
2. Run pipeline tests (`pytest`) — verify all existing tests pass after Python package rename
3. Grep audit: confirm zero remaining `odoo-gsd:`, `odoo-gen:`, `gsd:`, `\bGSD\b` references (excluding Odoo platform refs, auto-generated dirs, and this spec)
4. Verify all command files have `name: amil:*` frontmatter
5. Verify CLI entry point `amil-tools.cjs` loads and runs

---

## 7. Scope Clarifications

**In scope — brand references renamed everywhere:**
- All three `.planning/` directories (`orchestrator/.planning/`, `pipeline/.planning/`, `pipeline/python/.planning/`) — active state files and historical phase artifacts
- `.planning/phases/*/` historical artifacts — brand references renamed for consistency (no structural changes)
- All three `CLAUDE.md` files — rebuilt with new brand, paths, and command tables

**Out of scope:**
- Odoo platform references (version strings, Docker images, `pylint-odoo`, `odoo-dev.sh`, etc.)
- Git history rewriting
- External plugin integration (Ralph Loop plugin references — those are in `~/.claude/plugins/`, not this repo)
- Upstream GitHub URLs (`glittercowboy/odoo-gsd`) — update to new repo URL or remove, but don't attempt to modify the upstream repo
