# Phase 1: Fork Foundation and State Infrastructure - Research

**Researched:** 2026-03-05
**Domain:** CLI fork renaming, JSON state management, graph algorithms, Node.js CJS
**Confidence:** HIGH

## Summary

Phase 1 transforms the Amil CLI into amil through systematic renaming of 233+ hardcoded references, then builds three new infrastructure modules: a model registry with atomic writes and rollback, a module status tracker with enforced lifecycle transitions, and a dependency graph with topological sort and circular dependency detection. The entire phase operates within Amil's zero-dependency Node.js CJS architecture using only built-in modules (fs, path, node:test, node:assert).

The codebase has been directly inspected. There are 98 files containing `get-shit-done`, `gsd-tools`, or `/amil:` references that need updating. The rename spans 6 distinct layers: directory paths (`get-shit-done/` directory), CLI tool name (`gsd-tools.cjs`), command prefix (`/amil:`), agent role names (`gsd-planner` etc in MODEL_PROFILES), config defaults (`gsd/phase-{phase}` branch templates), and documentation/templates. The 2464-line `bin/install.js` must be rewritten to support Claude Code only and add amil/Python checks.

The three new modules (registry.cjs ~400-600 LOC, module-status.cjs ~150-200 LOC, dependency-graph.cjs ~150-200 LOC) follow established Amil patterns: each exports functions consumed by `gsd-tools.cjs` via the CLI router, uses `output()`/`error()` from core.cjs, and operates on JSON files in `.planning/`. All are inline implementations with no npm dependencies -- topological sort is 20 LOC, atomic writes are 5 LOC, JSON validation is ~50 LOC.

**Primary recommendation:** Rename in strict layers (directory structure, then CLI entry point, then command prefix, then internal identifiers, then docs), verifying each layer with grep before proceeding. Build registry.cjs first as the keystone module, then module-status.cjs and dependency-graph.cjs which depend on its patterns.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FORK-01 | All 32 command files renamed from `/amil:` to `/amil:` prefix | 32 files in `commands/gsd/` directory need directory rename to `commands/amil/` and frontmatter prefix update |
| FORK-02 | All workflow files reference `amil` commands | 12+ workflow files in `get-shit-done/workflows/` with `gsd-tools` and `/amil:` references |
| FORK-03 | All agent files reference `amil` paths and commands | 12 agent files in `agents/` all prefixed `gsd-` with internal path references |
| FORK-04 | 233+ hardcoded path references renamed | 98 files identified containing old references across 6 layers |
| FORK-05 | `bin/install.js` rewritten for Claude Code only | 2464-line file currently supports 4 runtimes; strip to Claude Code only |
| FORK-06 | Install checks for amil at `~/.claude/amil/` | Add path existence check in install.js |
| FORK-07 | Install checks for Python 3.8+ | Add `python3 --version` check in install.js |
| FORK-08 | CLAUDE.md rewritten as Odoo ERP orchestrator context | New file; depends on knowing final command names |
| FORK-09 | package.json renamed to amil | Update name, description, repository, strip multi-runtime keywords |
| FORK-10 | Verification grep confirms zero remaining old references | Build verification script using `grep -r` for all old patterns |
| CONF-01 | Config extended with `odoo` config block schema | Extend `config.cjs` `cmdConfigEnsureSection` with odoo sub-object |
| CONF-02 | Odoo config validation rules enforced | Add validation functions for version (17.0/18.0), scope_levels array, belt path |
| REG-01 | Registry CRUD operations created | New `registry.cjs` with registryRead, registryReadModel, registryUpdate, registryValidate, registryStats |
| REG-02 | Atomic writes implemented | write-to-tmp + fs.renameSync pattern (5 LOC) |
| REG-03 | Registry versioning implemented | _meta.version counter, _meta.last_updated timestamp, _meta.modules_contributing list |
| REG-04 | Registry rollback implemented | .bak file preserved on each write, rollback restores from .bak |
| REG-05 | Registry validation checks | Many2one targets exist, no duplicate model names, required fields present |
| REG-06 | Registry stats command | Count models, fields, cross-module references |
| REG-07 | CLI subcommands registered | Add `registry read|read-model|update|rollback|validate|stats` to gsd-tools.cjs dispatcher |
| STAT-01 | module_status.json created | JSON file with per-module status and tier structure |
| STAT-02 | Status transitions enforced | State machine: planned -> spec_approved -> generated -> checked -> shipped |
| STAT-03 | Tier status computed | Aggregate module statuses per tier; tier complete when all modules shipped |
| STAT-04 | Per-module artifact directories | Create `.planning/modules/{module_name}/` with slot files |
| DEPG-01 | Dependency graph from manifests | Build adjacency list from module `depends` fields |
| DEPG-02 | Topological sort for generation order | Kahn's algorithm or DFS-based toposort (20 LOC) |
| DEPG-03 | Circular dependency detection | Track visiting set during DFS; throw with cycle path on detection |
| DEPG-04 | Tier grouping | Assign tiers (foundation/core/operations/communication) based on dependency depth |
| DEPG-05 | Generation blocked on dependency status | Check all depends modules are >= "generated" before allowing generation |
| TEST-01 | Registry tests | CRUD, atomic updates, rollback, cross-module validation, duplicate detection |
| TEST-02 | Module status tests | Status transitions, invalid transitions, tier completion |
| TEST-05 | Existing Amil tests updated | Update test helpers to use new tool path; fix assertions for renamed config |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Node.js | 25.5.0 | Runtime | Installed on system, Amil's native runtime |
| CJS (require/exports) | N/A | Module format | Amil's format throughout; no ESM conversion |
| fs (built-in) | N/A | File I/O, JSON state | All state is JSON files in `.planning/` |
| path (built-in) | N/A | Path resolution | Cross-platform path handling |
| node:test | 25.5.0 | Test framework | Built-in, zero dependencies, used by existing 16 tests |
| node:assert/strict | 25.5.0 | Assertions | Built-in, used by all existing tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| child_process (built-in) | N/A | Git ops, subprocess | For `execSync` git commits in install flow |
| os (built-in) | N/A | Home directory, temp dirs | `os.homedir()` for `~/.claude/` paths, `os.tmpdir()` for tests |
| c8 | ^11.0.0 | Coverage reporter | devDependency only; `npm run test:coverage` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual JSON validation | Zod/Ajv | Would add npm dependency; validation is Odoo-domain-specific (Many2one comodel rules) not expressible in generic schemas |
| Inline toposort (20 LOC) | `toposort` npm | 80 LOC package; not worth a dependency for basic DFS |
| fs.writeFileSync + renameSync | `write-file-atomic` | 150+ LOC package with uid/gid support unnecessary on Linux |

**Installation:**
```bash
# No npm install needed for runtime
git clone <repo> ~/.claude/amil
# Dev only (tests with coverage):
npm install  # installs c8 + esbuild devDependencies
```

## Architecture Patterns

### Recommended Project Structure
```
amil/                        # renamed from get-shit-done/
  bin/
    amil-tools.cjs           # renamed from gsd-tools.cjs (592 LOC + new registry/status/depgraph dispatch)
    lib/
      core.cjs                   # MODEL_PROFILES keys renamed (gsd-* -> amil-*)
      config.cjs                 # Extended with odoo config block (CONF-01, CONF-02)
      registry.cjs               # NEW: Model registry CRUD (~400-600 LOC)
      module-status.cjs          # NEW: Module lifecycle state machine (~150-200 LOC)
      dependency-graph.cjs       # NEW: Topological sort, tier grouping (~150-200 LOC)
      commands.cjs               # Existing, minor path updates
      state.cjs                  # Existing, minor path updates
      phase.cjs                  # Existing, minor path updates
      ... (other existing modules)
    install.js                   # Rewritten: Claude Code only + amil + Python checks
  workflows/                     # Renamed references within files
  references/                    # Renamed references within files
  templates/                     # Renamed references within files
commands/amil/               # renamed from commands/gsd/ (32 files)
agents/                          # Renamed gsd-* -> amil-* (12 files)
hooks/                           # Renamed gsd-* -> amil-* (3 files)
tests/
  helpers.cjs                   # Updated TOOLS_PATH
  registry.test.cjs             # NEW (TEST-01)
  module-status.test.cjs        # NEW (TEST-02)
  dependency-graph.test.cjs     # NEW (implied by DEPG requirements)
  ... (16 existing tests updated)
.planning/
  config.json                   # Extended with `odoo` block
  model_registry.json           # NEW: Central model state
  module_status.json            # NEW: Per-module lifecycle
  modules/                      # NEW: Per-module artifact dirs
    {module_name}/
      CONTEXT.md
      spec.json
      coherence-report.json
      generation-manifest.json
      check-report.json
```

### Pattern 1: CLI Router Dispatch (existing, extend)
**What:** `gsd-tools.cjs` dispatches subcommands to lib module functions. Each function takes `(cwd, ...args, raw)` and calls `output(result, raw, rawValue)` for JSON or `error(msg)` for failures.
**When to use:** Every new registry/status/depgraph CLI subcommand.
**Example:**
```javascript
// In amil-tools.cjs (extended dispatch table)
case 'registry':
  const registrySub = args[1];
  switch (registrySub) {
    case 'read':       return cmdRegistryRead(cwd, raw);
    case 'read-model': return cmdRegistryReadModel(cwd, args[2], raw);
    case 'update':     return cmdRegistryUpdate(cwd, args[2], raw);
    case 'rollback':   return cmdRegistryRollback(cwd, raw);
    case 'validate':   return cmdRegistryValidate(cwd, raw);
    case 'stats':      return cmdRegistryStats(cwd, raw);
    default: error(`Unknown registry subcommand: ${registrySub}`);
  }
  break;
```

### Pattern 2: Atomic JSON State Updates with Backup
**What:** All JSON state writes use write-to-tmp + rename, with .bak preservation for rollback.
**When to use:** Every write to model_registry.json, module_status.json.
**Example:**
```javascript
// Source: ARCHITECTURE.md research + Amil codebase patterns
function atomicWriteJSON(filePath, data) {
  const backupPath = filePath + '.bak';
  if (fs.existsSync(filePath)) {
    fs.copyFileSync(filePath, backupPath);
  }
  const tmpPath = filePath + '.tmp';
  fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
  fs.renameSync(tmpPath, filePath);
}
```

### Pattern 3: Module Status State Machine
**What:** Enforce valid lifecycle transitions: planned -> spec_approved -> generated -> checked -> shipped.
**When to use:** Every module status change triggered by workflow completion.
**Example:**
```javascript
const VALID_TRANSITIONS = {
  planned:        ['spec_approved'],
  spec_approved:  ['generated', 'planned'],    // can re-plan
  generated:      ['checked', 'spec_approved'], // can revise
  checked:        ['shipped'],
  shipped:        [],
};

function transitionModule(status, moduleName, newStatus) {
  const current = status.modules[moduleName]?.status || 'planned';
  const allowed = VALID_TRANSITIONS[current] || [];
  if (!allowed.includes(newStatus)) {
    throw new Error(
      `Invalid transition: ${moduleName} cannot go from "${current}" to "${newStatus}". ` +
      `Allowed: ${allowed.join(', ') || 'none'}`
    );
  }
  return {
    ...status,
    modules: {
      ...status.modules,
      [moduleName]: {
        ...status.modules[moduleName],
        status: newStatus,
        updated: new Date().toISOString(),
      },
    },
  };
}
```

### Pattern 4: DFS Topological Sort with Cycle Detection
**What:** Order modules by dependency depth; detect and report circular dependencies.
**When to use:** Determining generation order, computing tier assignments.
**Example:**
```javascript
// Source: STACK.md research
function topoSort(modules) {
  const visited = new Set();
  const visiting = new Set(); // cycle detection
  const sorted = [];

  function visit(name) {
    if (visiting.has(name)) {
      throw new Error(`Circular dependency detected involving: ${name}`);
    }
    if (visited.has(name)) return;
    visiting.add(name);
    for (const dep of modules[name]?.depends || []) {
      if (modules[dep]) visit(dep);
    }
    visiting.delete(name);
    visited.add(name);
    sorted.push(name);
  }

  for (const name of Object.keys(modules)) visit(name);
  return sorted;
}
```

### Pattern 5: Registry Schema
**What:** The model_registry.json structure that all CRUD operations work against.
**When to use:** Initializing empty registries, validating on read.
**Example:**
```javascript
// Empty registry structure
const EMPTY_REGISTRY = {
  _meta: {
    version: 0,
    last_updated: null,
    modules_contributing: [],
    odoo_version: '17.0',
  },
  models: {},
  // models keyed by Odoo model name (e.g., "university.student")
  // Each model: { name, module, fields: {}, _inherit: [], description }
  // Each field: { type, string, required, comodel_name?, inverse_name?, compute?, ... }
};
```

### Anti-Patterns to Avoid
- **Partial rename:** Renaming some references but missing others (especially MODEL_PROFILES keys in core.cjs, branch templates in config.cjs, and `.gsd/` home directory references). Always verify with grep after each rename layer.
- **Direct file mutation from workflows:** All registry/status operations must go through CLI subcommands, never through direct Read/Write tool calls in workflow markdown. This ensures atomic writes and version tracking.
- **Non-atomic writes:** Never use bare `fs.writeFileSync` for state files. Always use the write-tmp-rename pattern.
- **Mutable state objects:** Follow the immutability pattern from user rules -- return new objects from status transitions, don't mutate in place.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing/serialization | Custom parser | `JSON.parse` / `JSON.stringify` | Built into Node.js, handles all edge cases |
| File path resolution | String concatenation | `path.join()` / `path.resolve()` | Cross-platform separator handling |
| Temp directory creation | Manual mkdir | `fs.mkdtempSync(os.tmpdir())` | Guaranteed unique, OS-appropriate location |
| Test framework | Custom test runner | `node --test` | Built into Node.js 25, supports describe/it/beforeEach/mock |
| Coverage reporting | Custom instrumentation | `c8` (already a devDependency) | Already configured in package.json scripts |
| Atomic file writes | Transaction system | `fs.writeFileSync` + `fs.renameSync` | `renameSync` is atomic on Linux; 5 lines total |

**Key insight:** The zero-dependency constraint means every algorithm must be inline, but they are all simple enough (toposort=20 LOC, validation=50 LOC, atomic write=5 LOC) that libraries would add more complexity than they save.

## Common Pitfalls

### Pitfall 1: Incomplete Fork Rename (233+ References)
**What goes wrong:** Renaming most references but missing edge cases -- MODEL_PROFILES keys in core.cjs, branch templates in config.cjs defaults, `.gsd/` home directory references, `gsd-` prefixed tmp file names in output() function, test helper TOOLS_PATH.
**Why it happens:** 6 distinct reference pattern categories across 98 files. Simple find-replace produces false positives (e.g., `gsd` inside words like `amil` creates double-rename).
**How to avoid:** Build a rename manifest listing every pattern category. Rename in layers. Verify each layer with `grep -r` before proceeding. Final verification script must check ALL old patterns: `get-shit-done`, `gsd-tools`, `/amil:`, `gsd-planner`, `gsd-executor`, `gsd/phase-`, `.gsd/`.
**Warning signs:** Commands work in isolation but fail when workflows invoke sub-tools. Agent spawn with wrong role name. Branch names use old prefix.

### Pitfall 2: install.js Rewrite Scope Creep
**What goes wrong:** The 2464-line install.js supports 4 runtimes (Claude Code, OpenCode, Gemini CLI, Codex CLI) with detection, configuration, and settings management for each. Attempting to "simplify" it while preserving backward compatibility leads to a messy hybrid.
**Why it happens:** Fear of breaking existing installs. Desire to keep code "just in case."
**How to avoid:** Hard delete all non-Claude-Code runtime support. The requirement (FORK-05) is explicit: "rewritten for Claude Code only." Start from the Claude Code path and add amil + Python checks. Do not preserve OpenCode/Gemini/Codex paths.
**Warning signs:** Conditional runtime detection branches still present after rewrite. File still over 1000 lines.

### Pitfall 3: Registry Version vs Module Version Confusion
**What goes wrong:** The registry has `_meta.version` (incremented on every write). Modules have their own version in Odoo manifests. Developers confuse the two, leading to rollback of the wrong thing.
**Why it happens:** Both are called "version" and both increment.
**How to avoid:** Registry version is always `_meta.version` (integer, auto-incremented). Module version follows Odoo `__manifest__.py` convention (string like "17.0.1.0.0"). Keep them in different namespaces, never compare them.

### Pitfall 4: Test Helpers Pointing to Old Path
**What goes wrong:** `tests/helpers.cjs` has `TOOLS_PATH` pointing to `get-shit-done/bin/gsd-tools.cjs`. After rename, all 16 existing tests fail with ENOENT, not with assertion errors -- making it look like a Node.js problem rather than a path problem.
**Why it happens:** Test helpers are updated last because they are "just infrastructure."
**How to avoid:** Update `tests/helpers.cjs` TOOLS_PATH immediately after renaming the directory/file. Run existing tests as the smoke test for rename correctness.

### Pitfall 5: Config Extension Breaking Existing Defaults
**What goes wrong:** Adding the `odoo` block to config.cjs defaults causes existing tests to fail because they assert on the original default structure (e.g., `config.test.cjs` checks exact keys).
**Why it happens:** Tests are tightly coupled to the config shape.
**How to avoid:** Add the `odoo` block as an optional extension -- only present when explicitly initialized by `new-erp` command. The `config-ensure-section` creates the base config without the `odoo` block. A separate `config-set odoo.version 17.0` adds it.

## Code Examples

### Registry CRUD - Full Read
```javascript
// Source: Amil config.cjs pattern + ARCHITECTURE.md
function cmdRegistryRead(cwd, raw) {
  const registryPath = path.join(cwd, '.planning', 'model_registry.json');
  if (!fs.existsSync(registryPath)) {
    output({ models: {}, _meta: { version: 0 } }, raw);
    return;
  }
  try {
    const data = JSON.parse(fs.readFileSync(registryPath, 'utf-8'));
    output(data, raw);
  } catch (err) {
    // Attempt recovery from backup
    const bakPath = registryPath + '.bak';
    if (fs.existsSync(bakPath)) {
      const data = JSON.parse(fs.readFileSync(bakPath, 'utf-8'));
      output({ ...data, _recovered: true }, raw);
    } else {
      error('Registry corrupted and no backup available: ' + err.message);
    }
  }
}
```

### Registry Validation
```javascript
// Source: STACK.md research - Odoo 17 domain knowledge
function validateRegistry(registry) {
  const errors = [];
  const modelNames = new Set();

  for (const [modelName, model] of Object.entries(registry.models || {})) {
    // Check model name format
    if (!/^[a-z][a-z0-9_.]+$/.test(modelName)) {
      errors.push({ model: modelName, error: `Invalid Odoo model name format` });
    }

    // Check for duplicates
    if (modelNames.has(modelName)) {
      errors.push({ model: modelName, error: 'Duplicate model name' });
    }
    modelNames.add(modelName);

    // Check relational field targets
    for (const [fieldName, field] of Object.entries(model.fields || {})) {
      if (['Many2one', 'One2many', 'Many2many'].includes(field.type)) {
        if (!field.comodel_name) {
          errors.push({ model: modelName, field: fieldName, error: `${field.type} requires comodel_name` });
        } else if (!registry.models[field.comodel_name]) {
          errors.push({ model: modelName, field: fieldName, error: `${field.type} target "${field.comodel_name}" not in registry` });
        }
      }
      if (field.type === 'One2many' && !field.inverse_name) {
        errors.push({ model: modelName, field: fieldName, error: 'One2many requires inverse_name' });
      }
    }
  }

  return { valid: errors.length === 0, errors, model_count: modelNames.size };
}
```

### Tier Grouping from Dependency Depth
```javascript
// Source: ARCHITECTURE.md + topological sort pattern
function computeTiers(modules) {
  const sorted = topoSort(modules);
  const depths = {};

  for (const name of sorted) {
    const deps = (modules[name]?.depends || []).filter(d => modules[d]);
    depths[name] = deps.length === 0
      ? 0
      : Math.max(...deps.map(d => depths[d])) + 1;
  }

  const tiers = {};
  for (const [name, depth] of Object.entries(depths)) {
    const tierName = depth === 0 ? 'foundation'
      : depth === 1 ? 'core'
      : depth === 2 ? 'operations'
      : 'communication';
    if (!tiers[tierName]) tiers[tierName] = [];
    tiers[tierName].push(name);
  }

  return { tiers, depths, order: sorted };
}
```

### Test Pattern (matches existing Amil tests)
```javascript
// Source: tests/config.test.cjs pattern
const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { runGsdTools, createTempProject, cleanup } = require('./helpers.cjs');

describe('registry read command', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('returns empty registry when no file exists', () => {
    const result = runGsdTools('registry read', tmpDir);
    assert.ok(result.success);
    const data = JSON.parse(result.output);
    assert.deepStrictEqual(data.models, {});
    assert.strictEqual(data._meta.version, 0);
  });

  test('returns populated registry when file exists', () => {
    const registry = {
      _meta: { version: 1, last_updated: '2026-01-01' },
      models: { 'university.student': { name: 'university.student', module: 'university_student', fields: {} } },
    };
    const regPath = path.join(tmpDir, '.planning', 'model_registry.json');
    fs.writeFileSync(regPath, JSON.stringify(registry), 'utf-8');

    const result = runGsdTools('registry read', tmpDir);
    assert.ok(result.success);
    const data = JSON.parse(result.output);
    assert.strictEqual(data._meta.version, 1);
    assert.ok(data.models['university.student']);
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Amil multi-runtime (Claude/OpenCode/Gemini/Codex) | Claude Code only | This fork | Simplifies install.js from 2464 LOC to ~300 LOC |
| Generic project orchestration | Odoo ERP module orchestration | This fork | All new state files, domain-specific validation |
| No model registry | Centralized model_registry.json | This fork | Enables cross-module coherence checking |
| No dependency ordering | Topological sort with tier grouping | This fork | Enforces correct generation order |
| Direct fs.writeFileSync | Atomic write-rename with .bak | This fork | Prevents state corruption on crash |

**Deprecated/outdated:**
- `get-shit-done` path: Replaced by `amil`
- `/amil:` command prefix: Replaced by `/amil:`
- Multi-runtime install: Stripped to Claude Code only
- `gsd-*` agent names: Renamed to `amil-*`
- `.gsd/` home directory references: Changed to project-local `.planning/`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Node.js built-in test runner (v25.5.0) |
| Config file | `scripts/run-tests.cjs` (custom test runner that globs `tests/*.test.cjs`) |
| Quick run command | `node --test tests/registry.test.cjs` |
| Full suite command | `npm test` (runs `node scripts/run-tests.cjs`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REG-01 | Registry CRUD (read, read-model, update, validate, stats) | unit+integration | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-02 | Atomic writes (tmp + rename) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-03 | Registry versioning (_meta.version increment) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-04 | Registry rollback from .bak | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-05 | Validation (Many2one targets, duplicates, required fields) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-06 | Stats (model count, field count, cross-refs) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-07 | CLI subcommand dispatch | integration | `node --test tests/registry.test.cjs` | No - Wave 0 |
| STAT-01 | module_status.json creation | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| STAT-02 | Status transitions enforced | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| STAT-03 | Tier status computation | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| STAT-04 | Per-module artifact directory creation | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| DEPG-01 | Dependency graph construction | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-02 | Topological sort | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-03 | Circular dependency detection | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-04 | Tier grouping | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-05 | Generation blocking on dependency status | integration | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| FORK-10 | Zero remaining old references | smoke | `grep -r "get-shit-done\|/amil:" --include="*.cjs" --include="*.md" --include="*.js" \| grep -v node_modules` | No - Wave 0 |
| CONF-01 | Odoo config block schema | unit | `node --test tests/config.test.cjs` | Yes (extend) |
| CONF-02 | Odoo config validation | unit | `node --test tests/config.test.cjs` | Yes (extend) |
| TEST-05 | Existing tests pass with renamed prefix | smoke | `npm test` | Yes (update) |

### Sampling Rate
- **Per task commit:** `node --test tests/{changed-module}.test.cjs`
- **Per wave merge:** `npm test` (full suite)
- **Phase gate:** `npm run test:coverage` -- 80%+ lines across registry.cjs, module-status.cjs, dependency-graph.cjs

### Wave 0 Gaps
- [ ] `tests/registry.test.cjs` -- covers REG-01 through REG-07
- [ ] `tests/module-status.test.cjs` -- covers STAT-01 through STAT-04
- [ ] `tests/dependency-graph.test.cjs` -- covers DEPG-01 through DEPG-05
- [ ] Update `tests/helpers.cjs` -- TOOLS_PATH must point to renamed `amil/bin/amil-tools.cjs`

## Open Questions

1. **Directory rename strategy: nested rename vs. flat copy**
   - What we know: The `get-shit-done/` directory contains `bin/`, `workflows/`, `references/`, `templates/`. It must become `amil/`.
   - What's unclear: Should we `git mv get-shit-done amil` (preserves history but may cause merge issues) or restructure incrementally?
   - Recommendation: Use `git mv` for the directory rename in a single commit, then update all internal references in subsequent commits. This preserves git blame history.

2. **Agent file rename: prefix vs. full rename**
   - What we know: 12 agent files are named `gsd-*.md` in `agents/`. They need to become `amil-*.md`.
   - What's unclear: MODEL_PROFILES in core.cjs uses agent names as keys. Renaming agents means updating the key table AND every workflow that references agents by name.
   - Recommendation: Rename all agent files and update MODEL_PROFILES keys in the same commit. Add new Odoo-specific agents (from Phase 2+) later.

3. **Config odoo block: always present or opt-in?**
   - What we know: CONF-01 requires an `odoo` block in config.json. Existing tests assert on config structure.
   - What's unclear: Should `config-ensure-section` always include the `odoo` block, or only when explicitly initialized?
   - Recommendation: Make `odoo` block opt-in (added by `new-erp` command in Phase 2). Config validation (CONF-02) only runs when the block exists. This avoids breaking existing test assertions.

## Sources

### Primary (HIGH confidence)
- Amil codebase direct inspection: `bin/lib/*.cjs` (6013 LOC total), 11 lib modules, 32 command files, 12 agent files, 16 test files
- `tests/helpers.cjs` -- test infrastructure pattern (TOOLS_PATH, createTempProject, runGsdTools)
- `package.json` -- current name, scripts, devDependencies confirmed
- `config.cjs` -- current config schema and defaults confirmed
- `core.cjs` -- MODEL_PROFILES table with 12 `gsd-*` agent keys confirmed

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` -- zero-dependency constraint, inline algorithm patterns
- `.planning/research/ARCHITECTURE.md` -- registry schema, atomic write pattern, state file relationships
- `.planning/research/PITFALLS.md` -- fork rename minefield, state corruption prevention
- Odoo 17 model naming conventions (training data, consistent with docs)

### Tertiary (LOW confidence)
- Exact line count estimates for new modules (400-600 LOC for registry.cjs) -- based on complexity comparison with existing modules

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- directly inherited from Amil, confirmed by codebase inspection
- Architecture: HIGH -- extends proven Amil patterns, new modules follow established conventions
- Pitfalls: HIGH -- based on actual reference counts (98 files, 233+ occurrences) from codebase grep
- Code examples: HIGH -- derived from existing Amil patterns and verified research documents

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, no external API changes expected)
