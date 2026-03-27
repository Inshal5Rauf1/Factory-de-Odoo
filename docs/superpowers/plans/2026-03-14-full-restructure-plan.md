# Full Project Restructure Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure Factory-de-Odoo to mirror the `~/.claude/` install layout, consolidate all 28 agents, and ensure `install.py` installs everything.

**Architecture:** File moves via `git mv` (preserves history), followed by content updates to install.py, CLAUDE.md, README.md, .gitignore. No logic changes — only structure and naming. The Python package internal layout (`src/amil_utils/`) is unchanged.

**Tech Stack:** Git, Python 3.12, pytest, uv

**Spec:** `docs/superpowers/specs/2026-03-14-full-restructure-design.md`

---

## Chunk 1: File Moves (Tasks 1-5)

### Task 1: Move Python Package and Verify Tests

The Python package moves from `pipeline/python/` to `python/`. This is the highest-risk move because all 2,953 tests must still pass afterward. The internal layout of `src/amil_utils/` is unchanged, so all imports remain valid.

**Files:**
- Move: `pipeline/python/` → `python/` (321 tracked files)

- [ ] **Step 1: Clean build artifacts before moving**

```bash
find pipeline/python -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
rm -rf pipeline/python/.pytest_cache pipeline/python/.coverage
```

- [ ] **Step 2: Move the Python package directory**

```bash
git mv pipeline/python python
```

- [ ] **Step 3: Recreate venv and install in new location**

```bash
cd python && uv venv --python 3.12 && uv pip install -e ".[dev]" && cd ..
```

- [ ] **Step 4: Run full test suite to verify nothing broke**

```bash
cd python && uv run pytest tests/ -m "not docker" --tb=short -q && cd ..
```

Expected: All tests pass. If any fail, the move broke something — investigate before continuing.

- [ ] **Step 5: Verify CLI still works**

```bash
cd python && uv run amil-utils --help && uv run amil-utils orch --help && cd ..
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: move Python package from pipeline/python/ to python/

Internal layout (src/amil_utils/) unchanged. All imports and
test paths preserved. pyproject.toml relative paths still valid."
```

---

### Task 2: Consolidate All 28 Agents into agents/

Move 19 orchestrator agents and 9 pipeline agents into a single `agents/` directory at root.

**Files:**
- Move: `orchestrator/agents/amil-*.md` (19 files) → `agents/`
- Move: `pipeline/agents/amil-*.md` (9 files) → `agents/`

- [ ] **Step 1: Create root agents directory and move orchestrator agents**

```bash
mkdir -p agents
git mv orchestrator/agents/amil-*.md agents/
```

- [ ] **Step 2: Move pipeline agents to same directory**

```bash
git mv pipeline/agents/amil-*.md agents/
```

- [ ] **Step 3: Verify all 28 agents present**

```bash
ls agents/amil-*.md | wc -l
```

Expected: `28`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: consolidate all 28 agents into agents/

Merged orchestrator/agents/ (19) and pipeline/agents/ (9) into
a single flat directory. All agents now installable by install.py."
```

---

### Task 3: Move amil/ Content (Workflows, References, Templates, Knowledge, Defaults)

Move the `orchestrator/amil/` tree to root `amil/`, add knowledge files and defaults.json. Apply the 4 renames.

**Files:**
- Move: `orchestrator/amil/workflows/` (41 files) → `amil/workflows/`
- Move: `orchestrator/amil/references/` (14 files) → `amil/references/`
- Move: `orchestrator/amil/templates/` (36 files) → `amil/templates/`
- Move: `pipeline/knowledge/` (13 files) → `amil/knowledge/`
- Move: `pipeline/defaults.json` → `amil/defaults.json`
- Rename: `DEBUG.md` → `debug.md`, `UAT.md` → `uat.md`, `VALIDATION.md` → `validation.md`
- Rename: `ralph-loop.md` → `autonomous-erp-loop.md`

- [ ] **Step 1: Move the orchestrator/amil tree to root**

```bash
git mv orchestrator/amil amil
```

- [ ] **Step 2: Move knowledge files into amil/**

```bash
git mv pipeline/knowledge amil/knowledge
```

- [ ] **Step 3: Move defaults.json into amil/**

```bash
git mv pipeline/defaults.json amil/defaults.json
```

- [ ] **Step 4: Rename UPPERCASE templates to lowercase**

```bash
git mv amil/templates/DEBUG.md amil/templates/debug.md
git mv amil/templates/UAT.md amil/templates/uat.md
git mv amil/templates/VALIDATION.md amil/templates/validation.md
```

- [ ] **Step 5: Rename ralph-loop.md to self-documenting name**

```bash
git mv amil/workflows/ralph-loop.md amil/workflows/autonomous-erp-loop.md
```

- [ ] **Step 6: Verify counts**

```bash
echo "Workflows: $(ls amil/workflows/*.md | wc -l)"
echo "References: $(ls amil/references/ | wc -l)"
echo "Templates: $(find amil/templates -type f | wc -l)"
echo "Knowledge: $(find amil/knowledge -type f | wc -l)"
```

Expected: Workflows: 41, References: 14, Templates: ~36, Knowledge: 13

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: move amil/ content to root, add knowledge + defaults

- orchestrator/amil/ → amil/ (workflows, references, templates)
- pipeline/knowledge/ → amil/knowledge/ (preserves agent @include paths)
- pipeline/defaults.json → amil/defaults.json
- Renamed: DEBUG.md→debug.md, UAT.md→uat.md, VALIDATION.md→validation.md
- Renamed: ralph-loop.md → autonomous-erp-loop.md"
```

---

### Task 4: Move Commands and Hooks

**Files:**
- Move: `orchestrator/commands/amil/` (46 files) → `commands/amil/`
- Move: `orchestrator/hooks/` (3 files) → `hooks/`

- [ ] **Step 1: Move commands**

```bash
mkdir -p commands
git mv orchestrator/commands/amil commands/amil
```

- [ ] **Step 2: Move hooks**

```bash
git mv orchestrator/hooks hooks
```

- [ ] **Step 3: Verify counts**

```bash
echo "Commands: $(ls commands/amil/*.md | wc -l)"
echo "Hooks: $(ls hooks/amil-*.py | wc -l)"
```

Expected: Commands: 46, Hooks: 3

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: move commands/ and hooks/ to root

- orchestrator/commands/amil/ → commands/amil/ (46 commands)
- orchestrator/hooks/ → hooks/ (3 hooks)"
```

---

### Task 5: Move Remaining Files (Docker, Scripts, Assets, Docs, GitHub, Root Docs)

**Files:**
- Move: `pipeline/docker/` → `docker/`
- Move: `pipeline/scripts/` → `scripts/`
- Move: `orchestrator/assets/` → `assets/`
- Move: `orchestrator/docs/` → `docs/` (merge with existing docs/)
- Move: `orchestrator/.github/` → `.github/`
- Move: `orchestrator/CHANGELOG.md` → `CHANGELOG.md`
- Move: `orchestrator/SECURITY.md` → `SECURITY.md`
- Move: `orchestrator/LICENSE` → `LICENSE`
- Move: `pipeline/CONTRIBUTING.md` → `CONTRIBUTING.md`
- Move: `pipeline/.mcp.json` → `.mcp.json`

- [ ] **Step 1: Move docker and scripts**

```bash
git mv pipeline/docker docker
git mv pipeline/scripts scripts
```

- [ ] **Step 2: Move assets**

```bash
git mv orchestrator/assets assets
```

- [ ] **Step 3: Move orchestrator docs into existing docs/**

The `docs/` directory already exists (contains `superpowers/specs/`). Move the orchestrator docs into it.

```bash
git mv orchestrator/docs/context-monitor.md docs/context-monitor.md
git mv orchestrator/docs/USER-GUIDE.md docs/USER-GUIDE.md
```

- [ ] **Step 4: Move GitHub config**

```bash
git mv orchestrator/.github .github
```

- [ ] **Step 5: Move root-level docs**

```bash
git mv orchestrator/CHANGELOG.md CHANGELOG.md
git mv orchestrator/SECURITY.md SECURITY.md
git mv orchestrator/LICENSE LICENSE
git mv pipeline/CONTRIBUTING.md CONTRIBUTING.md
git mv pipeline/.mcp.json .mcp.json
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: move docker, scripts, assets, docs, .github to root

- pipeline/docker/ → docker/
- pipeline/scripts/ → scripts/
- orchestrator/assets/ → assets/
- orchestrator/docs/ → docs/
- orchestrator/.github/ → .github/
- Root docs: CHANGELOG.md, SECURITY.md, LICENSE, CONTRIBUTING.md, .mcp.json"
```

---

## Chunk 2: Content Updates (Tasks 6-8)

### Task 6: Update install.py

Move `orchestrator/install.py` to root and rewrite `INSTALL_DIRS`, `PIPELINE_PYTHON`, and error messages.

**Files:**
- Move + Modify: `orchestrator/install.py` → `install.py`

- [ ] **Step 1: Move install.py to root**

```bash
git mv orchestrator/install.py install.py
```

- [ ] **Step 2: Update INSTALL_DIRS**

Replace the `INSTALL_DIRS` dictionary. Old:

```python
INSTALL_DIRS = {
    "amil": "amil",
    "commands/amil": "commands/amil",
    "agents": "agents",
    "hooks": "hooks",
}
```

New:

```python
INSTALL_DIRS = {
    "agents": "agents",
    "amil": "amil",
    "commands": "commands",
    "hooks": "hooks",
}
```

- [ ] **Step 3: Update PIPELINE_PYTHON path**

Replace:
```python
PIPELINE_PYTHON = SOURCE_ROOT / "pipeline" / "python" if (SOURCE_ROOT / "pipeline").exists() else SOURCE_ROOT.parent / "pipeline" / "python"
```

With:
```python
PIPELINE_PYTHON = SOURCE_ROOT / "python"
```

- [ ] **Step 4: Update error message**

Replace `pip install -e pipeline/python` with `pip install -e python` in the error messages (2 occurrences).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: update install.py for new directory structure

- INSTALL_DIRS now covers agents, amil (incl knowledge), commands, hooks
- PIPELINE_PYTHON simplified to python/ (no more pipeline/ prefix)
- Error messages updated with new paths"
```

---

### Task 7: Merge CLAUDE.md, Update README.md, CONTRIBUTING.md

Rewrite CLAUDE.md by merging content from all three existing files with updated paths. Update README.md and CONTRIBUTING.md path references.

**Files:**
- Rewrite: `CLAUDE.md` (merge 3 sources)
- Modify: `README.md` (update paths)
- Modify: `CONTRIBUTING.md` (update paths)

- [ ] **Step 1: Read all three CLAUDE.md files and merge**

Read:
- `CLAUDE.md` (root — current, already in place)
- Content from the now-deleted `orchestrator/CLAUDE.md` and `pipeline/CLAUDE.md` is captured in the design spec section "CLAUDE.md Merge Strategy"

Rewrite `CLAUDE.md` with these sections (all paths updated):
1. Compact Instructions (unchanged)
2. Project — repo URL, purpose, branch
3. Architecture — `orchestrator/` and `pipeline/` replaced with new layout
4. Key Paths table — all paths updated per spec
5. Current State
6. CLI reference
7. Pipeline Agents table
8. Odoo Patterns
9. Rules
10. Development — `cd python && uv run pytest tests/ -q`

- [ ] **Step 2: Update README.md paths**

Search and replace in `README.md`:
- `pipeline/python/src/amil_utils/` → `python/src/amil_utils/`
- `pipeline/python/tests/` → `python/tests/`
- `pipeline/knowledge/` → `amil/knowledge/`
- `orchestrator/agents/` → `agents/`
- `orchestrator/amil/workflows/` → `amil/workflows/`
- `orchestrator/commands/amil/` → `commands/amil/`
- `orchestrator/hooks/` → `hooks/`
- `pipeline/python/src/amil_utils/orchestrator/` → `python/src/amil_utils/orchestrator/`
- `pipeline/python/src/amil_utils/templates/` → `python/src/amil_utils/templates/`
- `cd pipeline/python` → `cd python`
- `pipeline/CONTRIBUTING.md` → `CONTRIBUTING.md`
- `orchestrator/assets/factory-logo.svg` → `assets/factory-logo.svg`
- Architecture tree diagram — rewrite with new structure

- [ ] **Step 3: Update CONTRIBUTING.md paths**

Search and replace:
- `pipeline/python/` → `python/`
- Any references to `orchestrator/` or `pipeline/` directories

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md CONTRIBUTING.md && git commit -m "docs: merge CLAUDE.md, update README and CONTRIBUTING paths

- CLAUDE.md: three-way merge from root + orchestrator + pipeline
- README.md: all paths updated for new structure
- CONTRIBUTING.md: development paths updated"
```

---

### Task 8: Merge .gitignore, Update CI Workflow, Update odoo-dev.sh

**Files:**
- Rewrite: `.gitignore` (three-way merge)
- Rewrite: `.github/workflows/test.yml` (CJS → Python)
- Modify: `scripts/odoo-dev.sh` (path reference already correct — `SCRIPT_DIR` relative)

- [ ] **Step 1: Merge .gitignore**

The current root `.gitignore` is the base. Merge in relevant patterns from:
- `orchestrator/.gitignore` — drop CJS patterns (node_modules, hooks/dist/, etc.), keep nothing (all CJS-specific)
- `pipeline/.gitignore` — keep: `docker/dev/.env`

Add to root `.gitignore`:
```
# Docker dev environment
docker/dev/.env
```

The existing root `.gitignore` already covers: `__pycache__/`, `*.pyc`, `*.egg-info/`, `.venv/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `.planning/phases/`, `.planning/research/`, `pgdata/`, `*.log`

- [ ] **Step 2: Rewrite .github/workflows/test.yml for Python**

The current `test.yml` runs Node.js tests (npm ci, npm test) — completely wrong post-unification. Rewrite for Python:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        working-directory: python
        run: |
          uv venv --python 3.12
          uv pip install -e ".[dev]"

      - name: Run tests
        working-directory: python
        run: uv run pytest tests/ -m "not docker and not e2e" --tb=short -q
```

- [ ] **Step 3: Verify scripts/odoo-dev.sh needs no changes**

The script uses `SCRIPT_DIR` and `PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"` to build paths. After the move, `scripts/` is at root and `docker/dev/docker-compose.yml` is at root — so `PROJECT_ROOT/docker/dev/docker-compose.yml` resolves correctly. No changes needed.

- [ ] **Step 4: Commit**

```bash
git add .gitignore .github/workflows/test.yml && git commit -m "chore: merge .gitignore, rewrite CI for Python

- .gitignore: three-way merge, dropped CJS patterns, added docker/dev/.env
- test.yml: replaced Node.js CI with Python 3.12 + uv + pytest"
```

---

## Chunk 3: Cleanup and Final Deliverables (Tasks 9-11)

### Task 9: Delete Stale Files and Empty Directories

Remove files superseded by the restructure and clean up empty directories.

**Files to delete:**
- `pipeline/.continue-here.md`
- `pipeline/python/uni_fee/` (directory with 2 .mmd files)
- `pipeline/bin/amil-utils`
- `pipeline/VERSION`
- `pipeline/install.sh`

**Directories to remove (now empty):**
- `orchestrator/` (all contents moved)
- `pipeline/` (all contents moved)

- [ ] **Step 1: Delete stale tracked files**

```bash
git rm pipeline/.continue-here.md
git rm pipeline/VERSION
git rm pipeline/install.sh
git rm pipeline/bin/amil-utils
```

- [ ] **Step 2: Delete untracked/gitignored items**

```bash
rm -rf pipeline/python/uni_fee
```

- [ ] **Step 3: Remove empty directories**

After all `git mv` and `git rm` operations, check for and remove empty directories:

```bash
find orchestrator -type d -empty -delete 2>/dev/null; true
find pipeline -type d -empty -delete 2>/dev/null; true
rmdir orchestrator 2>/dev/null; true
rmdir pipeline 2>/dev/null; true
```

If `orchestrator/` or `pipeline/` still have untracked content (like `.planning/` or `.venv/`), remove them:

```bash
rm -rf orchestrator/.planning pipeline/.planning pipeline/python/.planning
rm -rf pipeline/.venv pipeline/python/.venv
rm -rf orchestrator pipeline
```

- [ ] **Step 4: Verify both directories are gone**

```bash
ls -d orchestrator/ 2>/dev/null && echo "ERROR: orchestrator/ still exists" || echo "OK: orchestrator/ removed"
ls -d pipeline/ 2>/dev/null && echo "ERROR: pipeline/ still exists" || echo "OK: pipeline/ removed"
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: delete stale files and empty directories

Removed: .continue-here.md, VERSION, install.sh, bin/amil-utils,
uni_fee/, orchestrator/, pipeline/"
```

---

### Task 10: Create CONVENTIONS.md

Create the naming and structure conventions reference at project root.

**Files:**
- Create: `CONVENTIONS.md`

- [ ] **Step 1: Write CONVENTIONS.md**

Create `CONVENTIONS.md` at project root with the content specified in the design spec (naming rules table, directory rules, file size limits). The exact content is defined in the spec under "CONVENTIONS.md Content".

- [ ] **Step 2: Commit**

```bash
git add CONVENTIONS.md && git commit -m "docs: create CONVENTIONS.md with naming and structure rules"
```

---

### Task 11: Full Verification

Run every item in the verification checklist.

- [ ] **Step 1: Verify Python package installs**

```bash
cd python && uv venv --python 3.12 && uv pip install -e ".[dev]" && cd ..
```

- [ ] **Step 2: Verify CLI**

```bash
cd python && uv run amil-utils --help && uv run amil-utils orch --help && cd ..
```

- [ ] **Step 3: Run full test suite**

```bash
cd python && uv run pytest tests/ -m "not docker" --tb=short -q && cd ..
```

- [ ] **Step 4: Verify install.py works**

```bash
python install.py 2>&1 | head -20
```

(May fail if `~/.claude/` doesn't exist — that's OK for verification. Check that it attempts to copy agents, amil, commands, hooks.)

- [ ] **Step 5: Verify agent count**

```bash
echo "Agents: $(ls agents/amil-*.md | wc -l)"
```

Expected: `28`

- [ ] **Step 6: Verify knowledge files**

```bash
echo "Knowledge: $(find amil/knowledge -type f | wc -l)"
```

Expected: `13`

- [ ] **Step 7: Grep for stale references**

```bash
grep -r "pipeline/" --include="*.md" --include="*.py" --include="*.yml" --include="*.json" . | grep -v ".git/" | grep -v ".venv/" | grep -v "superpowers/" | grep -v "CHANGELOG"
grep -r "orchestrator/" --include="*.md" --include="*.py" --include="*.yml" --include="*.json" . | grep -v ".git/" | grep -v ".venv/" | grep -v "superpowers/" | grep -v "CHANGELOG"
```

Expected: Zero results (excluding design specs and changelog which mention old paths as historical context).

- [ ] **Step 8: Verify CONVENTIONS.md exists**

```bash
test -f CONVENTIONS.md && echo "OK" || echo "MISSING"
```

- [ ] **Step 9: Verify test count**

```bash
cd python && uv run pytest tests/ --collect-only -q 2>/dev/null | tail -1 && cd ..
```

- [ ] **Step 10: Verify directory structure matches spec**

```bash
echo "=== Root directories ==="
ls -d */ .github/ 2>/dev/null | sort
echo "=== Expected: agents/ amil/ assets/ commands/ docker/ docs/ hooks/ python/ scripts/ ==="
```

- [ ] **Step 11: Final commit if any fixups needed**

If any verification steps required fixes, commit them:

```bash
git add -A && git status
# If changes exist:
git commit -m "fix: address verification issues from restructure"
```
