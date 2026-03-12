# Stack Research

**Domain:** CLI-based Odoo ERP module orchestration system
**Researched:** 2026-03-05
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Node.js | 25.x (system) | Runtime | Amil is pure Node.js CJS. Forking means inheriting this runtime. No reason to change -- Claude Code extensions are Node.js. Node 25 is installed on this system. |
| CommonJS (.cjs) | N/A | Module format | Amil uses CJS throughout (`require`/`module.exports`). Converting to ESM adds zero value and creates merge-forward friction with upstream Amil changes. Keep CJS. |
| Node.js built-in `fs` | N/A | File I/O, state persistence | Amil uses `fs.readFileSync`/`fs.writeFileSync` for all state. The model registry, module status, computation chains, and security scope files are all JSON -- `fs` handles this fine. |
| Node.js built-in `path` | N/A | Path resolution | Cross-platform path handling for `.planning/modules/{name}/` artifact directories and registry files. |
| Node.js built-in `child_process` | N/A | Git operations, belt invocation | Amil uses `execSync` for git commits. amil will also use it for invoking amil belt validation commands. |
| Node.js built-in `test` runner | 25.x | Testing | Node 25 has a mature built-in test runner (`node --test`). Zero dependencies. Supports describe/it, beforeEach/afterEach, mocking, coverage. No need for Vitest/Jest in a CLI tool with no browser concerns. |

**Confidence: HIGH** -- This is not a technology choice, it is an inheritance. Amil is zero-dependency Node.js CJS. The fork must maintain this to preserve the 34 existing workflow files, 12 lib modules (~5400 LOC), and the entire command/agent/workflow architecture.

### State Management Files

| File | Format | Purpose | Why This Format |
|------|--------|---------|-----------------|
| `model_registry.json` | JSON | Cross-module model definitions (fields, relations, inherits) | JSON is human-readable, diffable in git, parseable without dependencies. Amil already uses JSON for `config.json`. |
| `module_status.json` | JSON | Module lifecycle tracking (planned -> spec_approved -> generated -> checked -> shipped) | Simple key-value state transitions. JSON is sufficient. |
| `computation_chains.json` | JSON | Tracks computed field dependencies across modules | Directed graph of field computations. JSON array of edges. |
| `security_scope.json` | JSON | Security groups, record rules, scope hierarchy | Hierarchical scope data (institution > campus > faculty > department > program). JSON nests naturally. |

**Confidence: HIGH** -- Amil's proven pattern is markdown for human-facing state (STATE.md, ROADMAP.md) and JSON for machine-facing state (config.json). The registry files are machine-facing.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None (zero dependencies) | N/A | N/A | Amil is explicitly zero-dependency. amil MUST maintain this. Every npm dependency is a liability for a tool installed globally in `~/.claude/`. No `node_modules`, no `package.json`, no version conflicts with user projects. |

**Confidence: HIGH** -- This is a critical architectural constraint, not a limitation. The zero-dependency approach is what makes Amil installable via `git clone` with no build step.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Node.js built-in test runner | Unit + integration testing | `node --test --experimental-test-coverage`. Supports glob patterns: `node --test 'tests/**/*.test.cjs'` |
| Node.js built-in `assert` | Test assertions | `const assert = require('node:assert/strict')`. Covers deepEqual, throws, rejects -- everything needed. |
| Node.js built-in `test` mocking | Mock fs/child_process | `const { mock } = require('node:test')`. Mock file reads for registry testing without touching disk. |
| `git` | Version control | Already used by Amil for commit automation. |
| Claude Code | AI agent runtime | The orchestrator runs inside Claude Code. Commands are registered as `/amil:*` slash commands. |

## Key Architecture Decisions

### Why Zero Dependencies

Amil's zero-dependency approach is deliberate and must be preserved:

1. **Install simplicity**: `git clone` + add to Claude settings. No `npm install`.
2. **No version conflicts**: The tool lives in `~/.claude/amil/`. If it had dependencies, they could conflict with user project dependencies.
3. **No build step**: CJS files run directly. No transpilation, no bundling.
4. **Claude Code context**: The tool is loaded into Claude Code's context. Smaller footprint = more context budget for actual work.

### JSON Schema Validation Without Libraries

The model registry needs validation (ensure Many2one targets exist, field types are valid, etc.). Without Ajv or Zod, implement validation as:

```javascript
// registry.cjs - validation functions
function validateModelEntry(entry) {
  const errors = [];
  if (!entry.name || typeof entry.name !== 'string') {
    errors.push('name: required string');
  }
  if (!entry.name.match(/^[a-z][a-z0-9_.]+$/)) {
    errors.push(`name: invalid Odoo model name "${entry.name}"`);
  }
  if (!Array.isArray(entry.fields)) {
    errors.push('fields: required array');
  }
  for (const field of entry.fields || []) {
    if (field.type === 'Many2one' && !field.comodel_name) {
      errors.push(`field ${field.name}: Many2one requires comodel_name`);
    }
  }
  return errors;
}
```

This is ~50 lines of focused validation code vs. pulling in a 200KB library. The validation rules are Odoo-domain-specific anyway -- no generic schema language captures "Many2one.comodel_name must reference an existing model in the registry."

### Topological Sort Without Libraries

Module dependency ordering (tier computation) requires topological sort. Implement inline:

```javascript
// registry.cjs - topological sort for module dependencies
function topoSort(modules) {
  const visited = new Set();
  const sorted = [];
  const visiting = new Set();

  function visit(name) {
    if (visiting.has(name)) throw new Error(`Circular dependency: ${name}`);
    if (visited.has(name)) return;
    visiting.add(name);
    const mod = modules[name];
    for (const dep of mod?.depends || []) {
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

This is 20 lines. The `toposort` npm package is 80 lines. Not worth a dependency.

### Atomic JSON Writes Without Libraries

Amil currently does direct `fs.writeFileSync`. For the model registry, which is the single source of truth for cross-module coherence, use a write-rename pattern:

```javascript
function atomicWriteJSON(filePath, data) {
  const tmpPath = filePath + '.tmp';
  const content = JSON.stringify(data, null, 2) + '\n';
  fs.writeFileSync(tmpPath, content, 'utf-8');
  fs.renameSync(tmpPath, filePath);
}
```

This is 5 lines. The `write-file-atomic` npm package is 150+ lines with uid/gid support we do not need. The `fs.renameSync` is atomic on Linux (this system runs Linux 6.17).

## Installation

```bash
# Clone the fork
git clone <repo-url> ~/.claude/amil

# Add to Claude Code settings (~/.claude/settings.json)
# Add to customInstructions: "Read and follow ~/.claude/amil/CLAUDE.md"

# Verify
node ~/.claude/amil/bin/amil-tools.cjs --help
```

No `npm install`. No build step. No dependencies.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Node.js built-in test runner | Vitest | If the project needed browser-compatible tests, JSX transforms, or TypeScript compilation. None apply here -- this is a CLI tool. |
| Manual JSON validation functions | Ajv | If the schema needed to be shared across multiple languages/services. Here, validation is Node.js only and Odoo-domain-specific. |
| Manual toposort (20 LOC) | `toposort` npm package | If the graph algorithms needed were complex (shortest path, cycle enumeration). Here, we just need basic topological ordering. |
| `fs.writeFileSync` + `fs.renameSync` | `write-file-atomic` | If the tool needed Windows compatibility with NTFS atomicity guarantees. This system is Linux-only (Claude Code runs on Linux). |
| CJS (CommonJS) | ESM | If building a library meant for consumption by modern bundlers. This is a CLI tool invoked by `node` directly. CJS has zero friction with `require()` and `__dirname`. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| TypeScript | Amil is 5400 LOC of CJS. Converting to TS adds a build step, breaks the `git clone` install model, and provides no value for a tool where all consumers are Claude Code agents reading markdown prompts. | Plain JavaScript with JSDoc type comments where clarity helps. |
| npm dependencies (any) | Breaks the zero-dependency install model. Every dependency is a risk of version conflicts, supply chain attacks, and install failures in the `~/.claude/` directory. | Inline implementations. The algorithms needed (toposort, JSON validation, atomic writes) are each <50 LOC. |
| SQLite / LevelDB / any database | The state files (model_registry.json, module_status.json) are small (<1MB even at 100 modules). A database adds complexity, a binary dependency, and breaks git-diffability. | JSON files with atomic write pattern. |
| YAML for state files | JSON is parseable with zero dependencies (`JSON.parse`). YAML requires a parser library (js-yaml, yaml). Amil already uses JSON for config. | JSON for machine state, Markdown for human state. |
| Monorepo tools (nx, turborepo) | This is a single CLI tool, not a monorepo. amil and amil-utils are separate repos by design. | Simple git clone per repo. |
| Commander.js / yargs / oclif | Amil's CLI is not a traditional CLI -- it is invoked by Claude Code via `node gsd-tools.cjs <command> [args]`. The argument parsing is a simple switch statement in `commands.cjs` (~550 LOC). No need for a CLI framework. | Manual argument parsing (inherited from Amil). |

## Stack Patterns by Variant

**If adding a new state file (e.g., `computation_chains.json`):**
- Follow Amil's config.json pattern: JSON file in `.planning/`
- Read with `JSON.parse(fs.readFileSync(path, 'utf-8'))`
- Write with `atomicWriteJSON(path, data)`
- Validate with domain-specific functions, not schema libraries

**If adding a new CLI command (e.g., `amil:plan-module`):**
- Add a workflow markdown file in `workflows/plan-module.md`
- Add command handler in `bin/lib/commands.cjs`
- Follow Amil's pattern: parse args, load state, perform operation, output JSON

**If adding a new agent (e.g., `odoo-coherence-checker`):**
- Create markdown prompt file in `references/agents/`
- Register in `core.cjs` MODEL_PROFILES table
- Agent is invoked via Claude Code's `Task()` subagent pattern

**If adding registry operations:**
- All registry CRUD goes in `bin/lib/registry.cjs` (new file)
- Functions: `registryRead()`, `registryUpdate(model)`, `registryRollback(version)`, `registryValidate()`, `registryStats()`
- Atomic writes for all mutations
- Version tracking: `registry_version` integer incremented on each write

## Version Compatibility

| Component | Compatible With | Notes |
|-----------|-----------------|-------|
| Node.js 25.x | Amil CJS codebase | Node 25 runs CJS natively. Built-in test runner is stable. |
| Node.js 25.x built-in test | `assert/strict` | Both are built-in, always compatible. |
| Odoo 17.0 | Python 3.10+ | amil does not run Python -- it generates specs that amil uses to produce Python. But the generated model names, field types, and manifest fields must conform to Odoo 17 conventions. |
| Claude Code | Task() subagent API | amil relies on Claude Code's Task() for spawning agents with fresh 200K context. This is a Claude Code feature, not a Node.js one. |

## Odoo 17 Domain Knowledge (Relevant to Stack)

The stack must encode knowledge of Odoo 17 structures for validation:

- **Model names**: dot-notation (`university.student`, `university.course`). Regex: `/^[a-z][a-z0-9_.]+$/`
- **Field types**: Char, Text, Integer, Float, Boolean, Date, Datetime, Selection, Html, Binary, Monetary, Many2one, One2many, Many2many, Reference
- **Relational field constraints**: Many2one requires `comodel_name`. One2many requires `comodel_name` + `inverse_name`. Many2many requires `comodel_name`.
- **Manifest required fields**: `name`, `version`, `depends`, `license`
- **Module naming**: lowercase, underscores, no dots (`university_student`, not `university.student`)
- **Security**: `ir.model.access.csv` format, `ir.rule` XML records

This domain knowledge lives in validation functions within `registry.cjs`, not in configuration files or external schemas.

## Sources

- [Amil source code](~/.claude/get-shit-done/) -- Direct inspection of bin/lib/*.cjs (5400 LOC total), zero npm dependencies confirmed
- [Odoo 17 Module Manifests](https://www.odoo.com/documentation/17.0/developer/reference/backend/module.html) -- Official manifest field reference
- [Ajv JSON Schema Validator](https://ajv.js.org/) -- Evaluated and rejected; domain-specific validation is better inline
- [toposort npm](https://www.npmjs.com/package/toposort) -- Evaluated and rejected; 20 LOC inline implementation sufficient
- [write-file-atomic](https://www.npmjs.com/package/write-file-atomic) -- Evaluated and rejected; `fs.renameSync` is atomic on Linux
- [Node.js built-in test runner](https://nodejs.org/api/test.html) -- Native test runner available in Node 25

---
*Stack research for: Odoo ERP module orchestration system (amil)*
*Researched: 2026-03-05*
