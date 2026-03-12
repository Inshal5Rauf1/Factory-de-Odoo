# Phase 4: Spec Generation and Coherence - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning
**Source:** User-provided specifications (discussion session)

<domain>
## Phase Boundary

Phase 4 creates the `/amil:plan-module` command and workflow that:
1. Loads module CONTEXT.md + decomposition entry + config
2. Spawns researcher agent for per-module Odoo research (RESEARCH.md)
3. Spawns spec generator agent with CONTEXT.md + RESEARCH.md + tiered registry
4. Runs coherence checker (pure CJS) against spec.json + model_registry.json
5. Presents coherence report + spec summary to human
6. On approval, transitions module status to `spec_approved`

</domain>

<decisions>
## Implementation Decisions

### spec.json Schema — Declarative Contract (SPEC-03)

**Locked: spec.json is a contract between amil (orchestrator) and amil (belt)**

The spec is declarative, not Odoo code. The belt's agents (amil-model-gen, amil-view-gen, amil-security-gen) translate declarations into actual Odoo code.

12 top-level sections: models, fields, business_rules, computation_chains, workflow, view_hints, reports, notifications, cron_jobs, security, portal, api_endpoints

Plus `_available_models` — tiered registry injection written INTO spec.json as read-only reference for the belt.

**Computation chains format (locked):**
```json
"computation_chains": [
  {
    "name": "cgpa_chain",
    "steps": [
      {"model": "uni.course.result", "field": "grade_point", "trigger": "on_write"},
      {"model": "uni.enrollment", "field": "semester_gpa", "trigger": "depends"},
      {"model": "uni.student", "field": "cgpa", "trigger": "depends"}
    ]
  }
]
```
No field type info — belt's model architect agent looks up types from the models section of the same spec.

**View hints format (locked):**
```json
"view_hints": [
  {"model": "uni.fee.line", "view_type": "tree", "key_fields": ["student_id", "fee_structure_id", "total_amount", "state"], "notes": "color-code by state"},
  {"model": "uni.fee.line", "view_type": "form", "key_fields": ["student_id", "fee_structure_id", "line_ids", "total_amount"], "notes": "notebook with lines tab and payment history tab"}
]
```
No XML. Belt's amil-view-gen translates hints into Odoo XML views.

**Security format (locked):**
```json
"security": {
  "groups": ["uni_fee.group_fee_manager", "uni_fee.group_fee_officer"],
  "access_rules": [
    {"model": "uni.fee.line", "group": "uni_fee.group_fee_officer", "perm_read": true, "perm_write": true, "perm_create": true, "perm_unlink": false}
  ],
  "record_rules": [
    {"name": "fee_campus_rule", "model": "uni.fee.line", "domain": "campus_id scoped", "description": "Fee officers see only their campus fees"}
  ]
}
```
Record rule domains stay as natural language descriptions. Belt's amil-security-gen translates to actual `ir.rule` domain expressions.

### Coherence Checker — Pure CJS (SPEC-05, SPEC-06)

**Locked: Option A — pure CJS library, no agent, fully deterministic**

File: `bin/lib/coherence.cjs`
CLI subcommand: `amil-tools coherence check --spec X --registry Y`
Test file: `tests/coherence.test.cjs`

4 structural checks, all JSON pattern matching:

1. **Many2one targets**: Iterate spec models -> for each Many2one field -> check `comodel_name` exists in either spec models or registry models. Pass/fail per field.
2. **Duplicate models**: Check spec model names against registry. If model already exists and module isn't the owner, flag it.
3. **Computed field sources**: For each computed field with `depends`, verify each depend path resolves (model.field exists in spec or registry).
4. **Security groups**: For each group referenced in access_rules or record_rules, verify it's either defined in this spec's groups or exists in the registry's security_groups.

**Output format (locked):**
```json
{
  "status": "fail",
  "checks": [
    {"check": "many2one_targets", "status": "fail", "violations": [
      {"model": "uni.fee.line", "field": "enrollment_id", "target": "uni.enrollment", "reason": "target model not in registry or spec"}
    ]},
    {"check": "duplicate_models", "status": "pass", "violations": []},
    {"check": "computed_depends", "status": "pass", "violations": []},
    {"check": "security_groups", "status": "pass", "violations": []}
  ]
}
```

### Spec Generation Flow (SPEC-01, SPEC-02, SPEC-04)

**Locked: Two sequential agents (researcher then generator), tiered registry injection**

Flow for `/amil:plan-module uni_fee`:

1. Workflow loads module's CONTEXT.md + decomposition entry + config
2. Spawn researcher agent (`amil-module-researcher.md`) with module context -> produces `.planning/modules/uni_fee/RESEARCH.md`
3. Spawn spec generator agent (`amil-spec-generator.md`) with CONTEXT.md + RESEARCH.md + tiered registry -> produces `.planning/modules/uni_fee/spec.json`
4. Run `coherence.cjs` against spec.json + model_registry.json (pure CJS, no agent)
5. Present spec summary + coherence report to human
6. On approval, update module_status.json to `spec_approved`

**Registry injection detail:** Tiered via `tieredRegistryInjection()` from Phase 2:
- Full detail for direct dependencies (modules in `depends` list)
- Model names + key fields for transitive dependencies
- Nothing for unrelated modules
- Written INTO spec.json as `_available_models` section (belt picks up from same file)

### Human Approval Flow (SPEC-07, SPEC-08)

**Locked: Coherence report first, then formatted spec summary**

Presentation order:
1. Coherence report: pass/fail per check, violations listed
2. If coherence fails: show violations, ask human to approve anyway or request revision
3. If coherence passes: show spec summary (model count, field count per model, business rules count, chain count, security groups)
4. NOT the full JSON — user can `cat .planning/modules/{module}/spec.json` for full detail
5. Approval transitions status to `spec_approved`

### Reviewer Agent Scope (AGNT-04)

**Locked: Reviewer agent IS the coherence presentation layer**

- `amil-spec-reviewer.md` reads CJS coherence report + spec.json
- Formats human-readable summary with Odoo-specific context (e.g., "Many2one to uni.enrollment — this model is in uni_student module, Tier 2")
- Runs inline in plan-module workflow after coherence check
- NOT a separate command — part of the plan-module flow

### Spec Generator Agent (AGNT-02)

**Locked: New dedicated agent file**

- `agents/amil-spec-generator.md` — produces spec.json from CONTEXT.md + RESEARCH.md + tiered registry
- Single-shot generation (all 12 sections in one pass)
- Must include `_available_models` section from tiered registry injection
- Agent receives: module CONTEXT.md, module RESEARCH.md, decomposition entry, config.json odoo block, tiered registry output

### Claude's Discretion

- Exact spec.json field names beyond the locked sections above
- How spec generator structures the models section (field grouping, ordering)
- Coherence checker edge case handling (e.g., base Odoo models not in registry)
- How reviewer agent formats the summary table
- Internal workflow structure for plan-module
- Error messages and validation feedback text

</decisions>

<specifics>
## Specific Ideas

### spec.json Full Schema Reference

```json
{
  "module": "uni_fee",
  "version": "17.0",
  "models": [
    {
      "name": "uni.fee.structure",
      "description": "Fee structure template",
      "inherit": null,
      "fields": [
        {"name": "name", "type": "Char", "required": true, "string": "Fee Structure Name"},
        {"name": "program_id", "type": "Many2one", "comodel_name": "uni.program", "required": true},
        {"name": "total_amount", "type": "Monetary", "compute": "_compute_total", "store": true}
      ]
    }
  ],
  "business_rules": [...],
  "computation_chains": [...],
  "workflow": [...],
  "view_hints": [...],
  "reports": [...],
  "notifications": [...],
  "cron_jobs": [...],
  "security": {...},
  "portal": [...],
  "api_endpoints": [...],
  "_available_models": {
    "direct": {...},
    "transitive": {...},
    "rest": [...]
  }
}
```

### coherence.cjs CLI Interface

```bash
# Check a spec against registry
node amil/bin/amil-tools.cjs coherence check --spec .planning/modules/uni_fee/spec.json --registry .planning/model_registry.json

# Output: JSON coherence report to stdout
```

### plan-module Command Flow

```
/amil:plan-module uni_fee
  |
  v
1. Validate module exists in module_status.json (status: "planned")
2. Check for existing spec.json (offer overwrite/skip)
3. Load CONTEXT.md from .planning/modules/uni_fee/
4. Load decomposition entry from decomposition.json
5. Spawn researcher agent -> RESEARCH.md
6. Build tiered registry via tieredRegistryInjection()
7. Spawn spec generator agent -> spec.json (includes _available_models)
8. Run coherence.cjs check
9. Spawn reviewer agent -> formatted presentation
10. Human approval -> module_status transition to spec_approved
```

</specifics>

<deferred>
## Deferred Ideas

- Spec diffing between versions (track what changed between revisions)
- Auto-fix coherence violations (too risky, human should decide)
- Parallel spec generation for same-tier modules (registry race conditions)
- Spec templates per module type (premature — let agent decide structure)
- Web-based OCA research during spec generation (v2 ADVS-03)

</deferred>

---

*Phase: 04-spec-generation-and-coherence*
*Context gathered: 2026-03-05 via user discussion*
