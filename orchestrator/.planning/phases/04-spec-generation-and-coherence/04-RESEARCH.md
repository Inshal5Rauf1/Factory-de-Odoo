# Phase 4: Spec Generation and Coherence - Research

**Researched:** 2026-03-05
**Domain:** Odoo module spec generation, cross-module coherence validation, agent orchestration
**Confidence:** HIGH

## Summary

Phase 4 builds the `/amil:plan-module` command and its supporting infrastructure: a researcher agent (already exists, reused), a spec generator agent (new), a pure CJS coherence checker library (new), and a reviewer agent (new). The workflow is a 10-step sequential pipeline that loads module context, spawns two agents in sequence, runs deterministic validation, and presents results for human approval.

The implementation is constrained by locked decisions from the CONTEXT.md: spec.json has 12+1 sections with specific formats for computation_chains, view_hints, and security; the coherence checker is pure CJS with 4 structural checks (no LLM); the reviewer agent formats coherence output for humans. All infrastructure patterns are established from Phases 1-3 (CJS modules, atomic writes, Task() subagent spawning, CLI subcommands).

**Primary recommendation:** Build coherence.cjs first (pure logic, fully testable), then the spec generator agent, then the plan-module command/workflow, then the reviewer agent -- each layer depends on the previous.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- spec.json is a declarative contract with 12 top-level sections plus `_available_models`
- Computation chains format: array of `{name, steps[{model, field, trigger}]}` -- no field type info
- View hints format: array of `{model, view_type, key_fields, notes}` -- no XML
- Security format: `{groups, access_rules, record_rules}` with natural language domains
- Coherence checker: pure CJS library at `bin/lib/coherence.cjs`, CLI subcommand `coherence check`
- 4 structural checks: many2one_targets, duplicate_models, computed_depends, security_groups
- Coherence output format: `{status, checks[{check, status, violations[]}]}`
- Two sequential agents: researcher then generator (not parallel)
- Tiered registry injection using existing `tieredRegistryInjection()` from Phase 2
- `_available_models` written INTO spec.json (belt reads from same file)
- Human approval flow: coherence report first, then spec summary, then approval
- Reviewer agent IS the coherence presentation layer (not a separate command)
- Spec generator agent: `agents/amil-spec-generator.md` -- single-shot, all 12 sections
- plan-module command: 10-step flow (validate, check existing, load context, load decomposition, spawn researcher, build tiered registry, spawn spec generator, run coherence, spawn reviewer, human approval)

### Claude's Discretion
- Exact spec.json field names beyond locked sections
- How spec generator structures the models section (field grouping, ordering)
- Coherence checker edge case handling (e.g., base Odoo models not in registry)
- How reviewer agent formats the summary table
- Internal workflow structure for plan-module
- Error messages and validation feedback text

### Deferred Ideas (OUT OF SCOPE)
- Spec diffing between versions
- Auto-fix coherence violations
- Parallel spec generation for same-tier modules
- Spec templates per module type
- Web-based OCA research during spec generation
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPEC-01 | `/amil:plan-module` command and workflow created | Command file + workflow file following discuss-module pattern |
| SPEC-02 | `odoo-spec-generator` agent created that produces spec.json | New agent file at `agents/amil-spec-generator.md` |
| SPEC-03 | spec.json includes 12 sections + _available_models | Schema fully defined in CONTEXT.md specifics section |
| SPEC-04 | `_available_models` injected from registry into spec.json | Uses existing `tieredRegistryInjection()` from registry.cjs |
| SPEC-05 | `odoo-coherence-checker` agent created (actually CJS, not agent) | Pure CJS at `bin/lib/coherence.cjs` with 4 structural checks |
| SPEC-06 | Coherence validates: Many2one targets, duplicates, computed depends, security groups | 4 deterministic JSON checks, fully testable |
| SPEC-07 | Coherence report presented to human with pass/fail per check | Reviewer agent formats output for human consumption |
| SPEC-08 | Human approves spec; module status updated to `spec_approved` | Uses existing `cmdModuleStatusTransition()` from module-status.cjs |
| AGNT-02 | Planner agent specialized for Odoo module planning | Spec generator agent -- produces spec.json, not general planning |
| AGNT-04 | Reviewer agent specialized for Odoo review | Coherence presentation + spec summary formatting |
| TEST-03 | `tests/coherence.test.cjs` created | Unit tests for all 4 checks + edge cases |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Node.js built-ins (fs, path) | N/A | File I/O, path manipulation | Zero npm deps rule (CLAUDE.md) |
| node:test + node:assert | Node 18+ | Test framework | Already used in all existing tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| registry.cjs | Internal | `tieredRegistryInjection()`, `readRegistryFile()` | Spec generation (inject _available_models) |
| module-status.cjs | Internal | `cmdModuleStatusTransition()`, `readStatusFile()` | Status validation and transitions |
| core.cjs | Internal | `output()`, `error()` functions | CLI command output |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure CJS coherence | LLM-based validation | CJS is deterministic, testable, fast; LLM adds latency and non-determinism |
| JSON schema validation | Manual checks | Schema libs would add npm dependency; 4 checks are simple enough for hand-written code |

**Installation:**
```bash
# No installation needed -- zero npm deps, Node.js built-ins only
```

## Architecture Patterns

### Recommended Project Structure
```
amil/
  bin/lib/
    coherence.cjs          # NEW: Pure CJS coherence checker (4 checks)
  workflows/
    plan-module.md         # NEW: 10-step plan-module workflow
commands/amil/
  plan-module.md           # NEW: Slash command entry point
agents/
  amil-spec-generator.md  # NEW: Spec generation agent
  amil-spec-reviewer.md   # NEW: Coherence presentation agent
tests/
  coherence.test.cjs       # NEW: Coherence checker tests
```

### Pattern 1: CJS Library Module (coherence.cjs)
**What:** Pure JavaScript module with exported functions for each check plus a `runAllChecks()` orchestrator
**When to use:** For all deterministic validation logic
**Example:**
```javascript
// Source: Follows registry.cjs pattern from Phase 1
'use strict';

const fs = require('fs');
const path = require('path');
const { output, error } = require('./core.cjs');

function checkMany2oneTargets(spec, registry) {
  const violations = [];
  const availableModels = new Set([
    ...spec.models.map(m => m.name),
    ...Object.keys(registry.models || {})
  ]);

  for (const model of spec.models) {
    for (const field of model.fields) {
      if (field.type === 'Many2one' && field.comodel_name) {
        if (!availableModels.has(field.comodel_name)) {
          violations.push({
            model: model.name,
            field: field.name,
            target: field.comodel_name,
            reason: 'target model not in registry or spec'
          });
        }
      }
    }
  }

  return {
    check: 'many2one_targets',
    status: violations.length === 0 ? 'pass' : 'fail',
    violations
  };
}

function runAllChecks(spec, registry) {
  const checks = [
    checkMany2oneTargets(spec, registry),
    checkDuplicateModels(spec, registry),
    checkComputedDepends(spec, registry),
    checkSecurityGroups(spec, registry)
  ];

  return {
    status: checks.every(c => c.status === 'pass') ? 'pass' : 'fail',
    checks
  };
}

// CLI command function
function cmdCoherenceCheck(cwd, specPath, registryPath, raw) {
  // ... load files, call runAllChecks, output result
}

module.exports = {
  runAllChecks,
  checkMany2oneTargets,
  checkDuplicateModels,
  checkComputedDepends,
  checkSecurityGroups,
  cmdCoherenceCheck
};
```

### Pattern 2: Command + Workflow (plan-module)
**What:** Slash command file at `commands/amil/plan-module.md` delegates to workflow at `amil/workflows/plan-module.md`
**When to use:** For all user-facing commands
**Example:**
```markdown
<!-- commands/amil/plan-module.md -->
---
name: amil:plan-module
description: Generate spec.json for an Odoo module from its CONTEXT.md
argument-hint: "{module_name}"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<context>
Generates a complete spec.json for the specified module...
</context>
<execution_context>
@~/.claude/amil/workflows/plan-module.md
</execution_context>
```

### Pattern 3: Agent Spawning via Task()
**What:** Use `subagent_type` parameter to specify agent, pass all context in the prompt string
**When to use:** For researcher and spec generator agent invocations
**Example:**
```markdown
<!-- From discuss-module.md workflow pattern -->
Task(
  prompt="You are generating a spec.json for module ${MODULE_NAME}...
  MODULE CONTEXT:
  ---
  ${CONTEXT_MD_CONTENT}
  ---
  RESEARCH:
  ---
  ${RESEARCH_MD_CONTENT}
  ---
  TIERED REGISTRY:
  ---
  ${TIERED_REGISTRY_JSON}
  ---
  Follow your agent instructions...",
  subagent_type="amil-spec-generator",
  description="Spec generation: ${MODULE_NAME}"
)
```

### Pattern 4: spec.json Data Model
**What:** Spec uses arrays for models (not objects keyed by name) to preserve ordering
**When to use:** Spec generator output format
**Key detail:** The spec.json models section uses an array of model objects (each with `name`, `description`, `inherit`, `fields` array). This differs from model_registry.json which uses an object keyed by model name. The coherence checker must handle this difference.

### Anti-Patterns to Avoid
- **Running coherence checks via LLM agent:** Use pure CJS only -- deterministic, testable, fast
- **Storing spec.json in model_registry.json format:** Spec uses arrays, registry uses objects -- they serve different purposes
- **Hardcoding base Odoo model names in coherence checker:** Use the registry as source of truth; if a Many2one target is not in registry or spec, it fails (user can add base models to registry later)
- **Passing full registry to spec generator:** Use tieredRegistryInjection() to limit context window usage
- **Making reviewer agent modify spec.json:** Reviewer is read-only presentation; spec changes require re-running the generator

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Module status transitions | Custom state machine | `cmdModuleStatusTransition()` from module-status.cjs | Already validates transitions, handles atomic writes |
| Tiered registry filtering | Custom dependency resolution | `tieredRegistryInjection()` from registry.cjs | Already implements BFS, 3-tier filtering |
| Atomic JSON writes | Direct fs.writeFileSync | `atomicWriteJSON()` pattern from registry.cjs | Handles .tmp + rename + .bak backup |
| CLI output formatting | Custom console.log | `output()` and `error()` from core.cjs | Handles --raw flag, consistent JSON output |
| Agent spawning | Manual prompt construction | `Task()` with `subagent_type` | Established pattern from Phases 2-3 |

**Key insight:** Phase 4's new code is the coherence checker logic and the two agent markdown files. Everything else (status management, registry access, CLI infrastructure, agent spawning) reuses existing Phase 1-3 code.

## Common Pitfalls

### Pitfall 1: spec.json Array vs Registry Object Mismatch
**What goes wrong:** Coherence checker treats spec.models as an object (keyed by name) when it is actually an array
**Why it happens:** model_registry.json uses `{models: {"model.name": {...}}}` but spec.json uses `{models: [{name: "model.name", ...}]}`
**How to avoid:** In coherence checker, always iterate spec.models as an array; build a Set of model names from `spec.models.map(m => m.name)` for lookups
**Warning signs:** Tests pass with object-style fixtures but fail with real spec.json

### Pitfall 2: Computed Depends Path Resolution
**What goes wrong:** `depends` values like `"line_ids.amount"` fail validation because the checker only looks at top-level fields
**Why it happens:** Odoo computed field `depends` can reference related fields via dot notation (e.g., `order_id.partner_id.name`)
**How to avoid:** For the first segment of a depends path, verify the field exists on the model. For subsequent segments, verify the relational field's comodel has the next field. If the chain goes through models not in spec or registry, flag as a violation.
**Warning signs:** All simple depends pass but multi-hop depends all fail

### Pitfall 3: Base Odoo Models Not in Registry
**What goes wrong:** Many2one to `res.partner`, `res.users`, `res.company`, `account.move` etc. always fail coherence because these base models are not in the project's model_registry.json
**Why it happens:** The registry only contains project-generated models, not the 200+ base Odoo models
**How to avoid:** This is a discretion area. Options: (1) treat base model references as warnings not errors, (2) maintain a small allowlist of common base models, (3) let it fail and document that users should add needed base models. Recommendation: maintain a `BASE_ODOO_MODELS` Set of ~20 commonly referenced models (res.partner, res.users, res.company, res.currency, product.product, account.move, mail.thread, etc.) that are treated as valid targets without being in the registry.
**Warning signs:** Every spec fails coherence due to base model references

### Pitfall 4: Spec Generator Context Window Overflow
**What goes wrong:** Spec generator agent receives too much context (full CONTEXT.md + full RESEARCH.md + full tiered registry) and truncates output
**Why it happens:** Module CONTEXT.md can be 500+ lines, RESEARCH.md another 300+, tiered registry could be 1000+ lines for complex dependency graphs
**How to avoid:** The tiered registry injection already limits registry size. For CONTEXT.md and RESEARCH.md, pass them in full -- they are the primary inputs. If issues arise, the spec generator should be instructed to produce a complete but minimal spec.
**Warning signs:** spec.json missing later sections (security, portal, api_endpoints)

### Pitfall 5: Forgetting to Register CLI Subcommand
**What goes wrong:** `coherence check` command is implemented in coherence.cjs but never registered in amil-tools.cjs
**Why it happens:** New CJS modules need both the library code AND the CLI dispatch registration
**How to avoid:** After creating coherence.cjs, add `case 'coherence':` block in amil-tools.cjs main switch, require the module, and dispatch to cmdCoherenceCheck
**Warning signs:** Tests pass (direct require) but workflow fails (CLI invocation)

## Code Examples

### Coherence Check: Many2one Targets
```javascript
// Source: Designed from CONTEXT.md locked format
function checkMany2oneTargets(spec, registry) {
  const violations = [];
  const registryModelNames = new Set(Object.keys(registry.models || {}));
  const specModelNames = new Set(spec.models.map(m => m.name));

  for (const model of spec.models) {
    for (const field of (model.fields || [])) {
      if (field.type === 'Many2one' && field.comodel_name) {
        const target = field.comodel_name;
        if (!specModelNames.has(target) &&
            !registryModelNames.has(target) &&
            !BASE_ODOO_MODELS.has(target)) {
          violations.push({
            model: model.name,
            field: field.name,
            target,
            reason: 'target model not in registry or spec'
          });
        }
      }
    }
  }

  return {
    check: 'many2one_targets',
    status: violations.length === 0 ? 'pass' : 'fail',
    violations
  };
}
```

### Coherence Check: Computed Depends
```javascript
// Source: Designed from CONTEXT.md locked format
function checkComputedDepends(spec, registry) {
  const violations = [];
  const allFields = buildFieldMap(spec, registry);
  // allFields: Map<modelName, Set<fieldName>>

  for (const model of spec.models) {
    for (const field of (model.fields || [])) {
      if (field.compute && field.depends) {
        // depends is a comma-separated string or array
        const deps = Array.isArray(field.depends) ? field.depends : [field.depends];
        for (const dep of deps) {
          const segments = dep.split('.');
          // First segment must be a field on this model
          const firstField = segments[0];
          const modelFields = allFields.get(model.name);
          if (!modelFields || !modelFields.has(firstField)) {
            violations.push({
              model: model.name,
              field: field.name,
              depends_path: dep,
              reason: `field "${firstField}" not found on model "${model.name}"`
            });
          }
          // For multi-segment paths, follow the chain through relational fields
          // (simplified: check first segment only for v1)
        }
      }
    }
  }

  return {
    check: 'computed_depends',
    status: violations.length === 0 ? 'pass' : 'fail',
    violations
  };
}
```

### CLI Registration Pattern
```javascript
// Source: amil-tools.cjs existing pattern
// Add to the main switch in amil-tools.cjs:
case 'coherence': {
  const coherenceSub = args[1];
  switch (coherenceSub) {
    case 'check':
      coherenceMod.cmdCoherenceCheck(cwd, flagMap['--spec'], flagMap['--registry'], raw);
      break;
    default:
      error(`Unknown coherence subcommand: ${coherenceSub}. Available: check`);
  }
  break;
}
```

### Workflow: Human Approval Pattern
```markdown
## Step 9: Present Results and Get Approval

### 9a: Show coherence report
If coherence status is "fail":
  Present each failing check with its violations.
  Use AskUserQuestion: "Coherence check found violations. Would you like to?"
  Options: "approve_anyway" (proceed despite violations), "revise" (re-run spec generation), "abort" (stop workflow)

If coherence status is "pass":
  Show spec summary: model count, field count per model, business rules count, chain count, security groups.

### 9b: Get final approval
Use AskUserQuestion: "Approve this spec for ${MODULE}?"
Options: "approve", "revise", "abort"

If "approve":
  node "$HOME/.claude/amil/bin/amil-tools.cjs" module-status transition "${MODULE}" spec_approved --raw --cwd "$(pwd)"

If "revise":
  Go back to Step 5 (researcher) or Step 7 (spec generator) based on user choice.

If "abort":
  Stop workflow, no status change.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Amil planner agent | Odoo-specific spec generator agent | Phase 4 | Agent produces spec.json not PLAN.md |
| LLM-based validation | Pure CJS coherence checks | Phase 4 decision | Deterministic, testable, no latency |
| Manual cross-module checking | Automated registry-based coherence | Phase 4 | Catches broken references before generation |

**Deprecated/outdated:**
- None -- Phase 4 builds new capabilities, does not replace existing ones

## Open Questions

1. **Base Odoo model allowlist scope**
   - What we know: Many2one to res.partner, res.users, etc. are valid but not in project registry
   - What's unclear: Exact list of base models to include (20? 50?)
   - Recommendation: Start with ~20 commonly used base models (res.partner, res.users, res.company, res.currency, product.product, product.template, account.move, account.account, account.journal, mail.thread, mail.activity.mixin, uom.uom, ir.attachment, ir.sequence, ir.cron, base.automation, report.action, calendar.event, hr.employee, hr.department). Expand as needed.

2. **Computed depends path depth**
   - What we know: Odoo supports multi-hop depends like `order_id.partner_id.name`
   - What's unclear: How deep should coherence checker validate? Full chain or first segment only?
   - Recommendation: Validate first segment (field exists on model). For subsequent segments, validate if possible (relational field target model is known and has the next field), but treat unresolvable chains as warnings, not errors.

3. **Spec generator failure handling**
   - What we know: Agent may produce malformed JSON or incomplete spec
   - What's unclear: Retry strategy for spec generator failures
   - Recommendation: Validate that spec.json is valid JSON and has all 12 required top-level keys. If validation fails, present error to user and offer retry. No automatic retry.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | node:test + node:assert (Node 18+) |
| Config file | package.json `scripts.test` |
| Quick run command | `node --test tests/coherence.test.cjs` |
| Full suite command | `npm test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPEC-05 | Many2one target validation | unit | `node --test tests/coherence.test.cjs --test-name-pattern many2one` | No - Wave 0 |
| SPEC-06 | Duplicate model detection | unit | `node --test tests/coherence.test.cjs --test-name-pattern duplicate` | No - Wave 0 |
| SPEC-06 | Computed depends validation | unit | `node --test tests/coherence.test.cjs --test-name-pattern computed` | No - Wave 0 |
| SPEC-06 | Security group validation | unit | `node --test tests/coherence.test.cjs --test-name-pattern security` | No - Wave 0 |
| SPEC-05 | runAllChecks aggregation | unit | `node --test tests/coherence.test.cjs --test-name-pattern runAllChecks` | No - Wave 0 |
| SPEC-05 | CLI coherence check subcommand | integration | `node --test tests/coherence.test.cjs --test-name-pattern cli` | No - Wave 0 |
| SPEC-01 | plan-module command exists | smoke | Manual -- verify command file exists | No |
| SPEC-02 | spec generator agent file | smoke | Manual -- verify agent file exists | No |
| SPEC-03 | spec.json schema validation | unit | `node --test tests/coherence.test.cjs --test-name-pattern schema` | No - Wave 0 |
| SPEC-07 | coherence report formatting | manual-only | Manual -- visual inspection of reviewer output | No |
| SPEC-08 | module status transition | unit | `node --test tests/module-status.test.cjs --test-name-pattern transition` | Yes |
| AGNT-02 | spec generator agent format | manual-only | Manual -- agent produces valid spec.json | No |
| AGNT-04 | reviewer agent formatting | manual-only | Manual -- reviewer presents readable output | No |

### Sampling Rate
- **Per task commit:** `node --test tests/coherence.test.cjs`
- **Per wave merge:** `npm test`
- **Phase gate:** Full suite green before `/amil:verify-work`

### Wave 0 Gaps
- [ ] `tests/coherence.test.cjs` -- covers SPEC-05, SPEC-06, TEST-03
- [ ] Test fixtures: sample spec.json and sample registry for coherence tests
- [ ] No framework install needed -- node:test already available

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `amil/bin/lib/registry.cjs` -- tieredRegistryInjection(), readRegistryFile() APIs
- Codebase analysis: `amil/bin/lib/module-status.cjs` -- transition API, VALID_TRANSITIONS map
- Codebase analysis: `amil/bin/amil-tools.cjs` -- CLI dispatch pattern, command registration
- Codebase analysis: `commands/amil/discuss-module.md` -- command file format
- Codebase analysis: `amil/workflows/discuss-module.md` -- workflow structure, Task() spawning pattern
- Codebase analysis: `agents/amil-module-researcher.md` -- agent file format, subagent_type usage
- Codebase analysis: `tests/registry.test.cjs` -- test patterns, helpers usage
- Codebase analysis: `tests/helpers.cjs` -- createTempProject(), cleanup(), runGsdTools()
- CONTEXT.md: All locked formats for spec.json, coherence output, workflow steps

### Secondary (MEDIUM confidence)
- None needed -- all implementation details are internal to this codebase

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all internal libraries, no external dependencies
- Architecture: HIGH -- follows exact patterns from Phases 1-3
- Pitfalls: HIGH -- identified from code analysis of spec vs registry data model differences

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable -- internal tooling, no external dependencies)
