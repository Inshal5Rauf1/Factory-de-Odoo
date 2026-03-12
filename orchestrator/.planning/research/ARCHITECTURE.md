# Architecture Patterns

**Domain:** Odoo ERP Module Orchestrator (Claude Code extension)
**Researched:** 2026-03-05

## Recommended Architecture

amil is a three-tier orchestration system that decomposes an ERP PRD into 20+ Odoo modules and drives their generation sequentially through a belt (amil), maintaining cross-module coherence via a shared model registry.

```
                    Human (PRD + decisions)
                           |
                    +--------------+
                    |   amil   |  Layer 1: Orchestration
                    |  CLI + State |
                    +------+-------+
                           |
            +--------------+--------------+
            |              |              |
     +------+------+ +----+----+ +-------+-------+
     | Command     | | State   | | Agent         |
     | Dispatcher  | | Manager | | Orchestrator  |
     +------+------+ +----+----+ +-------+-------+
            |              |              |
            |         +----+----+         |
            |         | JSON    |   Task() subagent
            |         | State   |   (fresh 200K context)
            |         | Files   |         |
            |         +---------+   +-----+-----+
            |                       |  amil  |  Layer 2: Generation
            |                       |  (belt)    |
            |                       +-----+------+
            |                             |
            |                       +-----+------+
            |                       | amil-  |  Layer 3: Utilities
            |                       | utils      |
            |                       +------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With | Data Format |
|-----------|---------------|-------------------|-------------|
| **CLI Router** (`bin/gsd-tools.cjs`) | Parse commands, dispatch to lib modules, JSON/raw output | All lib modules | JSON stdout, `@file:` for large payloads |
| **Command Files** (`commands/amil/*.md`) | Markdown-defined slash commands with frontmatter config; orchestrate workflow execution | Workflow files (via `@` references), CLI Router | Markdown with YAML frontmatter |
| **Workflow Files** (`workflows/*.md`) | Multi-step orchestration scripts that coordinate agents, state reads/writes, human checkpoints | Agents (via Task()), State Manager, CLI Router | Markdown instructions |
| **State Manager** (`bin/lib/state.cjs` + extensions) | Read/write STATE.md, frontmatter sync, progression engine | CLI Router, Workflow Files | STATE.md (markdown + YAML frontmatter) |
| **Config Manager** (`bin/lib/config.cjs`) | Read/write `.planning/config.json`, schema validation, defaults | CLI Router, all components needing config | JSON |
| **Registry Manager** (`bin/lib/registry.cjs` -- NEW) | Model registry CRUD, atomic updates, rollback, cross-model validation, tiered injection | CLI Router, Workflow Files, Coherence Checker | `model_registry.json` |
| **Module Status Tracker** (NEW, in registry or separate) | Module lifecycle transitions (planned -> spec_approved -> generated -> checked -> shipped) | CLI Router, Workflow Files | `module_status.json` |
| **Coherence Checker** (agent + lib support) | Validate Many2one targets, computation chains, security scopes, duplicate models | Plan-module workflow, Check-module workflow | `coherence-report.json` |
| **Belt Invoker** (within generate-module workflow) | Prepare spec + registry injection, spawn amil as Task(), parse manifest, update registry | amil (via Task()), Registry Manager | `spec.json` in, `generation-manifest.json` out |
| **Agent Files** (`agents/*.md`) | Persona definitions with role, constraints, I/O format for Task() subagents | Spawned by workflows via Task() | Markdown prompts |
| **Hooks** (`hooks/*.js`) | Statusline, context monitoring, update checking | CLI Router (read state), Claude Code hook system | JS executing in hook lifecycle |
| **Phase Manager** (`bin/lib/phase.cjs`) | Phase directory CRUD, plan indexing, completion tracking | CLI Router, State Manager | Filesystem directories + markdown files |
| **Roadmap Manager** (`bin/lib/roadmap.cjs`) | ROADMAP.md parsing, phase detail extraction, tier structure | CLI Router, Phase Manager | `ROADMAP.md` markdown |

### Data Flow

#### 1. Project Initialization Flow (`/amil:new-erp`)

```
Human provides PRD
  |
  v
Command: new-erp.md
  |
  v
Workflow: new-erp.md
  |
  +-- Ask Odoo config questions --> write .planning/config.json (odoo block)
  |
  +-- Spawn 4 parallel Task() research agents on PRD:
  |     |-- odoo-module-researcher (module boundaries)
  |     |-- odoo-module-researcher (OCA registry check)
  |     |-- odoo-module-researcher (dependency mapping)
  |     +-- odoo-module-researcher (computation chains)
  |
  +-- Merge research --> module dependency graph
  |
  +-- Human reviews decomposition (checkpoint)
  |
  +-- Generate:
        |-- ROADMAP.md (tiers as phases, modules as phase details)
        |-- module_status.json (all modules as "planned")
        |-- computation_chains.json (chain skeletons)
        |-- security_scope.json (framework config)
        +-- .planning/modules/{module}/ directories
```

#### 2. Module Generation Flow (`/amil:generate-module`)

```
Workflow reads:
  .planning/modules/{module}/spec.json
  .planning/model_registry.json
  .planning/config.json (odoo block)
  |
  v
Prepare belt context:
  - Inject _available_models from registry (tiered):
    * FULL models for direct depends
    * Field-list for transitive depends
    * Names-only for rest
  |
  v
Task() --> amil pipeline (fresh 200K context)
  - Belt reads spec.json
  - Belt generates module files in addons/{module}/
  - Belt produces generation-manifest.json
  |
  v
On belt return:
  1. Read generation-manifest.json
  2. Parse new models/fields from manifest
  3. Atomic registry update:
     a. Read current registry
     b. Merge new models (belt output wins for new fields)
     c. Update security_groups
     d. Update computation_chains (mark steps complete)
     e. Bump _meta.version
     f. Write to .tmp file, rename (atomic)
  4. Update module_status.json --> "generated"
  5. Git commit: "feat({module}): generate module"
```

#### 3. Coherence Check Flow (runs at plan-module AND check-module)

```
Input:
  spec.json (proposed module)
  model_registry.json (existing models)
  computation_chains.json
  security_scope.json
  |
  v
Checks:
  CHK-01: Structural
    - Every Many2one comodel_name exists in registry OR in spec
    - Every model has ACL entries
    - mail.thread models have tracking fields
    - Valid Python syntax patterns
  |
  CHK-02: Cross-module
    - Foreign key targets resolve
    - Computed field depends chains are complete
    - Security groups referenced exist
    - No duplicate model names across modules
    - Scope fields present for scoped models
  |
  CHK-03: Spec coverage (check-module only)
    - generation-manifest.json models vs spec.json models
    - Implemented vs stubbed features
  |
  CHK-04: Integration (check-module only)
    - Docker install test
    - Cross-boundary tests
  |
  v
Output:
  coherence-report.json (structured pass/fail per check)
  --> Human review at checkpoint
```

#### 4. State File Relationships

```
.planning/
  |
  +-- config.json              <-- Project config (Odoo block: version, security, scopes)
  |
  +-- STATE.md                 <-- Session state (current module, progress, blockers)
  |     Includes YAML frontmatter synced on every write
  |
  +-- ROADMAP.md               <-- Tier/phase structure (modules ordered by dependency)
  |
  +-- model_registry.json      <-- CENTRAL: All models across all modules
  |     Versioned, atomic updates, rollback capability
  |     Read before every plan/generate, updated after every generate
  |
  +-- module_status.json       <-- Per-module lifecycle (planned->shipped)
  |     Updated at each workflow transition point
  |
  +-- computation_chains.json  <-- Cross-module computed field chains
  |     Steps marked complete as modules generate
  |
  +-- security_scope.json      <-- RBAC framework config (mostly static after init)
  |
  +-- modules/
        +-- {module_name}/
              +-- CONTEXT.md               <-- Human Q&A answers (discuss-module)
              +-- RESEARCH.md              <-- OCA/pattern research (new-erp)
              +-- spec.json                <-- Full module specification (plan-module)
              +-- coherence-report.json    <-- Validation results (plan-module)
              +-- generation-manifest.json <-- Belt output (generate-module)
              +-- check-report.json        <-- 4-level check results (check-module)
```

## Patterns to Follow

### Pattern 1: Atomic State Updates with Versioning

**What:** All JSON state file writes use write-to-temp-then-rename to prevent corruption. The model registry carries a `_meta.version` counter that increments on every update.

**When:** Every write to `model_registry.json`, `module_status.json`, `computation_chains.json`.

**Why:** A failed belt invocation mid-write could corrupt the registry, breaking all downstream modules. Atomic writes + version counter enable rollback.

```javascript
// registry.cjs
function atomicWriteRegistry(registryPath, data) {
  const tmpPath = registryPath + '.tmp';
  const backupPath = registryPath + '.bak';

  // Backup current
  if (fs.existsSync(registryPath)) {
    fs.copyFileSync(registryPath, backupPath);
  }

  // Bump version
  data._meta.version = (data._meta.version || 0) + 1;
  data._meta.last_updated = new Date().toISOString();

  // Atomic write
  fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), 'utf-8');
  fs.renameSync(tmpPath, registryPath);

  return data._meta.version;
}

function rollbackRegistry(registryPath) {
  const backupPath = registryPath + '.bak';
  if (!fs.existsSync(backupPath)) {
    throw new Error('No backup available for rollback');
  }
  fs.copyFileSync(backupPath, registryPath);
}
```

### Pattern 2: Tiered Registry Injection

**What:** When injecting the model registry into a spec or belt context, filter models by relevance to avoid context bloat.

**When:** Before every `plan-module` and `generate-module` invocation.

**Why:** At 20+ modules and 100+ models, the full registry exceeds practical context limits. Tiered injection keeps the context lean while maintaining coherence.

```
Tier 1 (FULL): Direct dependencies
  - Module's `depends` list models
  - Include all fields, methods, constraints, security

Tier 2 (FIELD-LIST): Transitive dependencies
  - Dependencies of dependencies
  - Include model name, field names + types only (no methods/constraints)

Tier 3 (NAMES-ONLY): Everything else
  - All other registered models
  - Include model name only (for duplicate detection and Many2one target resolution)
```

```javascript
function buildTieredRegistry(registry, moduleSpec) {
  const directDeps = new Set(moduleSpec.depends || []);
  const transitiveDeps = new Set();

  // Collect transitive deps
  for (const dep of directDeps) {
    const depModels = Object.values(registry.models)
      .filter(m => m.module === dep);
    for (const model of depModels) {
      // Find what this model depends on via Many2one
      for (const [, field] of Object.entries(model.fields || {})) {
        if (field.type === 'Many2one' && field.comodel_name) {
          const target = registry.models[field.comodel_name];
          if (target && !directDeps.has(target.module)) {
            transitiveDeps.add(target.module);
          }
        }
      }
    }
  }

  return {
    _meta: registry._meta,
    full: filterByModules(registry, directDeps),
    field_list: summarizeByModules(registry, transitiveDeps),
    names_only: listRemainingModelNames(registry, directDeps, transitiveDeps),
  };
}
```

### Pattern 3: Task() Subagent with Fresh Context

**What:** Amil's existing Task() mechanism spawns a subagent with a fresh 200K context window. amil uses this for belt invocation, ensuring the generation pipeline is not polluted by orchestration state.

**When:** Every belt invocation (`generate-module`), every parallel research agent spawn (`new-erp`).

**Why:** The belt (amil) has its own 8-agent pipeline with 13 knowledge files. Sharing context with the orchestrator would leave insufficient room for the belt's own context needs.

```markdown
# In generate-module workflow:
Task(
  prompt: "Generate Odoo module from spec.json.
           Read spec at .planning/modules/{module}/spec.json.
           The _available_models section contains the current model registry.
           Follow the /amil:generate workflow.
           Write output to addons/{module_name}/.",
  subagent_type: "executor",
  model_profile: "quality"
)
```

### Pattern 4: Module Status State Machine

**What:** Each module follows a strict lifecycle: planned -> spec_approved -> generated -> checked -> shipped. Transitions are one-directional (no backward transitions except via explicit re-plan).

**When:** Status transitions are triggered by workflow completion gates.

**Why:** Prevents generating a module before its spec is approved, or shipping before checks pass. Status gates are the enforcement mechanism for the human-in-the-loop workflow.

```
planned ----[discuss + plan-module + human approve]--> spec_approved
spec_approved ----[generate-module success]---------> generated
generated ----[check-module all pass]---------------> checked
checked ----[complete-phase / human ship]-----------> shipped

Re-plan: Any status -> planned (explicit command, resets spec)
```

### Pattern 5: CLI Router Dispatch Pattern (existing Amil)

**What:** `gsd-tools.cjs` is a ~2000-line CLI router that dispatches subcommands to lib modules. Each lib module exports pure functions that take `(cwd, ...args)` and call `output()` or `error()`. Output is always JSON (or `--raw` for single values).

**When:** Every CLI interaction from commands/workflows/hooks.

**Why:** Centralizes all state manipulation behind a single CLI entry point, making it testable and debuggable. Commands/workflows are markdown files that invoke `gsd-tools.cjs` via Bash, keeping orchestration logic separate from state logic.

```
Command File (markdown)
  --> references Workflow File (markdown)
    --> calls `node gsd-tools.cjs <subcommand>` via Bash tool
      --> dispatches to lib/{module}.cjs function
        --> reads/writes .planning/ files
        --> outputs JSON to stdout
    --> workflow reads JSON output, makes decisions
    --> spawns Task() subagents as needed
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Registry Mutation from Workflows

**What:** Workflow markdown files directly reading/writing `model_registry.json` via Read/Write tools instead of going through the CLI router.

**Why bad:** Bypasses atomic write protection, version bumping, and validation. Two concurrent workflows could corrupt the registry. No rollback trail.

**Instead:** Always use `amil-tools registry update` and `amil-tools registry read` CLI commands.

### Anti-Pattern 2: Full Registry Injection

**What:** Injecting the entire `model_registry.json` into every belt invocation regardless of module dependencies.

**Why bad:** At 100+ models with full field definitions, the registry alone could consume 30-50K tokens of the 200K context window. The belt needs that context for its own 13 knowledge files and 8-agent pipeline.

**Instead:** Use tiered injection (Pattern 2). Only full models for direct depends, summaries for transitive, names for rest.

### Anti-Pattern 3: Parallel Belt Invocations

**What:** Running multiple `Task()` belt invocations simultaneously for modules in the same tier.

**Why bad:** Each belt invocation needs exclusive access to the addons directory and Docker. Parallel writes to the same `addons/` path cause file conflicts. Registry updates from parallel completions race. Docker can only run one test suite at a time.

**Instead:** Sequential module generation within tiers. Parallelism is for research agents and coherence checks, not belt invocations.

### Anti-Pattern 4: Storing Generated Code State in Registry

**What:** Tracking the actual generated Python/XML code content in the model registry.

**Why bad:** The registry would grow to megabytes, far exceeding practical context injection size. The generated code lives in `addons/{module}/` on disk -- the registry tracks metadata (model names, field types, dependencies), not code.

**Instead:** Registry stores structural metadata only. Code-level analysis uses amil-utils AST tools when needed.

### Anti-Pattern 5: Skipping Coherence Checks

**What:** Allowing `generate-module` to proceed without a passing coherence check from `plan-module`.

**Why bad:** A Many2one pointing to a nonexistent model will produce an Odoo module that crashes on install. Catching this at spec time is orders of magnitude cheaper than catching it after generation + Docker testing.

**Instead:** Coherence check is a hard gate. `module_status` must be `spec_approved` (which requires passing coherence) before `generate-module` will proceed.

## Component Build Order

This ordering reflects hard dependencies -- each component requires the ones above it.

```
Phase 1: Foundation (no dependencies on new code)
  1. Fork + rename (package.json, entry points, command prefixes)
  2. Config extension (add odoo block to config.cjs)
  3. Registry Manager (bin/lib/registry.cjs) -- NEW
     - CRUD, atomic writes, rollback, validation, tiered injection
     - CLI subcommands: read, read-model, update, rollback, validate, stats
  4. Module Status Tracker (bin/lib/module-status.cjs or in registry.cjs)
     - Status transitions, tier tracking
     - CLI subcommands: get, transition, list

Phase 2: Core Workflow (depends on Phase 1)
  5. CLAUDE.md rewrite (depends on: knowing command names from Phase 1)
  6. new-erp command + workflow (depends on: config, registry init)
  7. discuss-module command + workflow (depends on: module directory structure)
  8. plan-module command + workflow (depends on: registry read, spec format)
     - Includes coherence checker agent
  9. generate-module command + workflow (depends on: registry update, belt invocation)
     - Includes belt invoker, manifest parser, registry updater

Phase 3: Verification (depends on Phase 2)
  10. check-module command + workflow (depends on: generation-manifest, registry)
  11. progress command (depends on: module_status, registry stats)
  12. complete-phase command (depends on: module status, registry archival)

Phase 4: Polish (depends on Phases 1-3)
  13. Hooks (statusline, context monitor)
  14. Remaining command renames
  15. Agent prompt refinement
  16. Tests
  17. install.js rewrite
```

**Build order rationale:**
- Registry Manager is the keystone -- nearly every subsequent component reads or writes the registry. Build and test it first.
- Config extension is needed before any Odoo-specific workflow can read settings.
- CLAUDE.md should be written after commands are named but before workflows are tested (it guides Claude Code behavior).
- Belt invocation (step 9) is the highest-risk component -- it crosses the amil/amil boundary. All preceding components should be solid before tackling it.
- Tests are listed last but should be written alongside each component (TDD). The listing reflects the integration test suite.

## Scalability Considerations

| Concern | At 5 modules | At 20 modules | At 50+ modules |
|---------|-------------|---------------|----------------|
| Registry size | ~5KB, inject fully | ~50KB, must use tiered injection | ~200KB+, may need registry sharding by tier |
| Coherence check time | Seconds (few cross-refs) | Minutes (100+ cross-refs) | Need caching/incremental checks |
| Context window pressure | No issue | Tiered injection essential | May need registry summarization agent |
| Module status tracking | Flat list | Tier grouping helps | Need filtering/pagination in progress view |
| Git history | Clean | Manageable with per-module commits | Consider squash per tier at completion |
| Belt invocation context | Plenty of room | Tiered injection keeps room for belt | Belt may need its own registry pruning |

## Sources

- Amil codebase analysis: `bin/lib/core.cjs`, `bin/lib/state.cjs`, `bin/lib/config.cjs`, `bin/gsd-tools.cjs` (HIGH confidence -- direct code reading)
- AMIL_PRD.md: Architecture specification, state file schemas, workflow definitions (HIGH confidence -- authoritative project document)
- Amil command/workflow pattern: `commands/gsd/execute-phase.md` pattern of markdown + frontmatter + `@` references (HIGH confidence -- direct code reading)
- Odoo module structure knowledge: Training data on Odoo 17.0 module patterns, `__manifest__.py`, model inheritance, security groups (MEDIUM confidence -- training data, needs verification against Odoo 17.0 docs during implementation)
