# Amil Rebrand Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Total rebrand of Factory de Odoo from `gsd`/`odoo-gsd`/`odoo-gen` to `amil` — single namespace, single brand across all 221 affected files.

**Architecture:** Big Bang rename in one pass. Phase 1: git mv all directories/files. Phase 2: sed all string references (23 patterns, most-specific-first). Phase 3: delete pipeline commands/workflows + join-discord. Phase 4: complete 4 stub commands + create 7 new commands. Phase 5: rebuild 3 CLAUDE.md files. Phase 6: verify tests + grep audit.

**Tech Stack:** Bash (git mv, sed, find), Node.js (orchestrator tests), Python/pytest (pipeline tests)

**Spec:** `docs/superpowers/specs/2026-03-12-amil-rebrand-design.md`

---

## Chunk 1: File System Renames

### Task 1: Safety Preparation

**Files:**
- All uncommitted changes on `factory-upgrades` branch

- [ ] **Step 1: Verify branch and status**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git branch --show-current
git status --short | head -20
```
Expected: On `factory-upgrades`, 64+ modified files (Odoo 19.0 upgrade changes).

- [ ] **Step 2: Commit Odoo 19.0 upgrade changes**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add -A
git commit -m "feat: complete Odoo 19.0 upgrade — all 8 gaps + audit fixes

Apply FACTORY-UPGRADE-BUILD-GUIDE.md phases 1-10:
- Template 19.0 support (form/list/search/kanban/wizard views)
- Manifest and security CSV generation for 19.0
- Auto-fix pipeline for pylint-odoo compliance
- Docker validation runner with 19.0 images
- 797 orchestrator tests passing, 94+ pipeline tests passing"
```

- [ ] **Step 3: Create safety tag**

```bash
git tag pre-amil-rebrand
```

### Task 2: Directory & File Renames

**Directories renamed:**
- `orchestrator/odoo-gsd/` → `orchestrator/amil/`
- `orchestrator/commands/odoo-gsd/` → `orchestrator/commands/amil/`
- `pipeline/python/src/odoo_gen_utils/` → `pipeline/python/src/amil_utils/`

**Files renamed:** 19 orchestrator agents + 9 pipeline agents + 3 hooks + 3 other files = 34 file renames

- [ ] **Step 1: Rename directories**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git mv orchestrator/odoo-gsd orchestrator/amil
git mv orchestrator/commands/odoo-gsd orchestrator/commands/amil
git mv pipeline/python/src/odoo_gen_utils pipeline/python/src/amil_utils
```

- [ ] **Step 2: Rename orchestrator agent files (19)**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
for f in orchestrator/agents/odoo-gsd-*.md; do
  git mv "$f" "${f/odoo-gsd-/amil-}"
done
```

Produces: `amil-belt-executor.md`, `amil-belt-verifier.md`, `amil-codebase-mapper.md`, `amil-debugger.md`, `amil-erp-decomposer.md`, `amil-executor.md`, `amil-integration-checker.md`, `amil-module-questioner.md`, `amil-module-researcher.md`, `amil-nyquist-auditor.md`, `amil-phase-researcher.md`, `amil-plan-checker.md`, `amil-planner.md`, `amil-project-researcher.md`, `amil-roadmapper.md`, `amil-research-synthesizer.md`, `amil-spec-generator.md`, `amil-spec-reviewer.md`, `amil-verifier.md`

- [ ] **Step 3: Rename pipeline agent files (9)**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
for f in pipeline/agents/odoo-*.md; do
  git mv "$f" "${f/odoo-/amil-}"
done
```

Produces: `amil-scaffold.md`, `amil-validator.md`, `amil-model-gen.md`, `amil-view-gen.md`, `amil-security-gen.md`, `amil-test-gen.md`, `amil-search.md`, `amil-extend.md`, `amil-logic-writer.md`

- [ ] **Step 4: Rename hook files (3) + other files (3)**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
# Hooks
for f in hooks/odoo-gsd-*.js; do
  git mv "$f" "${f/odoo-gsd-/amil-}"
done

# PRD doc
git mv orchestrator/ODOO_GSD_PRD.md orchestrator/AMIL_PRD.md

# CLI tool (now inside renamed amil/ dir)
git mv orchestrator/amil/bin/odoo-gsd-tools.cjs orchestrator/amil/bin/amil-tools.cjs

# Pipeline binary
git mv pipeline/bin/odoo-gen-utils pipeline/bin/amil-utils
```

- [ ] **Step 5: Verify renames**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
# Should find 0 odoo-gsd- prefixed agents
ls orchestrator/agents/odoo-gsd-*.md 2>/dev/null | wc -l
# Should find 19 amil- prefixed agents
ls orchestrator/agents/amil-*.md | wc -l
# Should find 0 odoo- prefixed pipeline agents
ls pipeline/agents/odoo-*.md 2>/dev/null | wc -l
# Should find 9 amil- prefixed pipeline agents
ls pipeline/agents/amil-*.md | wc -l
# Verify directory renames
ls orchestrator/amil/bin/amil-tools.cjs
ls orchestrator/commands/amil/
ls pipeline/python/src/amil_utils/__init__.py
```

Expected: 0, 19, 0, 9, and all paths exist.

- [ ] **Step 6: Commit file renames**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add -A
git commit -m "refactor: rename all odoo-gsd/odoo-gen files and directories to amil

Big Bang rebrand Phase 1 — file system renames:
- 3 directories: odoo-gsd→amil, commands/odoo-gsd→commands/amil, odoo_gen_utils→amil_utils
- 19 orchestrator agent files: odoo-gsd-*→amil-*
- 9 pipeline agent files: odoo-*→amil-*
- 3 hook files: odoo-gsd-*→amil-*
- 3 other files: ODOO_GSD_PRD→AMIL_PRD, odoo-gsd-tools.cjs→amil-tools.cjs, odoo-gen-utils→amil-utils"
```

---

## Chunk 2: String Replacements & Deletions

### Task 3: Bulk String Replacement

**Scope:** All text files excluding `.git/`, `.venv/`, `node_modules/`, `__pycache__/`, `*.egg-info/`, `docs/superpowers/specs/*`, `docs/superpowers/plans/*`

**Patterns:** 23 replacements applied most-specific-first (see spec Section 5)

- [ ] **Step 1: Create replacement script**

Create: `/home/inshal-rauf/Factory-de-Odoo/amil-rebrand.sh`

```bash
#!/bin/bash
# Amil rebrand — 23 string replacements, most-specific-first
# Run from repo root after git mv renames are done
set -euo pipefail

cd /home/inshal-rauf/Factory-de-Odoo

# Collect target files (text files, excluding auto-generated and historical docs)
FILES=$(find . -type f \
  -not -path './.git/*' \
  -not -path './.venv/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*.egg-info/*' \
  -not -path './docs/superpowers/specs/*' \
  -not -path './docs/superpowers/plans/*' \
  \( -name '*.md' -o -name '*.js' -o -name '*.cjs' -o -name '*.json' \
     -o -name '*.py' -o -name '*.toml' -o -name '*.sh' -o -name '*.yml' \
     -o -name '*.yaml' -o -name '*.cfg' -o -name '*.txt' -o -name '*.ini' \))

COUNT=0
for f in $FILES; do
  sed -i -E \
    -e 's/odoo-gsd-tools\.cjs/amil-tools.cjs/g' \
    -e 's/odoo_gen_utils/amil_utils/g' \
    -e 's/odoo-gen-utils/amil-utils/g' \
    -e 's/odoo-gen-manifest\.json/amil-manifest.json/g' \
    -e 's/ODOO_GSD_PRD/AMIL_PRD/g' \
    -e 's/ODOO_GSD/AMIL/g' \
    -e 's/ODOO_GEN_PATH/AMIL_GEN_PATH/g' \
    -e 's/odoo-gsd-/amil-/g' \
    -e 's/odoo-gsd:/amil:/g' \
    -e 's/odoo-gsd/amil/g' \
    -e 's/odoo-gen:/amil:/g' \
    -e 's/odoo-gen/amil/g' \
    -e 's/odoo-scaffold/amil-scaffold/g' \
    -e 's/odoo-validator/amil-validator/g' \
    -e 's/odoo-model-gen/amil-model-gen/g' \
    -e 's/odoo-view-gen/amil-view-gen/g' \
    -e 's/odoo-security-gen/amil-security-gen/g' \
    -e 's/odoo-test-gen/amil-test-gen/g' \
    -e 's/odoo-search/amil-search/g' \
    -e 's/odoo-extend/amil-extend/g' \
    -e 's/odoo-logic-writer/amil-logic-writer/g' \
    -e 's/gsd:/amil:/g' \
    -e 's/\bGSD\b/Amil/g' \
    "$f"
  COUNT=$((COUNT + 1))
done
echo "Processed $COUNT files"

# Handle extensionless files that the find command misses
# pipeline/bin/amil-utils has no .sh extension but contains brand references
sed -i -E \
  -e 's/odoo_gen_utils/amil_utils/g' \
  -e 's/odoo-gen-utils/amil-utils/g' \
  -e 's/odoo-gen/amil/g' \
  pipeline/bin/amil-utils

echo "Processed extensionless files"
```

- [ ] **Step 2: Run replacement script**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
chmod +x amil-rebrand.sh
bash amil-rebrand.sh
```

Expected: `Processed ~200+ files`

- [ ] **Step 3: Spot-check critical files**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
# package.json should have "amil" as name and bin key
grep -n '"amil"' orchestrator/package.json | head -5
# install.js should reference amil paths
grep -c 'amil' orchestrator/bin/install.js
# pyproject.toml should have amil-utils
grep 'amil' pipeline/python/pyproject.toml | head -5
# Python __init__.py should not reference odoo_gen_utils
grep -c 'odoo_gen_utils' pipeline/python/src/amil_utils/__init__.py
# Test helpers should reference amil-tools.cjs
grep 'amil-tools' orchestrator/tests/helpers.cjs
# install.sh should not reference odoo-gen (except ODOO_GEN_DIR variable name — cosmetic)
grep -c 'odoo-gen' pipeline/install.sh
# pipeline/bin/amil-utils should reference amil_utils
grep 'amil_utils' pipeline/bin/amil-utils
```

Expected: `"amil"` in package.json, 100+ amil refs in install.js, `amil-utils`/`amil_utils` in pyproject.toml, 0 old refs in __init__.py, `amil-tools.cjs` in helpers.

- [ ] **Step 4: Remove temporary script**

```bash
rm /home/inshal-rauf/Factory-de-Odoo/amil-rebrand.sh
```

- [ ] **Step 5: Commit string replacements**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add -A
git commit -m "refactor: apply 23 string replacement patterns for amil rebrand

Big Bang rebrand Phase 2 — content replacements:
- odoo-gsd-tools.cjs → amil-tools.cjs
- odoo_gen_utils → amil_utils (Python package)
- odoo-gsd:/odoo-gen:/gsd: → amil: (command prefixes)
- ODOO_GSD → AMIL (env vars)
- All 23 patterns from spec Section 5, most-specific-first order
- Excludes: Odoo platform refs, .venv/, node_modules/, spec doc"
```

### Task 4: Pipeline Cleanup & Command Deletion

**Delete:**
- `pipeline/commands/` (13 files) — pipeline has no user-facing commands
- `pipeline/workflows/` (4 files) — logic absorbed into orchestrator workflows
- `orchestrator/commands/amil/join-discord.md` — not relevant to Amil

- [ ] **Step 1: Delete pipeline commands and workflows**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
rm -rf pipeline/commands/
rm -rf pipeline/workflows/
```

- [ ] **Step 2: Delete join-discord command**

```bash
rm orchestrator/commands/amil/join-discord.md
```

- [ ] **Step 3: Verify deletions**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
ls pipeline/commands/ 2>/dev/null && echo "FAIL: commands still exist" || echo "OK: commands deleted"
ls pipeline/workflows/ 2>/dev/null && echo "FAIL: workflows still exist" || echo "OK: workflows deleted"
ls orchestrator/commands/amil/join-discord.md 2>/dev/null && echo "FAIL: join-discord still exists" || echo "OK: join-discord deleted"
# Verify remaining command count (should be 39: 40 original - 1 deleted)
ls orchestrator/commands/amil/*.md | wc -l
```

Expected: 3x OK, 39 files.

- [ ] **Step 4: Commit deletions**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add -A
git commit -m "refactor: delete pipeline commands/workflows and join-discord

Big Bang rebrand Phase 3 — cleanup:
- Deleted pipeline/commands/ (13 files) — pipeline is pure library, no user-facing commands
- Deleted pipeline/workflows/ (4 files) — logic absorbed into orchestrator workflows
- Deleted join-discord command — not relevant to Amil brand"
```

---

## Chunk 3: Command Content

### Task 5: Complete 4 Stub Commands

**Files:**
- Modify: `orchestrator/commands/amil/run-prd.md`
- Modify: `orchestrator/commands/amil/batch-discuss.md`
- Modify: `orchestrator/commands/amil/live-uat.md`
- Modify: `orchestrator/commands/amil/coherence-report.md`

Each stub currently has only YAML frontmatter. Add full `<context>`, `<objective>`, `<execution_context>`, and `<process>` sections following the pattern in `new-erp.md`.

- [ ] **Step 1: Complete run-prd.md**

Write full content to `orchestrator/commands/amil/run-prd.md`:

```markdown
---
name: amil:run-prd
description: Run full PRD-to-ERP generation cycle
argument-hint: "<path-to-prd>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
  - Skill
---
<context>
Runs one iteration of the autonomous PRD-to-ERP generation pipeline. Reads module_status.json and ERP_CYCLE_LOG.md, applies priority table to select the highest-priority action, executes it, logs the result, runs coherence check, and handles errors with retry/block logic.

**Requires:** `.planning/PRD.md`, initialized ERP project (from /amil:new-erp)
**Produces:** Module state transitions, ERP_CYCLE_LOG.md updates, coherence reports
</context>

<objective>
Execute one cycle of the PRD-to-ERP pipeline: select highest-priority action from module_status.json, execute it, verify coherence, log result.

**After this command:** Check ERP_CYCLE_LOG.md for progress. Run again for next cycle, or use Ralph Loop for autonomous iteration.
</objective>

<execution_context>
@~/.claude/amil/workflows/run-prd.md
</execution_context>

<process>
Execute the run-prd workflow end-to-end. The workflow handles priority selection, action dispatch, coherence verification, and error recovery.
</process>
```

- [ ] **Step 2: Complete batch-discuss.md**

Write full content to `orchestrator/commands/amil/batch-discuss.md`:

```markdown
---
name: amil:batch-discuss
description: Auto-detect underspecified modules and discuss in batches
allowed-tools:
  - Read
  - Write
  - Bash
  - Agent
  - AskUserQuestion
---
<context>
Scans module_status.json for modules at "planned" status with missing or incomplete CONTEXT.md. Groups them into batches of 5 and runs the module questioner agent for each, producing structured CONTEXT.md files with discussion scores.

**Requires:** Initialized ERP project with modules at "planned" status
**Produces:** `.planning/modules/{module}/CONTEXT.md` for each discussed module, updated discussion scores
</context>

<objective>
Auto-detect underspecified modules (discussion score < 70 or missing CONTEXT.md) and run interactive Q&A sessions in batches of 5. Update CONTEXT.md and discussion scores for each module.

**After this command:** Review generated CONTEXT.md files, then run `/amil:plan-module {module}` for modules with score >= 70.
</objective>

<process>

## Step 1: Scan for underspecified modules

Read `module_status.json` and identify modules where:
- Status is "planned" AND
- CONTEXT.md is missing OR discussion_score < 70

Sort by dependency order (foundation modules first).

## Step 2: Show batch summary

```
## Batch Discussion Queue

**Modules needing discussion:** {count}
**Batch size:** 5

| # | Module | Status | Score | Reason |
|---|--------|--------|-------|--------|
| 1 | {name} | planned | {score} | {missing context / low score} |
```

Ask user to confirm or adjust the batch.

## Step 3: Process each batch

For each batch of up to 5 modules:
1. Spawn the `amil-module-questioner` agent for the module
2. Conduct type-aware Q&A session (detect module type from name, load question template)
3. Generate structured CONTEXT.md
4. Calculate discussion score based on answer completeness
5. Update module_status.json with new discussion_score

## Step 4: Report results

```
## Batch Discussion Complete

| # | Module | Score Before | Score After | Status |
|---|--------|-------------|-------------|--------|
| 1 | {name} | {before} | {after} | Ready for spec / Needs more |
```

</process>
```

- [ ] **Step 3: Complete live-uat.md**

Write full content to `orchestrator/commands/amil/live-uat.md`:

```markdown
---
name: amil:live-uat
description: Interactive browser-based UAT verification for shipped modules
allowed-tools:
  - Read
  - Bash
  - Glob
  - Write
  - AskUserQuestion
---
<context>
Guides the user through browser-based User Acceptance Testing of generated Odoo modules. Verifies Docker instance is running, presents key flows per module for manual testing, records pass/fail results, and generates a UAT report.

**Requires:** Generated modules deployed in Docker instance
**Produces:** `.planning/modules/{module}/uat-report.json`
</context>

<objective>
Conduct interactive browser-based UAT for Odoo modules. Verify Docker instance is running, guide user through key flows, record pass/fail results, generate UAT report.

**After this command:** Review UAT report. Modules passing UAT can transition to "shipped" status.
</objective>

<execution_context>
@~/.claude/amil/workflows/live-uat.md
</execution_context>

<process>
Execute the live-uat workflow end-to-end. The workflow handles Docker verification, flow presentation, result recording, and report generation.
</process>
```

- [ ] **Step 4: Complete coherence-report.md**

Write full content to `orchestrator/commands/amil/coherence-report.md`:

```markdown
---
name: amil:coherence-report
description: Analyze cross-module coherence for the full ERP
allowed-tools:
  - Read
  - Bash
  - Glob
---
<context>
Performs comprehensive cross-module coherence analysis across the entire ERP project. Runs 4 check categories against model_registry.json: Many2one target validity, duplicate model detection, computed field dependency chains, and security group consistency.

**Requires:** `model_registry.json` with registered modules
**Produces:** Coherence report to stdout, optionally saved to `.planning/coherence-report.json`
</context>

<objective>
Run full cross-module coherence analysis. Execute all 4 checks (Many2one targets, duplicate models, computed depends, security groups) across the entire model_registry.json. Report violations by severity and module pair.

**After this command:** Fix reported coherence violations before proceeding with further module generation.
</objective>

<process>

## Step 1: Load model registry

Read `model_registry.json` from `.planning/`. Verify it contains registered modules.

If empty or missing:
```
No model registry found. Run /amil:generate-module for at least one module first.
```
Exit.

## Step 2: Run coherence checks

Execute all 4 check categories using the CLI tool:

```bash
node ~/.claude/amil/bin/amil-tools.cjs coherence --cwd .
```

**Check 1: Many2one Target Validity** — verify target models exist in registry.
**Check 2: Duplicate Model Detection** — scan for models in multiple modules (excluding `_inherit`).
**Check 3: Computed Field Dependencies** — trace `depends=` chains, flag circular deps.
**Check 4: Security Group Consistency** — verify groups referenced in views/rules exist.

## Step 3: Report

```
## Cross-Module Coherence Report

**Modules analyzed:** {count}
**Models registered:** {count}

### Critical ({count})
| Module A | Module B | Issue | Field/Model |
|----------|----------|-------|-------------|

### Warning ({count})
| Module | Issue | Detail |
|--------|-------|--------|

**Overall coherence score:** {score}%
```

## Step 4: Save report (optional)

Write structured JSON to `.planning/coherence-report.json`.

</process>
```

- [ ] **Step 5: Fix reapply-patches frontmatter**

Edit `orchestrator/commands/amil/reapply-patches.md` — add missing `name:` field to YAML frontmatter:

Change:
```yaml
---
description: Reapply local modifications after a Amil update
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---
```

To:
```yaml
---
name: amil:reapply-patches
description: Reapply local modifications after an Amil update
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---
```

Note: The sed script already changed "GSD" to "Amil" in this file's content. We just need to add the `name:` field and fix the article ("a Amil" → "an Amil").

- [ ] **Step 6: Commit stub completions**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add orchestrator/commands/amil/run-prd.md \
      orchestrator/commands/amil/batch-discuss.md \
      orchestrator/commands/amil/live-uat.md \
      orchestrator/commands/amil/coherence-report.md \
      orchestrator/commands/amil/reapply-patches.md
git commit -m "feat: complete 4 stub commands and fix reapply-patches frontmatter

- amil:run-prd — full PRD-to-ERP cycle with priority-based action selection
- amil:batch-discuss — auto-detect underspecified modules, discuss in batches of 5
- amil:live-uat — interactive browser-based UAT with Docker verification
- amil:coherence-report — 4-check cross-module coherence analysis
- amil:reapply-patches — added missing name: frontmatter field"
```

### Task 6: Create 7 New Commands

**Files:**
- Create: `orchestrator/commands/amil/validate-module.md`
- Create: `orchestrator/commands/amil/search-modules.md`
- Create: `orchestrator/commands/amil/research-module.md`
- Create: `orchestrator/commands/amil/extend-module.md`
- Create: `orchestrator/commands/amil/index-modules.md`
- Create: `orchestrator/commands/amil/module-history.md`
- Create: `orchestrator/commands/amil/phases.md`

- [ ] **Step 1: Create validate-module.md**

```markdown
---
name: amil:validate-module
description: Run pylint-odoo + Docker installation/test validation on a generated module
argument-hint: "{module_name}"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Write
  - Agent
---
<context>
Validates a generated Odoo module using two passes: static analysis (pylint-odoo with OCA rules) and dynamic validation (Docker-based installation and test execution). Produces a structured validation report.

**Requires:** Generated module directory in addons path
**Produces:** `.planning/modules/{module}/validation-report.json`
</context>

<objective>
Run full validation on a generated Odoo module: pylint-odoo static analysis + Docker installation/test verification. Produce structured validation report.

**After this command:** Fix reported issues, then re-validate or proceed to `/amil:live-uat`.
</objective>

<execution_context>
Spawn the `amil-validator` pipeline agent to execute validation.
</execution_context>

<process>
1. Verify module exists in addons directory
2. Spawn `amil-validator` agent with module path
3. Agent runs pylint-odoo static analysis (OCA ruleset)
4. Agent runs Docker-based installation and `--test-tags={module}` execution
5. Collect and present structured validation report
6. Save report to `.planning/modules/{module}/validation-report.json`
</process>
```

- [ ] **Step 2: Create search-modules.md**

```markdown
---
name: amil:search-modules
description: Semantically search OCA/GitHub for existing Odoo modules matching a description
argument-hint: "<natural language description>"
allowed-tools:
  - Read
  - Bash
  - Write
  - Agent
---
<context>
Searches the local ChromaDB index of OCA modules (and optionally GitHub) for existing Odoo modules matching a natural language description. Ranks results by semantic similarity and offers gap analysis.

**Requires:** Local ChromaDB index (built via /amil:index-modules)
**Produces:** Search results with relevance scores and gap analysis
</context>

<objective>
Semantically search for existing Odoo modules matching a natural language description. Rank by relevance, offer gap analysis.

**After this command:** Use `/amil:extend-module` to fork a match, or `/amil:plan-module` to build from scratch.
</objective>

<execution_context>
Spawn the `amil-search` pipeline agent to execute search.
</execution_context>

<process>
1. Parse natural language description into search query
2. Spawn `amil-search` agent with query
3. Agent searches ChromaDB index + optional GitHub API
4. Present ranked results with relevance scores
5. Offer gap analysis comparing matches against requirements
</process>
```

- [ ] **Step 3: Create research-module.md**

```markdown
---
name: amil:research-module
description: Research Odoo patterns and existing solutions before designing a module
argument-hint: "<module need description>"
allowed-tools:
  - Read
  - Bash
  - Write
  - Agent
  - WebSearch
  - WebFetch
---
<context>
Researches Odoo patterns, OCA conventions, and existing solutions before designing a module. Compiles a research report covering relevant Odoo models, patterns, pitfalls, and recommendations.

**Requires:** Natural language description of the module need
**Produces:** `.planning/modules/{module}/research-report.md`
</context>

<objective>
Research Odoo patterns, OCA conventions, and existing solutions for a module need. Compile research report to inform module design.

**After this command:** Review research report, then run `/amil:discuss-module {module}`.
</objective>

<execution_context>
Spawn the `amil-module-researcher` agent with knowledge base access.
</execution_context>

<process>
1. Parse module need description
2. Spawn `amil-module-researcher` agent
3. Agent researches Odoo patterns, OCA conventions, existing solutions
4. Compile research report: models, patterns, pitfalls, recommendations
5. Save to `.planning/modules/{module}/research-report.md`
</process>
```

- [ ] **Step 4: Create extend-module.md**

```markdown
---
name: amil:extend-module
description: Fork an existing module and generate companion _ext module with delta code
argument-hint: "{base_module_name}"
allowed-tools:
  - Read
  - Bash
  - Write
  - Agent
---
<context>
Forks an existing Odoo module and generates a companion `{module}_ext` module containing only delta code. Uses `_inherit` model extension and xpath view patterns to minimize code while maximizing upstream compatibility.

**Requires:** Base module accessible (OCA, GitHub, or local), extension requirements
**Produces:** Generated `{module}_ext` module in addons directory
</context>

<objective>
Fork an existing module and generate a companion _ext module with delta code using _inherit and xpath patterns.

**After this command:** Validate with `/amil:validate-module {module}_ext`.
</objective>

<execution_context>
Spawn the `amil-extend` pipeline agent to execute extension generation.
</execution_context>

<process>
1. Identify base module (local, OCA, or GitHub)
2. Analyze base module structure and models
3. Spawn `amil-extend` agent with base module path and requirements
4. Agent generates companion _ext module with _inherit + xpath patterns
5. Register new module in model_registry.json
6. Run coherence check against existing modules
</process>
```

- [ ] **Step 5: Create index-modules.md**

```markdown
---
name: amil:index-modules
description: Build or update local ChromaDB index of OCA Odoo modules for semantic search
allowed-tools:
  - Read
  - Bash
  - Write
---
<context>
Builds or updates a local ChromaDB vector index of OCA Odoo modules. Crawls GitHub repos, extracts manifests and READMEs, generates embeddings, and stores them for semantic search.

**Requires:** Python environment with amil_utils[search] installed
**Produces:** ChromaDB index at `~/.claude/amil/search-index/`
</context>

<objective>
Build or update the local ChromaDB index of OCA modules for semantic search.

**After this command:** Use `/amil:search-modules` to query the index.
</objective>

<process>
1. Verify Python environment has `amil_utils[search]` installed
2. Run the indexing CLI:
   ```bash
   python -m amil_utils index-oca
   ```
3. CLI crawls OCA GitHub repos, extracts manifests and READMEs
4. Generates embeddings using ChromaDB's built-in ONNX model
5. Stores vectors in `~/.claude/amil/search-index/`
6. Report indexing statistics (modules indexed, repos crawled, duration)
</process>
```

- [ ] **Step 6: Create module-history.md**

```markdown
---
name: amil:module-history
description: Show generation history — timeline of modules with status and coherence results
allowed-tools:
  - Read
  - Bash
  - Glob
---
<context>
Displays the generation history timeline showing all modules with their current status, file counts, generation dates, and coherence check results.

**Requires:** Initialized ERP project with module_status.json
**Produces:** Formatted history display to stdout
</context>

<objective>
Show generation history — timeline of modules with status, file counts, and coherence results.

**After this command:** Use `/amil:progress` for overall status, or `/amil:coherence-report` for detailed analysis.
</objective>

<process>
1. Read `module_status.json` from `.planning/`
2. For each module, gather: status, file count, generation timestamp, last coherence score
3. Sort by generation date (most recent first)
4. Display formatted timeline:
   ```
   ## Module Generation History

   | # | Module | Status | Files | Generated | Coherence |
   |---|--------|--------|-------|-----------|-----------|
   | 1 | {name} | shipped | {count} | {date} | {score}% |
   ```
5. Show summary statistics (total modules, counts by status, avg coherence)
</process>
```

- [ ] **Step 7: Create phases.md**

```markdown
---
name: amil:phases
description: Show generation phases and overall ERP project progress
allowed-tools:
  - Read
  - Bash
  - Glob
---
<context>
Displays ERP project generation phases with per-phase completion percentages. Reads from ROADMAP.md and module_status.json to calculate progress across the module generation waves.

**Requires:** Initialized ERP project with ROADMAP.md
**Produces:** Formatted phase progress display to stdout
</context>

<objective>
Show generation phases and overall ERP project progress with phase-by-phase completion percentages.

**After this command:** Use `/amil:progress` for detailed context, or `/amil:run-prd` to advance the next cycle.
</objective>

<process>
1. Read ROADMAP.md and `module_status.json` from `.planning/`
2. Map modules to generation waves (Foundation, Department, Cross-functional, Integration, Analytics, Polish)
3. Calculate per-wave completion by module status distribution
4. Display formatted progress:
   ```
   ## ERP Generation Phases

   | Wave | Name | Modules | Shipped | Progress |
   |------|------|---------|---------|----------|
   | 1 | Foundation | {n} | {n} | {pct}% |

   **Overall:** {shipped}/{total} modules shipped ({pct}%)
   ```
</process>
```

- [ ] **Step 8: Verify command count**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
ls orchestrator/commands/amil/*.md | wc -l
```

Expected: **46** (39 existing after delete + 7 new = 46).

- [ ] **Step 9: Verify all commands have name: frontmatter**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
for f in orchestrator/commands/amil/*.md; do
  if ! grep -q '^name:' "$f"; then
    echo "MISSING name: in $f"
  fi
done
```

Expected: No output (all commands have `name:` field).

- [ ] **Step 10: Verify all name: fields use amil: prefix**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
grep '^name:' orchestrator/commands/amil/*.md | grep -v 'amil:' || echo "All commands use amil: prefix"
```

Expected: `All commands use amil: prefix`

- [ ] **Step 11: Commit new commands**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add orchestrator/commands/amil/validate-module.md \
      orchestrator/commands/amil/search-modules.md \
      orchestrator/commands/amil/research-module.md \
      orchestrator/commands/amil/extend-module.md \
      orchestrator/commands/amil/index-modules.md \
      orchestrator/commands/amil/module-history.md \
      orchestrator/commands/amil/phases.md
git commit -m "feat: create 7 new commands migrated from pipeline

- amil:validate-module — pylint-odoo + Docker validation via amil-validator agent
- amil:search-modules — semantic OCA/GitHub search via amil-search agent
- amil:research-module — Odoo pattern research via amil-module-researcher agent
- amil:extend-module — fork-and-extend via amil-extend agent
- amil:index-modules — ChromaDB index build via amil_utils CLI
- amil:module-history — generation timeline from module_status.json
- amil:phases — ERP generation wave progress from ROADMAP.md

Total command count: 46 (34 renamed + 5 completed stubs + 7 new)"
```

---

## Chunk 4: Documentation & Verification

### Task 7: Rebuild CLAUDE.md Files

**Files:**
- Modify: `CLAUDE.md` (root)
- Modify: `orchestrator/CLAUDE.md`
- Modify: `pipeline/CLAUDE.md`

- [ ] **Step 1: Update root CLAUDE.md**

The sed script already changed most references. Manually verify and fix the Key Paths table and any remaining issues:

Verify these paths are correct in root `CLAUDE.md`:
```
| Orchestrator lib | `orchestrator/amil/bin/lib/` |
| Commands | `orchestrator/commands/amil/` |
| Workflows | `orchestrator/amil/workflows/` |
| Python src | `pipeline/python/src/amil_utils/` |
| Templates 17.0 | `pipeline/python/src/amil_utils/templates/17.0/` |
| Templates 18.0 | `pipeline/python/src/amil_utils/templates/18.0/` |
| Templates 19.0 | `pipeline/python/src/amil_utils/templates/19.0/` |
| Templates shared | `pipeline/python/src/amil_utils/templates/shared/` |
| Auto-fix | `pipeline/python/src/amil_utils/auto_fix.py` |
| MCP server | `pipeline/python/src/amil_utils/mcp/server.py` |
| Renderer context | `pipeline/python/src/amil_utils/renderer_context.py` |
```

The sed script should have handled all of these. Read the file and verify.

- [ ] **Step 2: Rewrite orchestrator CLAUDE.md**

The sed script changed inline references, but the file needs structural updates. Replace the full content of `orchestrator/CLAUDE.md` with:

```markdown
# Amil — Odoo ERP Module Orchestrator

An orchestration system built on Claude Code for generating, validating, and shipping cross-module-consistent Odoo ERP modules.

## Architecture

### Core Value
Cross-module coherence: every generated Odoo module must be referentially consistent with all other modules in the project (model references, security rules, menu hierarchies, view inheritance).

### Module Lifecycle
```
planned -> spec_approved -> generated -> checked -> shipped
```
Modules progress through these states sequentially. Only one module generates at a time (the amil belt needs exclusive Docker access).

### State Files (.planning/)
| File | Purpose |
|------|---------|
| `config.json` | Profile, workflow toggles, branching strategy |
| `STATE.md` | Current position, decisions, blockers, session continuity |
| `ROADMAP.md` | Phase definitions, plan progress tables |
| `PROJECT.md` | Core value, key decisions, project identity |
| `REQUIREMENTS.md` | Requirement traceability with completion status |
| `model_registry.json` | Central registry of all Odoo models across modules |
| `module_status.json` | Per-module lifecycle state tracking |

### CLI Tool
```bash
node amil/bin/amil-tools.cjs <command> [args] [--raw] [--cwd <path>]
```

Key commands: `state`, `resolve-model`, `find-phase`, `commit`, `verify-summary`, `roadmap`, `requirements`, `phase`, `validate`, `init`, `frontmatter`, `template`, `scaffold`, `progress`.

### Directory Structure
```
amil/
  bin/
    amil-tools.cjs    # CLI entry point
    install.js         # Claude-Code-only installer
    lib/               # CJS modules (core, state, phase, config, etc.)
  workflows/           # Workflow definitions (execute-plan, plan-phase, etc.)
  references/          # Reference docs (checkpoints, git integration, etc.)
  templates/           # Document templates (summary, plan, project, etc.)
commands/amil/         # Slash commands (/amil:*)
agents/                # Agent definitions (amil-*.md)
hooks/                 # Hook scripts (amil-*.js)
tests/                 # Test suite (*.test.cjs)
```

## Command Reference

All commands use the `/amil:` prefix (46 total):

### Project Lifecycle
| Command | Purpose |
|---------|---------|
| `/amil:new-project` | Initialize a new Amil project |
| `/amil:new-milestone` | Start a new milestone cycle |
| `/amil:complete-milestone` | Archive completed milestone |
| `/amil:audit-milestone` | Audit milestone completion |
| `/amil:plan-milestone-gaps` | Create phases for milestone gaps |

### Phase Workflow
| Command | Purpose |
|---------|---------|
| `/amil:research-phase` | Research before planning |
| `/amil:discuss-phase` | Gather context through questions |
| `/amil:plan-phase` | Create detailed phase plan |
| `/amil:execute-phase` | Execute phase plans |
| `/amil:validate-phase` | Validate phase consistency |
| `/amil:verify-work` | Verify completed work via UAT |
| `/amil:add-tests` | Generate tests for completed phase |

### Phase Management
| Command | Purpose |
|---------|---------|
| `/amil:add-phase` | Add phase to end of milestone |
| `/amil:insert-phase` | Insert urgent phase between existing |
| `/amil:remove-phase` | Remove future phase |
| `/amil:list-phase-assumptions` | Surface assumptions about a phase |

### ERP Module Generation
| Command | Purpose |
|---------|---------|
| `/amil:new-erp` | Initialize ERP project from PRD |
| `/amil:discuss-module` | Interactive module discussion |
| `/amil:plan-module` | Generate spec.json for module |
| `/amil:generate-module` | Generate module from spec.json |
| `/amil:validate-module` | pylint-odoo + Docker validation |
| `/amil:search-modules` | Semantic search for existing modules |
| `/amil:research-module` | Research patterns for module need |
| `/amil:extend-module` | Fork and extend existing module |
| `/amil:index-modules` | Build/update ChromaDB module index |

### Automation & Reporting
| Command | Purpose |
|---------|---------|
| `/amil:run-prd` | Full PRD-to-ERP generation cycle |
| `/amil:batch-discuss` | Auto-discuss underspecified modules |
| `/amil:coherence-report` | Cross-module coherence analysis |
| `/amil:live-uat` | Browser-based UAT verification |
| `/amil:module-history` | Generation history timeline |
| `/amil:phases` | Generation phases and progress |

### Utility
| Command | Purpose |
|---------|---------|
| `/amil:progress` | Show project progress |
| `/amil:quick` | Quick single-task execution |
| `/amil:health` | Check project health |
| `/amil:debug` | Systematic debugging |
| `/amil:map-codebase` | Analyze codebase with parallel agents |
| `/amil:cleanup` | Archive completed phase directories |
| `/amil:update` | Update Amil to latest version |
| `/amil:reapply-patches` | Reapply local modifications after update |
| `/amil:set-profile` | Switch model profile |
| `/amil:settings` | Configure workflow toggles |
| `/amil:help` | Show all commands |

### Session Management
| Command | Purpose |
|---------|---------|
| `/amil:pause-work` | Create context handoff |
| `/amil:resume-work` | Resume from previous session |
| `/amil:add-todo` | Capture task as todo |
| `/amil:check-todos` | List pending todos |

## Rules

1. **Sequential generation only** -- one module at a time through the belt
2. **All state changes through CLI subcommands** -- never edit STATE.md or config.json manually
3. **Atomic writes for JSON state** -- write complete files, never partial updates
4. **Immutable data patterns** -- create new objects, never mutate existing
5. **CJS module format** -- all lib modules use CommonJS (require/module.exports)
6. **Zero npm runtime dependencies** -- only Node.js built-ins at runtime

## Development

### Running Tests
```bash
npm test                    # Run all tests
npm run test:coverage       # Run with coverage (80%+ required)
```

### Test Structure
- Tests are in `tests/*.test.cjs`
- Test helpers in `tests/helpers.cjs`
- `TOOLS_PATH` points to `amil/bin/amil-tools.cjs`
- Tests create temp directories, never modify the real project

### Code Quality
- Functions under 50 lines
- Files under 800 lines
- No deep nesting (max 4 levels)
- No hardcoded secrets
- Proper error handling at every level
```

- [ ] **Step 3: Rewrite pipeline CLAUDE.md**

Replace full content of `pipeline/CLAUDE.md` with:

```markdown
# Odoo Module Automation — Pipeline Component

## Architecture

Pipeline is a **pure library** — no user-facing commands. All user interaction flows through the orchestrator's `/amil:` commands.

```
Layer 1: Orchestrator (Factory de Odoo)
  Context management, state, phases, agents, checkpoints, git
  All /amil: commands live here

Layer 2: Pipeline (THIS COMPONENT)
  Agents, templates, knowledge base — invoked by orchestrator

Layer 3: Python Utilities (amil-utils)
  Jinja2 rendering, pylint-odoo, Docker validation, ChromaDB search
```

## Pipeline Agents

Invoked by orchestrator commands, not directly by users:

| Agent | Invoked By | Purpose |
|-------|-----------|---------|
| `amil-scaffold` | `amil:generate-module` | Quick-mode module scaffolding |
| `amil-validator` | `amil:validate-module` | pylint-odoo + Docker validation |
| `amil-model-gen` | `amil:generate-module` | OCA-compliant model methods |
| `amil-view-gen` | `amil:generate-module` | Form/list/search XML views |
| `amil-security-gen` | `amil:generate-module` | Security CSV + record rules |
| `amil-test-gen` | `amil:generate-module` | Unit/integration tests |
| `amil-search` | `amil:search-modules` | Semantic OCA/GitHub search |
| `amil-extend` | `amil:extend-module` | Fork-and-extend with _inherit |
| `amil-logic-writer` | `amil:generate-module` | Business logic implementation |

## Python Utilities (amil-utils)

```bash
python -m amil_utils <subcommand>
```

Key subcommands: `render-module`, `validate`, `index-oca`, `search`, `auto-fix`

**Package:** `pipeline/python/src/amil_utils/`
**Config:** `pipeline/python/pyproject.toml`
**Tests:** `pipeline/python/tests/` (70+ test files)

## Key Decisions
| Decision | Rationale | Status |
|----------|-----------|--------|
| Pure library — no user-facing commands | All interaction through orchestrator /amil: commands | Decided |
| Odoo 19.0 primary target | Latest stable, backward compatible with 17.0/18.0 | Decided |
| Fork-and-extend strategy | Leverage existing OCA/GitHub modules | Decided |
| Semantic search (ChromaDB + ONNX) | Intent-based matching | Decided |
| Python 3.12 | Odoo 17.0-19.0 supports 3.10-3.12 | Decided |
| Docker for validation | Only way to truly verify installs/tests | Decided |
| OCA quality bar | pylint-odoo, i18n, full security, tests | Decided |

## Development

```bash
cd pipeline/python
pytest                          # Run all tests
pytest --cov=amil_utils         # With coverage
```

---
*Pipeline is a library component of Factory de Odoo. See orchestrator/CLAUDE.md for the full command reference.*
```

- [ ] **Step 4: Commit CLAUDE.md rebuilds**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add CLAUDE.md orchestrator/CLAUDE.md pipeline/CLAUDE.md
git commit -m "docs: rebuild CLAUDE.md files for amil rebrand

- Root CLAUDE.md: updated all key paths to amil/ and amil_utils/
- Orchestrator CLAUDE.md: full rewrite with 46-command reference table
- Pipeline CLAUDE.md: simplified to pure library docs (no commands section)"
```

### Task 8: Verification

- [ ] **Step 1: Run orchestrator tests**

```bash
cd /home/inshal-rauf/Factory-de-Odoo/orchestrator
npm test 2>&1 | tail -20
```

Expected: All tests pass (797 tests). Some tests may fail due to renamed paths — fix any failures before proceeding.

**Common fixes if tests fail:**
- `TOOLS_PATH` in `tests/helpers.cjs` should point to `amil/bin/amil-tools.cjs`
- Test fixtures referencing `odoo-gsd` should have been caught by sed
- If a test creates temp directories with old names, update the test

- [ ] **Step 2: Run pipeline tests**

```bash
cd /home/inshal-rauf/Factory-de-Odoo/pipeline/python
python -m pytest --tb=short 2>&1 | tail -30
```

Expected: Tests pass (excluding pre-existing failures). Watch for import errors on `amil_utils`.

**Common fixes if tests fail:**
- `import odoo_gen_utils` should be `import amil_utils` (sed handles this)
- `conftest.py` fixtures referencing old paths
- Test files importing from old package name

- [ ] **Step 3: Grep audit — verify zero remaining old brand references**

```bash
cd /home/inshal-rauf/Factory-de-Odoo

echo "=== Checking for odoo-gsd: ==="
grep -r --include='*.md' --include='*.js' --include='*.cjs' --include='*.json' \
  --include='*.py' --include='*.toml' --include='*.sh' --include='*.yml' \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=__pycache__ \
  'odoo-gsd' . | grep -v 'docs/superpowers/' | grep -v '.egg-info' | head -20

echo "=== Checking for odoo-gen (not odoo platform) ==="
grep -r --include='*.md' --include='*.js' --include='*.cjs' --include='*.json' \
  --include='*.py' --include='*.toml' --include='*.sh' --include='*.yml' \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=__pycache__ \
  'odoo-gen' . | grep -v 'docs/superpowers/' | grep -v '.egg-info' | head -20

echo "=== Checking for gsd: (command prefix) ==="
grep -r --include='*.md' --include='*.js' --include='*.cjs' --include='*.json' \
  --include='*.py' --include='*.toml' --include='*.sh' --include='*.yml' \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=__pycache__ \
  'gsd:' . | grep -v 'docs/superpowers/' | grep -v '.egg-info' | head -20

echo "=== Checking for odoo_gen_utils ==="
grep -r --include='*.py' --include='*.toml' --include='*.cfg' \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=__pycache__ \
  'odoo_gen_utils' . | grep -v '.egg-info' | head -20

echo "=== Checking for standalone GSD (word boundary) ==="
grep -rw --include='*.md' --include='*.js' --include='*.cjs' \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=__pycache__ \
  'GSD' . | grep -v 'docs/superpowers/' | grep -v '.egg-info' | head -20

echo "=== Checking for ODOO_GEN (uppercase, not caught by lowercase sed) ==="
grep -r --include='*.sh' --include='*.js' --include='*.py' \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=__pycache__ \
  'ODOO_GEN' . | grep -v 'docs/superpowers/' | grep -v '.egg-info' | head -20

echo "=== Checking extensionless files ==="
grep -r 'odoo' pipeline/bin/amil-utils 2>/dev/null | head -5
```

Expected: Zero matches for all 7 checks (excluding `docs/superpowers/` which is intentionally preserved). Note: `ODOO_GEN_DIR` variable name in `install.sh` is cosmetic (variable gets value from `SCRIPT_DIR`) — acceptable if found.

**If matches found:** Fix each remaining reference manually, then re-run the grep.

- [ ] **Step 4: Verify all command name: frontmatter uses amil: prefix**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
echo "=== Commands missing amil: prefix ==="
for f in orchestrator/commands/amil/*.md; do
  NAME=$(grep '^name:' "$f" | head -1 | sed 's/name: *//')
  if [[ ! "$NAME" == amil:* ]]; then
    echo "BAD: $f has name: $NAME"
  fi
done
echo "=== Total commands ==="
ls orchestrator/commands/amil/*.md | wc -l
```

Expected: No BAD lines, 46 total commands.

- [ ] **Step 5: Commit any test/audit fixes**

If Steps 1-4 revealed issues that needed fixing:

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git add -A
git commit -m "fix: resolve remaining brand references found in grep audit

Clean up any references missed by the bulk sed replacement."
```

Skip this step if no fixes were needed.

- [ ] **Step 6: Final verification commit**

```bash
cd /home/inshal-rauf/Factory-de-Odoo
git log --oneline -10
```

Expected commit history (newest first):
```
fix: resolve remaining brand references (if needed)
docs: rebuild CLAUDE.md files for amil rebrand
feat: create 7 new commands migrated from pipeline
feat: complete 4 stub commands and fix reapply-patches frontmatter
refactor: delete pipeline commands/workflows and join-discord
refactor: apply 23 string replacement patterns for amil rebrand
refactor: rename all odoo-gsd/odoo-gen files and directories to amil
feat: complete Odoo 19.0 upgrade
```

---

## Execution Notes

### Order Matters
Tasks MUST be executed in order. The sed script (Task 3) depends on git mv (Task 2) completing first. Command content (Tasks 5-6) depends on sed running first (to have correct paths in workflow references). CLAUDE.md rebuilds (Task 7) should be last content change before verification.

### Rollback
If anything goes catastrophically wrong:
```bash
git reset --hard pre-amil-rebrand
```

### Known Edge Cases
1. **Pattern 12 `odoo-gen` is broad** — verify it didn't match inside unrelated words (e.g., `odoo-generic`). The grep audit in Task 8 Step 3 catches false positives.
2. **Pattern 22 `gsd:` catches everything with that prefix** — including YAML `name:` fields that already have `gsd:` (like `cleanup.md`). This is correct behavior.
3. **Pattern 23 `\bGSD\b` requires GNU sed** — the `-E` flag enables extended regex with `\b` word boundaries. Verify with `sed --version` that GNU sed is installed.
4. **Python imports** — the sed changes `from odoo_gen_utils` → `from amil_utils` and `import odoo_gen_utils` → `import amil_utils`. Verify no import errors in pytest.
5. **`.planning/` files** — brand references in STATE.md, PROJECT.md, ROADMAP.md, REQUIREMENTS.md are renamed. This is intentional per spec Section 7.
6. **`cleanup.md` already has content** — it is NOT a true stub. It has objective, execution_context, and process sections. The sed handles renaming its `name: gsd:cleanup` → `name: amil:cleanup` and workflow path. No manual completion needed.
7. **`pipeline/bin/amil-utils` is extensionless** — the main sed find command won't catch it. A dedicated sed step handles it separately (see Task 3 Step 1).
8. **`ODOO_GEN_DIR` variable name in `install.sh`** — this uppercase+underscore variable name doesn't match any sed pattern. The variable itself is cosmetic (gets value from `SCRIPT_DIR`). Acceptable to leave as-is.
