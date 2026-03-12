# Phase 2: PRD Decomposition and ERP Init - Research

**Researched:** 2026-03-05
**Domain:** CLI workflow orchestration, parallel agent spawning, Odoo module decomposition
**Confidence:** HIGH

## Summary

Phase 2 builds the `/amil:new-erp` command -- the primary entry point for initializing an Odoo ERP project from a PRD document. This phase involves: (1) creating a new slash command and workflow that asks 7 Odoo-specific config questions, (2) spawning 4 parallel `Task()` research agents against a PRD, (3) merging their JSON outputs into a decomposition, (4) presenting the decomposition for human approval, (5) generating a flat ROADMAP.md for the target ERP project, and (6) implementing tiered registry injection (REG-08) in `registry.cjs`.

The codebase patterns are well-established from Phase 1. All required infrastructure exists: `config.cjs` with `cmdConfigSet` for dot-notation writes, `registry.cjs` with `readRegistryFile`, `module-status.cjs` with `cmdModuleStatusInit`, and `dependency-graph.cjs` with `topoSort`/`computeTiers`. The `new-project.md` workflow demonstrates the exact `Task()` spawning pattern for parallel agents. Two new agent files must be created (`odoo-erp-decomposer.md`, `odoo-module-researcher.md`) while two agents are inline `Task()` prompts in the workflow.

**Primary recommendation:** Structure Phase 2 into 3 plans: (1) tiered registry injection + config validation extensions, (2) new-erp command/workflow with interactive questions and 4-agent PRD analysis, (3) merge logic, human approval presentation, and ROADMAP.md generation with tests.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**new-erp Interactive Questions (Stage A):**
- 7 sequential config questions, each writes to config.json immediately via `cmdConfigSet`
- Questions: Odoo version, multi-company, localization, existing modules, LMS integration, notification channels, deployment target
- No question about module count (agents determine from PRD)
- Q4 (existing_modules) passed to ALL 4 research agents as context AND stored in config

**PRD Input (Stage B prerequisite):**
- PRD must exist as `.planning/PRD.md` or user is prompted to provide one

**4 Research Agents -- Parallel Task() Spawns:**
- Agent 1: Module Boundary Analyzer (`agents/odoo-erp-decomposer.md`) -- dedicated agent file
- Agent 2: OCA Registry Checker (`agents/odoo-module-researcher.md`) -- dedicated agent file, Claude training knowledge only (no web fetch)
- Agent 3: Dependency Mapper -- inline Task() in workflow
- Agent 4: Computation Chain Identifier -- inline Task() in workflow

**Agent Output Formats:**
- module-boundaries.json: `{ "modules": [{ "name", "description", "models", "base_depends", "estimated_complexity" }] }`
- oca-analysis.json: `{ "findings": [{ "domain", "oca_module", "odoo_module", "recommendation", "reason" }] }`
- dependency-map.json: `{ "dependencies": [{ "module", "depends_on", "reason" }] }`
- computation-chains.json: `{ "chains": [{ "name", "description", "steps", "cross_module" }] }`

**Merge Strategy:**
- Sequential 5-step merge after all 4 agents complete
- Base from Agent 1 -> annotate with Agent 2 -> toposort via dependency-graph.cjs from Agent 3 -> attach chains from Agent 4 -> write decomposition.json

**Human Approval Checkpoint:**
- Structured text presentation (tiered table format), not raw JSON
- Options: approve / modify / regenerate

**ROADMAP.md Generation:**
- Flat format, no roadmap.js changes needed
- Phase number = topological sort order, tier info in detail bullets
- Uses existing `roadmap.js` parser (reads `### Phase N:` headers)
- This roadmap is for the TARGET ERP project, not the amil tool repo

**Tiered Registry Injection (REG-08):**
- Three tiers: full models (direct depends), field-list-only (transitive depends), names-only (rest)
- Implemented as a function in registry.cjs
- Takes a module name and returns filtered registry

**Q4 Existing Modules -- Dual Usage:**
- Stored in config AND passed to agents
- Does NOT pre-populate registry (that is v2 map-erp)

**Two Separate Roadmap Contexts:**
- amil tool roadmap vs ERP project roadmap are independent, live in different directories

### Claude's Discretion

- Exact wording of interactive question prompts
- Error messages and validation feedback text
- Internal structure of the new-erp.md workflow file
- How the merge step handles edge cases (e.g., agent disagrees on module boundaries)
- Computation chain attachment logic (matching chain steps to module names)

### Deferred Ideas (OUT OF SCOPE)

- `/amil:map-erp` for scanning existing Odoo modules into registry (v2)
- On-demand third-party model scanning (v2 ADVS-03)
- Web-based OCA registry checking via brave_search or WebFetch
- Real-time Odoo instance scanning via XML-RPC
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-03 | `new-erp` command collects Odoo-specific config via interactive questions and writes `odoo` block to config.json | Existing `cmdConfigSet` with dot-notation supports writing `odoo.*` keys. New validation rules needed for Q2 (boolean), Q3 (localization enum), Q5 (LMS enum), Q7 (deployment enum). Q1/Q6 already validated by CONF-02. |
| REG-08 | Tiered registry injection (full models for direct depends, field-list-only for transitive, names-only for rest) | New function in `registry.cjs` that traverses `module_status.json` dependency graph using `dependency-graph.cjs` topoSort/computeTiers. Returns filtered copy of registry. |
| NWRP-01 | `/amil:new-erp` command and workflow created | New `commands/amil/new-erp.md` + `amil/workflows/new-erp.md`. Follow exact pattern from `new-project.md`. |
| NWRP-02 | Odoo-specific config questions asked at project init | 7 questions using `AskUserQuestion`, each writing to config.json via `cmdConfigSet` or equivalent. |
| NWRP-03 | 4 parallel research agents spawned on PRD | 4 `Task()` calls (2 referencing agent files, 2 inline). All receive PRD text + existing_modules from config. |
| NWRP-04 | Research outputs merged into module dependency graph with phased generation order | 5-step merge reads 4 JSON files, cross-references, runs topoSort, writes decomposition.json. |
| NWRP-05 | Human reviews and approves module decomposition before roadmap generation | Structured text presentation with tiered table. AskUserQuestion with approve/modify/regenerate options. |
| NWRP-06 | ROADMAP.md generated with dependency tiers as phases | Write flat markdown with `### Phase N: module_name` headers that existing `roadmap.cjs` parser can read. |
| NWRP-07 | New agents created: `odoo-erp-decomposer`, `odoo-module-researcher` | Two `.md` files in `agents/` following existing naming pattern `amil-*.md`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Node.js built-ins (fs, path, child_process) | Node 18+ | File I/O, path resolution | Zero npm dependency rule from CLAUDE.md |
| amil-tools.cjs | Existing | CLI dispatch, config read/write, registry CRUD | Central entry point, all commands route through it |
| registry.cjs | Existing | Model registry with atomic writes | REG-08 extends this with tiered injection function |
| dependency-graph.cjs | Existing | topoSort, computeTiers, cycle detection | Merge step uses this for tier assignment |
| module-status.cjs | Existing | Module lifecycle init/transition | decomposition.json modules initialized here |
| config.cjs | Existing | cmdConfigSet with dot-notation writes | Writes odoo.* config keys from interactive questions |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Claude Task() API | Claude Code native | Parallel agent spawning | Spawning 4 research agents on PRD |
| AskUserQuestion API | Claude Code native | Interactive config questions | 7 Odoo config questions + approval checkpoint |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AskUserQuestion per question | Single batch question | Locked: sequential, each writes immediately |
| Web fetch for OCA check | Claude training knowledge | Locked: brave_search is false, use training data only |

## Architecture Patterns

### Recommended Project Structure

New files for Phase 2:
```
commands/amil/
  new-erp.md                   # Slash command definition
amil/workflows/
  new-erp.md                   # Full workflow logic
agents/
  amil-erp-decomposer.md  # Agent 1: Module boundary analysis
  amil-module-researcher.md # Agent 2: OCA registry check
amil/bin/lib/
  registry.cjs                 # MODIFIED: add tieredRegistryInjection()
  config.cjs                   # MODIFIED: add new odoo key validations
tests/
  new-erp.test.cjs             # Tests for new-erp workflow logic
  tiered-registry.test.cjs     # Tests for REG-08 tiered injection
```

Research output files (created at runtime by agents):
```
.planning/research/
  module-boundaries.json       # Agent 1 output
  oca-analysis.json            # Agent 2 output
  dependency-map.json          # Agent 3 output
  computation-chains.json      # Agent 4 output
  decomposition.json           # Merged result
```

### Pattern 1: Command/Workflow Separation

**What:** Slash command files (`commands/amil/new-erp.md`) are thin entry points that reference workflow files. The workflow file contains all logic.
**When to use:** Every new slash command.
**Example:**
```markdown
# commands/amil/new-erp.md
---
name: amil:new-erp
description: Initialize an Odoo ERP project from a PRD
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<execution_context>
@~/.claude/amil/workflows/new-erp.md
</execution_context>
<process>
Execute the new-erp workflow end-to-end.
</process>
```

### Pattern 2: Parallel Task() Spawning

**What:** Use Claude Code's `Task()` to spawn agents in parallel, wait for all to complete, then process outputs.
**When to use:** When 4 research agents must analyze the PRD simultaneously.
**Example from new-project.md (verified in codebase):**
```
Task(prompt="...", subagent_type="amil-project-researcher", model="{model}", description="Stack research")
```
All 4 tasks launched together, outputs collected after all complete.

### Pattern 3: Config Write via cmdConfigSet

**What:** Write individual config keys using dot-notation via the CLI tool.
**When to use:** After each interactive question answer.
**Example:**
```bash
node "$HOME/.claude/amil/bin/amil-tools.cjs" config-set odoo.version "17.0"
node "$HOME/.claude/amil/bin/amil-tools.cjs" config-set odoo.multi_company false
node "$HOME/.claude/amil/bin/amil-tools.cjs" config-set odoo.localization "pk"
```

### Pattern 4: Agent File Naming

**What:** Agent files follow the pattern `amil-{purpose}.md` in the `agents/` directory.
**When to use:** The 2 dedicated agent files (NWRP-07).
**Existing examples:** `amil-executor.md`, `amil-planner.md`, `amil-verifier.md`
**New files:** `amil-erp-decomposer.md`, `amil-module-researcher.md`

### Anti-Patterns to Avoid

- **Mutating existing registry in-place during tiered injection:** The tiered injection function must return a NEW filtered copy, never modify the registry on disk. This is read-only filtering.
- **Spawning agents sequentially:** Agents 1-4 are independent and MUST run in parallel via `Task()`. Sequential spawning wastes time.
- **Writing all 7 config keys at once:** Locked decision says each question writes immediately. This ensures partial progress is preserved if session is interrupted.
- **Modifying roadmap.cjs parser:** The ERP project roadmap uses the same `### Phase N:` format that roadmap.cjs already parses. No parser changes needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Topological sort | Custom sort algorithm | `dependency-graph.cjs topoSort()` | Already tested with 15 tests, handles cycles |
| Tier grouping | Custom tier assignment | `dependency-graph.cjs computeTiers()` | Depth-based tier labels already implemented |
| Atomic JSON writes | Manual fs.writeFile | `atomicWriteJSON()` from registry.cjs or module-status.cjs | Backup + tmp + rename pattern proven |
| Config key validation | Inline checks | Extend `validateOdooConfigKey()` in config.cjs | Centralized validation, tested by 23 config tests |
| Module status init | Manual JSON manipulation | `cmdModuleStatusInit()` | Creates artifact dir, CONTEXT.md, updates module_status.json atomically |

**Key insight:** Phase 1 built all the primitives. Phase 2 composes them -- the new code is primarily the workflow orchestration (prompt engineering for agents, merge logic, presentation formatting) not infrastructure.

## Common Pitfalls

### Pitfall 1: Agent Output Schema Mismatch
**What goes wrong:** Agent produces JSON that doesn't match the expected schema (missing keys, wrong nesting, extra fields).
**Why it happens:** LLM output is non-deterministic. Agent prompts must be extremely specific about schema.
**How to avoid:** Include the exact JSON schema in each agent prompt. After agent completes, validate output against schema before merge. If validation fails, surface error to user rather than silently ignoring.
**Warning signs:** Merge step crashes with "Cannot read property X of undefined".

### Pitfall 2: Dependency on External Modules in Agent Output
**What goes wrong:** Agent 1 proposes module depends on `base`, `mail`, `account` -- modules that exist in standard Odoo but not in the registry.
**Why it happens:** These are Odoo base modules, not custom `uni_*` modules.
**How to avoid:** `base_depends` in module-boundaries.json captures standard Odoo depends. These are NOT tracked in module_status.json or the dependency graph -- they are metadata only. The dependency graph only tracks custom `uni_*` module dependencies.
**Warning signs:** topoSort crashes because `base` module not found in modules map.

### Pitfall 3: Two Roadmap Contexts Collision
**What goes wrong:** new-erp accidentally modifies the amil tool's own ROADMAP.md instead of writing the target ERP's roadmap.
**Why it happens:** Both use `.planning/ROADMAP.md` but in different project directories.
**How to avoid:** The new-erp workflow operates on the TARGET project cwd, not on the amil tool repo. The ERP project's `.planning/` directory is separate. Workflow must use the correct cwd context. Clear comments in workflow.
**Warning signs:** Phase numbers conflict with tool roadmap phases.

### Pitfall 4: Notification Channels Validation Mismatch
**What goes wrong:** Q6 allows `["email", "whatsapp", "sms"]` but existing `VALID_NOTIFICATION_CHANNELS` in config.cjs is `['email', 'sms', 'push', 'in_app']`.
**Why it happens:** CONTEXT.md specifies a different set than what was implemented in Phase 1.
**How to avoid:** Update `VALID_NOTIFICATION_CHANNELS` to include `whatsapp` or handle this as a new-erp-specific validation. The Q6 validation may need its own allowed set separate from the existing config validation.
**Warning signs:** User selects "whatsapp" and gets a validation error.

### Pitfall 5: Config Validation for New Keys
**What goes wrong:** New odoo keys (multi_company, localization, canvas_integration, deployment_target) bypass validation.
**Why it happens:** `validateOdooConfigKey()` only checks `odoo.version`, `odoo.scope_levels`, and `odoo.notification_channels`.
**How to avoid:** Extend `validateOdooConfigKey()` with cases for: `odoo.multi_company` (boolean), `odoo.localization` (enum: pk/sa/ae/none), `odoo.canvas_integration` (enum: canvas/moodle/none), `odoo.deployment_target` (enum: single/multi).

## Code Examples

Verified patterns from the existing codebase:

### Tiered Registry Injection (REG-08)
```javascript
// Source: New function for registry.cjs
// Takes module name + module_status.json, returns filtered registry
function tieredRegistryInjection(cwd, moduleName) {
  const registry = readRegistryFile(cwd);
  const statusData = require('./module-status.cjs').readStatusFile(cwd);
  const mod = statusData.modules[moduleName];
  if (!mod) return { models: {} };

  const directDeps = new Set(mod.depends || []);

  // Compute transitive deps (deps of deps, not including direct)
  const transitiveDeps = new Set();
  for (const dep of directDeps) {
    const depMod = statusData.modules[dep];
    if (depMod && depMod.depends) {
      for (const td of depMod.depends) {
        if (!directDeps.has(td)) transitiveDeps.add(td);
      }
    }
  }

  const result = { models: {} };
  for (const [modelName, model] of Object.entries(registry.models)) {
    const modelModule = model.module;
    if (directDeps.has(modelModule)) {
      // Full model: all fields, all metadata
      result.models[modelName] = { ...model };
    } else if (transitiveDeps.has(modelModule)) {
      // Field-list-only: model name + field names, no field metadata
      result.models[modelName] = {
        name: model.name,
        module: model.module,
        fields: Object.fromEntries(
          Object.keys(model.fields || {}).map(f => [f, { name: f }])
        ),
      };
    } else {
      // Names-only: just model name
      result.models[modelName] = { name: model.name, module: model.module };
    }
  }
  return result;
}
```

### Config Validation Extension
```javascript
// Source: Extension to validateOdooConfigKey() in config.cjs
const VALID_LOCALIZATIONS = ['pk', 'sa', 'ae', 'none'];
const VALID_LMS_INTEGRATIONS = ['canvas', 'moodle', 'none'];
const VALID_DEPLOYMENT_TARGETS = ['single', 'multi'];

// Add cases to validateOdooConfigKey():
if (keyPath === 'odoo.multi_company') {
  if (typeof parsedValue !== 'boolean') {
    return 'odoo.multi_company must be a boolean';
  }
}
if (keyPath === 'odoo.localization') {
  if (!VALID_LOCALIZATIONS.includes(String(parsedValue))) {
    return `Invalid odoo.localization: "${parsedValue}". Must be one of: ${VALID_LOCALIZATIONS.join(', ')}`;
  }
}
if (keyPath === 'odoo.canvas_integration') {
  if (!VALID_LMS_INTEGRATIONS.includes(String(parsedValue))) {
    return `Invalid odoo.canvas_integration: "${parsedValue}". Must be one of: ${VALID_LMS_INTEGRATIONS.join(', ')}`;
  }
}
if (keyPath === 'odoo.deployment_target') {
  if (!VALID_DEPLOYMENT_TARGETS.includes(String(parsedValue))) {
    return `Invalid odoo.deployment_target: "${parsedValue}". Must be one of: ${VALID_DEPLOYMENT_TARGETS.join(', ')}`;
  }
}
```

### Module Init After Decomposition Approval
```bash
# For each module in the approved decomposition:
node "$HOME/.claude/amil/bin/amil-tools.cjs" module-status init uni_core foundation '["base","mail"]' --cwd "$TARGET_CWD"
node "$HOME/.claude/amil/bin/amil-tools.cjs" module-status init uni_student core '["uni_core"]' --cwd "$TARGET_CWD"
```

### Decomposition Presentation Format
```
ERP MODULE DECOMPOSITION -- 12 modules across 4 tiers

TIER 1: Foundation (generate first)
  | Module      | Models   | Build     | Depends             |
  | uni_core    | 6        | NEW       | base, mail          |

TIER 2: Core Academic
  | Module      | Models   | Build     | Depends             |
  | uni_student | 8        | NEW       | uni_core            |
  | uni_program | 5        | EXTEND    | uni_core            |

COMPUTATION CHAINS (cross-module):
  1. enrollment_fee: uni_student.enrollment -> uni_fee.invoice -> uni_account.payment

WARNINGS:
  - uni_notification depends on 3 tier-2 modules (complex dependency)

Approve this decomposition? (yes / modify / regenerate)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic agent | 4 parallel specialized agents | Phase 2 design | Better decomposition quality, faster execution |
| Manual module dependency tracking | Automated topoSort + tier grouping | Phase 1 | Merge step can auto-assign tier numbers |
| Interactive config as freeform text | AskUserQuestion with constrained options | Existing Amil pattern | Consistent UX, validated input |

## Open Questions

1. **Notification channels set mismatch**
   - What we know: CONTEXT.md says Q6 options are `["email", "whatsapp", "sms"]`. Phase 1 config.cjs has `VALID_NOTIFICATION_CHANNELS = ['email', 'sms', 'push', 'in_app']`.
   - What's unclear: Should we extend the existing set or create a separate validation for new-erp context?
   - Recommendation: Add `whatsapp` to `VALID_NOTIFICATION_CHANNELS` and keep `push`/`in_app` as well. The Q6 question presents only the 3 options but the validator accepts the full set.

2. **Agent output when PRD is vague**
   - What we know: Agent prompts need specific schemas. PRD quality varies.
   - What's unclear: How gracefully do agents handle a terse or ambiguous PRD?
   - Recommendation: Include a minimum-output instruction in agent prompts (e.g., "If PRD lacks detail for a domain, output the domain with estimated_complexity: 'unknown' and a note in description").

3. **Transitive dependency depth for tiered injection**
   - What we know: REG-08 specifies direct deps = full, transitive deps = field-list, rest = names-only.
   - What's unclear: How deep should transitive go? Just depth 2, or all transitive?
   - Recommendation: All transitive (any module reachable via dependency chain from the target module's direct deps). This is computationally cheap given the small module count (~20).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Node.js built-in test runner (node:test) |
| Config file | package.json `"scripts": { "test": "node --test tests/" }` |
| Quick run command | `node --test tests/tiered-registry.test.cjs` |
| Full suite command | `npm test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-03 | New odoo config keys validated and written | unit | `node --test tests/config.test.cjs -x` | Exists (extend) |
| REG-08 | Tiered injection returns correct model detail levels | unit | `node --test tests/tiered-registry.test.cjs -x` | Wave 0 |
| NWRP-01 | new-erp command file exists and references workflow | unit | `node --test tests/new-erp.test.cjs -x` | Wave 0 |
| NWRP-04 | Merge produces correct decomposition from 4 agent outputs | unit | `node --test tests/new-erp.test.cjs -x` | Wave 0 |
| NWRP-06 | Generated ROADMAP.md parseable by roadmap.cjs | integration | `node --test tests/roadmap.test.cjs -x` | Exists (extend) |
| NWRP-07 | Agent files exist with correct frontmatter | unit | `node --test tests/agent-frontmatter.test.cjs -x` | Exists (extend) |

### Sampling Rate
- **Per task commit:** `node --test tests/tiered-registry.test.cjs tests/config.test.cjs`
- **Per wave merge:** `npm test`
- **Phase gate:** Full suite green before `/amil:verify-work`

### Wave 0 Gaps
- [ ] `tests/tiered-registry.test.cjs` -- covers REG-08 tiered injection (direct/transitive/rest filtering)
- [ ] `tests/new-erp.test.cjs` -- covers merge logic, decomposition.json schema validation, ROADMAP.md generation
- [ ] Extend `tests/config.test.cjs` -- add cases for odoo.multi_company, odoo.localization, odoo.canvas_integration, odoo.deployment_target validation

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `amil/bin/lib/registry.cjs` (326 LOC) -- verified CRUD operations, atomicWriteJSON pattern
- Codebase inspection: `amil/bin/lib/config.cjs` (223 LOC) -- verified validateOdooConfigKey, cmdConfigSet
- Codebase inspection: `amil/bin/lib/dependency-graph.cjs` (201 LOC) -- verified topoSort, computeTiers
- Codebase inspection: `amil/bin/lib/module-status.cjs` (205 LOC) -- verified cmdModuleStatusInit, readStatusFile
- Codebase inspection: `amil/workflows/new-project.md` (1112 LOC) -- verified Task() spawning pattern for parallel agents
- Codebase inspection: `commands/amil/new-project.md` -- verified command/workflow separation pattern
- Phase 2 CONTEXT.md -- all locked decisions from user discussion

### Secondary (MEDIUM confidence)
- None needed -- all research is codebase-internal

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries are existing codebase modules, no external dependencies
- Architecture: HIGH - follows exact patterns established in Phase 1 and new-project workflow
- Pitfalls: HIGH - identified from direct code inspection (validation gaps, naming patterns, dual roadmap context)

**Research date:** 2026-03-05
**Valid until:** Indefinite (internal codebase research, no external dependency versioning concerns)
