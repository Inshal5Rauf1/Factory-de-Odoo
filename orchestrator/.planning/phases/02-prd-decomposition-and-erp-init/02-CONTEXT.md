# Phase 2: PRD Decomposition and ERP Init - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning
**Source:** User-provided specifications (discussion session)

<domain>
## Phase Boundary

Phase 2 creates the `/amil:new-erp` command and workflow that:
1. Collects Odoo-specific config via interactive questions (Stage A)
2. Analyzes a PRD document with 4 parallel research agents (Stage B)
3. Merges agent outputs into a module decomposition
4. Presents decomposition to human for approval
5. Generates a flat ROADMAP.md with modules as phases
6. Implements tiered registry injection (REG-08)

</domain>

<decisions>
## Implementation Decisions

### new-erp Interactive Questions (Stage A)

**Locked: 7 sequential config questions, each writes to config.json immediately**

| # | Question | Default | Validation | Config key |
|---|----------|---------|------------|------------|
| Q1 | Odoo version? | "17.0" | ["17.0", "18.0"] | odoo.version |
| Q2 | Multi-company setup? (separate company per campus) | false | boolean | odoo.multi_company |
| Q3 | Localization? | "pk" | ["pk", "sa", "ae", "none"] | odoo.localization |
| Q4 | Existing Odoo modules being extended? | "none" | free text, comma-separated | odoo.existing_modules |
| Q5 | LMS integration? | "canvas" | ["canvas", "moodle", "none"] | odoo.canvas_integration |
| Q6 | Notification channels? | - | multi-select, subset of ["email", "whatsapp", "sms"] | odoo.notification_channels |
| Q7 | Deployment target? | "single" | ["single", "multi"] | odoo.deployment_target |

- No question about module count — agents determine that from PRD
- After Stage A, the `odoo` block is written to config.json
- Q4 answer (existing_modules) is passed to ALL 4 research agents as context AND stored in config

### PRD Input (Stage B prerequisite)

**Locked: PRD must exist as `.planning/PRD.md` or user is prompted to provide one**
- The PRD file is the input to all 4 research agents
- Command should check for `.planning/PRD.md` first, then prompt if missing

### 4 Research Agents — Parallel Task() Spawns

**Locked: 2 dedicated agent files + 2 inline Task() prompts**

**Agent 1: Module Boundary Analyzer** (`agents/amil-erp-decomposer.md`)
- Input: PRD text + existing_modules from config
- Job: Identify functional domains, propose module names (uni_{domain}), list models, note base Odoo depends
- Output: `.planning/research/module-boundaries.json`
- Format: `{ "modules": [{ "name", "description", "models", "base_depends", "estimated_complexity" }] }`
- Dedicated agent file (reusable — can re-invoke for re-decomposition)

**Agent 2: OCA Registry Checker** (`agents/amil-module-researcher.md`)
- Input: PRD text + existing_modules from config
- Job: For each domain, check if OCA/standard Odoo has existing module. Recommend build/extend/skip.
- Output: `.planning/research/oca-analysis.json`
- Format: `{ "findings": [{ "domain", "oca_module", "odoo_module", "recommendation", "reason" }] }`
- Uses Claude's training knowledge only (no web fetch, brave_search is false)
- Dedicated agent file (reused during discuss-module for deeper dives)

**Agent 3: Dependency Mapper** (inline Task() in workflow)
- Input: PRD text + existing_modules from config
- Job: Identify cross-domain references, build raw dependency list, flag circular risks
- Output: `.planning/research/dependency-map.json`
- Format: `{ "dependencies": [{ "module", "depends_on", "reason" }] }`
- Single-purpose, runs once during new-erp only

**Agent 4: Computation Chain Identifier** (inline Task() in workflow)
- Input: PRD text + existing_modules from config
- Job: Find every chain where data flows across models (stored computes, triggers, workflows)
- Output: `.planning/research/computation-chains.json`
- Format: `{ "chains": [{ "name", "description", "steps", "cross_module" }] }`
- Single-purpose, runs once during new-erp only

### Merge Strategy

**Locked: Sequential 5-step merge after all 4 agents complete**

1. Take module list from Agent 1 (module-boundaries.json) as the base
2. Cross-reference with Agent 2 (oca-analysis.json) — annotate each module with build/extend/skip
3. Take dependency list from Agent 3 — run through `dependency-graph.cjs` to get topological sort and tier assignment
4. Attach computation chains from Agent 4 to relevant modules
5. Write merged result to `.planning/research/decomposition.json`

### Human Approval Checkpoint

**Locked: Structured text presentation, not raw JSON**

Format:
```
ERP MODULE DECOMPOSITION — {N} modules across {M} tiers

TIER 1: Foundation (generate first)
  | Module      | Models   | Build     | Depends             |
  | uni_core    | 6        | NEW       | base, mail          |

TIER 2: Core Academic
  ...

COMPUTATION CHAINS (cross-module):
  1. chain_name: step1 -> step2 -> step3

WARNINGS:
  - Any circular risks, same-tier ordering issues, extend-module dependencies

Approve this decomposition? (yes / modify / regenerate)
```

The underlying data lives in `decomposition.json`. The presentation is a formatted string printed by the workflow.

### ROADMAP.md Generation

**Locked: Flat format, no roadmap.js changes**

Phase number = topological sort order. Tier info in detail bullets only.

```markdown
### Phase 1: uni_core
- Tier: 1 (Foundation)
- Models: uni.institution, uni.campus, uni.department, uni.program
- Depends: base, mail
- Build: NEW
- Status: not_started
```

- Uses existing `roadmap.js` parser — reads `### Phase N:` headers and bullet detail sections
- Modules within same tier ordered by topological sort
- `module_status.json` and `dependency-graph.cjs` handle actual tier logic and generation ordering
- This roadmap is for the TARGET ERP project, not the amil tool repo

### Tiered Registry Injection (REG-08)

**Locked: Three tiers based on dependency distance**
- Full models (all fields, all metadata): direct depends
- Field-list-only (model name + field names, no field metadata): transitive depends
- Names-only (just model names): everything else in registry
- Implemented as a function in registry.cjs that takes a module name and returns filtered registry

### Q4 Existing Modules — Dual Usage

**Locked: Stored in config AND passed to agents**
- Stored in `config.json` under `odoo.existing_modules` for later use during spec generation
- Passed as context to all 4 research agents during new-erp
- Does NOT pre-populate registry — that happens later via `/amil:map-erp` (v2)
- During new-erp, we only know module names, not their full model definitions

### Two Separate Roadmap Contexts

**Locked: amil tool roadmap vs ERP project roadmap are independent**
- amil repo has its own roadmap (Phase 1-5, building the tool)
- `new-erp` generates a roadmap for the target ERP project (uni_core, uni_student, etc.)
- These live in different directories, never interact

### Claude's Discretion

- Exact wording of interactive question prompts
- Error messages and validation feedback text
- Internal structure of the new-erp.md workflow file
- How the merge step handles edge cases (e.g., agent disagrees on module boundaries)
- Computation chain attachment logic (matching chain steps to module names)

</decisions>

<specifics>
## Specific Ideas

### Agent Output JSON Schemas

Module boundaries: modules[] with name, description, models[], base_depends[], estimated_complexity
OCA analysis: findings[] with domain, oca_module, odoo_module, recommendation (build_new/extend/skip), reason
Dependency map: dependencies[] with module, depends_on[], reason
Computation chains: chains[] with name, description, steps[] (model.field format), cross_module boolean

### Config Questions Map to Existing Config Validation

Q1 (version) already validated by CONF-02 (Phase 1)
Q6 (notification_channels) already validated by CONF-02 (Phase 1)
New validations needed: Q2 (boolean), Q3 (localization enum), Q5 (LMS enum), Q7 (deployment enum)

### Module Naming Convention

All custom modules use `uni_` prefix (e.g., uni_core, uni_student, uni_fee, uni_exam)
Models use dot notation: uni.institution, uni.student, uni.fee.structure

</specifics>

<deferred>
## Deferred Ideas

- `/amil:map-erp` for scanning existing Odoo modules into registry (v2)
- On-demand third-party model scanning (v2 ADVS-03)
- Web-based OCA registry checking via brave_search or WebFetch
- Real-time Odoo instance scanning via XML-RPC

</deferred>

---

*Phase: 02-prd-decomposition-and-erp-init*
*Context gathered: 2026-03-05 via user discussion*
