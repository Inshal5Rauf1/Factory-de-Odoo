# amil: Product Requirements Document

## Fork of Amil → Odoo ERP Module Orchestrator

**Version:** 1.0
**Date:** 2026-03-05
**Author:** TIFAQM Engineering

---

## 1. Executive Summary

amil is a fork of Amil (Get Shit Done) — a Claude Code project management extension — specialized for orchestrating Odoo ERP module generation at scale. It takes a university ERP PRD, decomposes it into 20+ modules, and drives the Odoo-Development-Automation belt (amil) to produce production-ready Odoo modules with cross-module coherence.

### Architecture

```
amil (FORK of Amil — this repo)
  │  Orchestrates module decomposition, dependency ordering,
  │  cross-module state (model registry), human checkpoints
  │
  └── amil (UNCHANGED — separate repo, Amil extension → becomes amil extension)
        │  Single-module generation pipeline
        │  8 agents, 13 knowledge files, Jinja2 templates, Docker validation
        │
        └── amil-utils (Python CLI, called from within amil agents)
              AST analysis, ChromaDB search, MCP server, Docker ops
```

**Key relationship:** amil currently extends Amil. After forking, amil's install references change from `~/.claude/amil/` to `~/.claude/amil/`. amil itself stays in its own repo, untouched except for this path change.

---

## 2. Amil Codebase Structure (Pre-Fork Baseline)

The Amil repo contains ~110 files across these directories:

### 2.1 CLI Tooling

| File | Purpose | Fork Action |
|------|---------|-------------|
| `bin/amil-tools.cjs` | Main CLI router (~2,000+ lines). Dispatches to lib modules. Handles JSON output, `@file:` temp payloads, `--raw` mode. | **Rename** entry points from `gsd` to `amil`. Add new subcommands for registry, module-status, computation-chains. Extend `main()` router with new command handlers. |
| `bin/lib/core.js` | State reading/writing, config management, project init | **Extend** with model registry CRUD, module status tracking, computation chain management. Add `odoo` config block parsing. |
| `bin/lib/commands.js` | Command registration, dispatch, help generation | **Modify** command prefix from `gsd` to `amil`. Register new commands (new-erp, map-erp, discuss-module, plan-module, generate-module, check-module, audit-erp). |
| `bin/lib/phase.js` | Phase CRUD, transitions, status tracking | **Extend** to support module-as-phase semantics. Each Odoo module maps to a Amil phase. Add module dependency ordering within phase transitions. |
| `bin/lib/roadmap.js` | ROADMAP.md parsing, phase detail sections | **Extend** parser to understand module dependency tiers (foundation → core → operations → communication) and wave-based execution mapping. |
| `bin/lib/state.js` | STATE.md frontmatter read/write, status sync | **Extend** with module-level state fields (current_module, modules_completed, modules_remaining, registry_version). |
| `bin/lib/config.js` | `.planning/config.json` read/write, schema validation | **Extend** schema with `odoo` block (version, multi_company, localization, belt_repo_path, default_depends, security_framework, scope_levels, notification_channels, canvas_integration). |
| `bin/lib/frontmatter.js` | YAML frontmatter manipulation | **Keep as-is.** |
| `bin/lib/verify.js` | Verification logic, pass/fail tracking | **Extend** with Odoo-specific verification: model registry consistency check, cross-module Many2one validation, security scope completeness. |
| `bin/install.js` | Installer (~1,400 lines). Multi-runtime support, path replacement, hook registration, manifest generation. | **Heavy rewrite.** Change package name to `amil`. Change install path to `~/.claude/amil/`. Remove OpenCode/Gemini/Codex runtime support (Claude Code only). Add amil dependency check (verify `~/.claude/amil/` exists). Add Python dependency check (amil-utils). |

### 2.2 Commands (`commands/gsd/*.md`)

Amil has 32 command files. Each is a markdown file with frontmatter defining the slash command and body containing the orchestration instructions.

#### Commands to HEAVY REWRITE (new Odoo-specific logic)

| Amil Command File | New Name | What Changes |
|------------------|----------|-------------|
| `commands/gsd/new-project.md` | `commands/amil/new-erp.md` | Replace generic project questions with Odoo-specific init: version, multi-company, localization, module count, existing modules, LMS integration, notification channels, deployment target. Spawn 4 parallel research agents (module boundary analysis, OCA registry check, cross-module dependency mapping, computation chain identification). Output: module dependency graph with phased generation order, not generic roadmap. |
| `commands/gsd/map-codebase.md` | `commands/amil/map-erp.md` | Replace generic codebase scanning with 4 Odoo-specific agents: manifest parser (`__manifest__.py` → dependency graph), model AST analyzer (fields, methods, inheritance → registry), security scanner (`ir.model.access.csv` + record rules), view pattern detector (XML → tabs, smart buttons, kanban). Output: `model_registry.json` + `erp_map.md`. Can also use amil's MCP server for live XML-RPC introspection of running instances. |
| `commands/gsd/plan-phase.md` | `commands/amil/plan-module.md` | Replace generic planning with spec.json generation. Spawn odoo-spec-generator agent to produce structured spec (models, business_rules, computation_chains, workflow, view_hints, reports, notifications, cron_jobs, security, portal, api_endpoints). Inject `_available_models` from registry. Run cross-module coherence check before human approval: Many2one targets exist, computation chain depends match, security scope fields present, no duplicate model names. |
| `commands/gsd/execute-phase.md` | `commands/amil/generate-module.md` | Replace generic execution with belt invocation. Load spec.json, inject current model registry, spawn amil pipeline as `Task()` subagent with fresh 200K context. Belt runs multi-pass pipeline (scaffold → models → views → logic → security → reports → tests → validate). On success: update model registry atomically, git commit. On failure: present errors with retry/manual-fix/skip options. |
| `commands/gsd/verify-work.md` | `commands/amil/check-module.md` | Replace generic verification with 4-level checker: CHK-01 structural (Many2one targets, ACLs, mail.thread, syntax), CHK-02 cross-module (foreign keys, computed chains, security scopes, dependency graph), CHK-03 spec coverage (manifest vs spec — implemented vs stubbed), CHK-04 integration (Docker install, run tests across boundaries). Structured pass/fail for human sign-off. |
| `commands/gsd/audit-milestone.md` | `commands/amil/audit-erp.md` | Replace generic audit with full ERP audit: Docker install all modules together, run integration tests across boundaries, trace computation chains end-to-end, verify security scopes, check portal route conflicts, validate cron jobs reference existing methods, production readiness checklist. |

#### Commands to MEDIUM REWRITE (adapt to module context)

| Amil Command File | New Name | What Changes |
|------------------|----------|-------------|
| `commands/gsd/discuss-phase.md` | `commands/amil/discuss-module.md` | Replace generic discussion with module-type-specific question templates. Spawn odoo-module-questioner agent with module type context. Fee module: monetary vs float, fee structure, penalty method, payment channels, challan format, partial payments, waivers, scholarships. Exam module: grading scales, makeup policy, proctoring. Student module: enrollment states, program transfers, academic holds. Output: `{module}-CONTEXT.md`. |
| `commands/gsd/complete-milestone.md` | `commands/amil/complete-phase.md` | Add: registry archival (snapshot model_registry.json at completion), release tagging per module tier, update module_status.json to "shipped". |
| `commands/gsd/progress.md` | `commands/amil/progress.md` | Add: module status table (planned/spec_approved/generated/checked/shipped), registry stats (total models, total fields, cross-module references), computation chain completion status, overall ERP readiness percentage. |
| `commands/gsd/quick.md` | `commands/amil/quick.md` | Add: quick field addition (add field to existing generated module + update registry), quick bug fix (fix without full cycle), quick view modification. Must update registry on any model change. |

#### Commands to LIGHT REWRITE (rename prefix, minimal changes)

| Amil Command File | New Name | What Changes |
|------------------|----------|-------------|
| `commands/gsd/pause-work.md` | `commands/amil/pause-work.md` | Rename prefix only. Add: save current module context on pause. |
| `commands/gsd/resume-work.md` | `commands/amil/resume-work.md` | Rename prefix only. Add: reload model registry on resume. |
| `commands/gsd/help.md` | `commands/amil/help.md` | Update help text with Odoo-specific commands and workflow description. |
| `commands/gsd/add-todo.md` | `commands/amil/add-todo.md` | Rename prefix only. |
| `commands/gsd/debug.md` | `commands/amil/debug.md` | Rename prefix only. Add: Odoo-specific debug context (check Docker logs, pylint-odoo output, model registry state). |
| `commands/gsd/settings.md` | `commands/amil/settings.md` | Rename prefix. Add `odoo` config block editing (version, multi_company, localization, etc.). |
| `commands/gsd/set-profile.md` | `commands/amil/set-profile.md` | Rename prefix only. |

#### All remaining Amil commands

Rename prefix from `/amil:` to `/amil:`. Keep behavior. This includes any utility commands, status commands, transition commands, etc. not listed above.

### 2.3 Agents (`agents/*.md`)

Amil has ~12 agent prompt files. Each defines a persona with role, constraints, and output format.

#### Agents to REWRITE for Odoo context

| Amil Agent | New Name | What Changes |
|-----------|----------|-------------|
| `agents/researcher.md` | `agents/researcher.md` | Specialize for Odoo research: OCA module registry, Odoo documentation, field type patterns, common ERP patterns. Keep research methodology (3+ sources, citation, conflict resolution) but add Odoo knowledge base references. |
| `agents/planner.md` | `agents/planner.md` | Specialize for Odoo module planning: spec.json structure, model decomposition, dependency analysis, wave-based execution. Keep planning methodology (waves, task granularity, dependency tracking) but output spec.json instead of PLAN.md. |
| `agents/executor.md` | `agents/executor.md` | Specialize for belt orchestration: loading spec.json, injecting registry, invoking amil agents, collecting manifests. The actual code generation stays in amil — this agent coordinates. |
| `agents/reviewer.md` | `agents/reviewer.md` | Specialize for Odoo review: model naming conventions, security patterns, view structure, Python code quality (pylint-odoo rules). Keep review methodology (pass/fail, actionable feedback) but apply Odoo standards. |
| `agents/verifier.md` | `agents/verifier.md` | Specialize for Odoo verification: Docker install test, cross-module reference validation, computation chain tracing, security scope completeness. Keep goal-backward verification pattern. |

#### Agents to KEEP as-is

| Amil Agent | Reason |
|-----------|--------|
| `agents/debugger.md` | Generic debugging works for Odoo too. May add Odoo-specific debug hints (Docker logs, pylint-odoo, XML validation). |
| `agents/questioner.md` | Keep as base, but odoo-module-questioner replaces it for module discussions. |

#### NEW Agents (not in Amil)

| New Agent | Purpose | Format Pattern |
|-----------|---------|---------------|
| `agents/odoo-module-researcher.md` | PRD decomposition: analyze PRD text, identify module boundaries, detect OCA overlaps, map computation chains, output dependency graph. Spawned by `/amil:new-erp`. | Follow Amil agent format: role definition, constraints, input/output specification, tool usage instructions. |
| `agents/odoo-spec-generator.md` | Generate spec.json from module CONTEXT + RESEARCH + registry. Knows Odoo model patterns, field types, security patterns, view patterns. Spawned by `/amil:plan-module`. | Same format. Include spec.json schema as reference in prompt. |
| `agents/odoo-coherence-checker.md` | Cross-module validation: Many2one target existence, computation chain integrity, security scope consistency, duplicate detection. Runs against model_registry.json. Spawned by `/amil:plan-module` and `/amil:check-module`. | Same format. Input: spec.json + model_registry.json. Output: structured pass/fail with specific violations. |
| `agents/odoo-module-questioner.md` | Module-type-specific questions. Knows what to ask for fee modules vs exam modules vs student modules vs HR modules. Spawned by `/amil:discuss-module`. | Same format. Include question templates per module type. |
| `agents/odoo-erp-decomposer.md` | Master decomposition agent: reads full PRD, outputs module list with dependency tiers, estimated complexity, and generation order. Spawned by `/amil:new-erp`. | Same format. Output: structured JSON with modules, tiers, dependencies. |
| `agents/odoo-audit-agent.md` | Full ERP audit: Docker install all, integration test orchestration, computation chain end-to-end tracing, production checklist generation. Spawned by `/amil:audit-erp`. | Same format. |

### 2.4 Workflows (`workflows/*.md`)

Amil has ~30 workflow files. These are multi-step orchestration scripts.

#### Workflows to REWRITE

| Amil Workflow | New Name | What Changes |
|--------------|----------|-------------|
| `workflows/new-project.md` | `workflows/new-erp.md` | Replace generic flow with: (1) Odoo config questions → write config.json with `odoo` block, (2) Spawn 4 parallel research agents on PRD, (3) Merge research → module dependency graph, (4) Human reviews decomposition, (5) Generate ROADMAP.md with module tiers as phases, each module as a phase detail section. |
| `workflows/plan-phase.md` | `workflows/plan-module.md` | Replace with: (1) Load module CONTEXT.md + RESEARCH.md + model_registry.json, (2) Spawn odoo-spec-generator to produce spec.json, (3) Spawn odoo-coherence-checker to validate spec against registry, (4) Present coherence report + spec to human for approval, (5) On approval: update module_status.json to "spec_approved". |
| `workflows/execute-phase.md` | `workflows/generate-module.md` | Replace with: (1) Load spec.json + model_registry.json, (2) Prepare belt invocation context (inject registry as `_available_models`), (3) Spawn amil pipeline as `Task()` with fresh context, (4) Belt returns generation_manifest.json, (5) On success: parse manifest → update model_registry.json (add new models/fields) → atomic git commit → update module_status.json to "generated", (6) On failure: present errors, offer retry/manual-fix/skip. |
| `workflows/verify-work.md` | `workflows/check-module.md` | Replace with: (1) Run CHK-01 structural checks, (2) Run CHK-02 cross-module checks against registry, (3) Run CHK-03 spec coverage (diff manifest vs spec), (4) Run CHK-04 Docker integration (invoke amil's validate command), (5) Present structured results for human sign-off, (6) On pass: update module_status.json to "checked". |
| `workflows/discuss-phase.md` | `workflows/discuss-module.md` | Replace with: (1) Detect module type from spec name/description, (2) Spawn odoo-module-questioner with type-specific template, (3) Interactive Q&A session, (4) Write answers to {module}-CONTEXT.md. |

#### Workflows to EXTEND

| Amil Workflow | What Changes |
|--------------|-------------|
| `workflows/transition.md` | Add: after module check passes, if next module depends on this one, auto-inject updated registry into next module's context. |
| `workflows/complete-milestone.md` | Add: snapshot model_registry.json, tag release per tier, update module_status.json for all modules in tier. |
| `workflows/audit-milestone.md` → `workflows/audit-erp.md` | Major extension: Docker install all modules, integration tests, computation chain tracing, security audit, portal conflict check, cron validation, production checklist. |

#### Workflows to KEEP (rename prefix only)

All remaining workflows: pause, resume, debug-session, quick-fix, etc. Rename references from `gsd` to `amil`.

### 2.5 Templates (`templates/*.md`)

Amil has templates for project artifacts. These get Odoo-specialized versions.

| Amil Template | Fork Action |
|-------------|-------------|
| `templates/project.md` | Rewrite as Odoo ERP project template. Include: Odoo version, module list, dependency tiers, model registry summary, ERP scope. |
| `templates/requirements.md` | Extend with Odoo-specific requirement categories: models, security groups, computation chains, reports, portals, integrations (Canvas, WhatsApp). |
| `templates/research.md` | Extend with Odoo research structure: OCA module analysis, existing Odoo module audit, field type patterns, localization requirements. |
| `templates/codebase-summary.md` | Rewrite for Odoo addons structure: module manifest summary, model registry excerpt, security group map, view pattern inventory. |
| All other templates | Rename references, keep structure. |

### 2.6 Reference Docs (`reference/*.md`)

Amil includes reference documentation for agents and workflows.

| Reference Doc | Fork Action |
|--------------|-------------|
| `reference/checkpoints.md` | Extend with Odoo checkpoints: post-spec coherence, post-generation registry update, post-check human sign-off, post-tier integration test. |
| `reference/git-integration.md` | Extend with Odoo git patterns: one commit per module generation, registry snapshot commits, tier completion tags. |
| `reference/verification-patterns.md` | Extend with Odoo verification: 4-level checker, Docker-based integration, computation chain tracing. |
| `reference/tdd-patterns.md` | Extend with Odoo test patterns: TransactionCase, HttpCase, tagged tests, Docker test runner. |
| All other references | Keep as-is or light adaptation. |

### 2.7 Hooks

Amil has hooks for statusline, context monitor, and update checker.

| Hook | Fork Action |
|------|-------------|
| `hooks/statusline.md` | Extend to show: current module name, module progress (3/20), registry stats (45 models), current phase within module (planning/generating/checking). |
| `hooks/context-monitor.md` | Extend context budget awareness with: model registry size tracking (registry grows with each module, may need pruning for context window), belt invocation context reservation (200K for fresh Task() context). |
| `hooks/update-checker.md` | Change update check URL to amil repo. Remove Amil upstream check. |

### 2.8 System Files

| File | Fork Action |
|------|-------------|
| `CLAUDE.md` | **Heavy rewrite.** Define amil as Odoo ERP orchestrator. Document: three-layer architecture, command reference, state file locations, model registry format, belt invocation pattern, agent roster. This is the primary context document Claude Code reads. |
| `package.json` | Rename package to `amil`. Update description, repository URL, author. Keep devDeps (c8, esbuild). |
| `README.md` | Full rewrite for amil documentation. |
| `CHANGELOG.md` | Start fresh from v0.1.0. |
| `LICENSE` | Keep MIT or change per TIFAQM preference. |
| `.github/` | Update CI workflows, issue templates, PR template for amil context. |

### 2.9 Tests (`tests/`)

Amil has 13 test files with 428+ tests.

| Test File | Fork Action |
|-----------|-------------|
| `tests/core.test.js` | Extend with: model registry read/write, module status transitions, computation chain CRUD. |
| `tests/commands.test.js` | Rewrite command dispatch tests for `amil:*` prefix. Add new command tests. |
| `tests/config.test.js` | Add tests for `odoo` config block validation. |
| `tests/phase.test.js` | Extend with module-as-phase mapping tests. |
| `tests/roadmap.test.js` | Extend with dependency tier parsing tests. |
| `tests/state.test.js` | Extend with module-level state field tests. |
| `tests/init.test.js` | Rewrite for Odoo-specific initialization flow. |
| `tests/verify.test.js` | Extend with Odoo verification logic tests. |
| All other tests | Rename references, adapt assertions. |

#### NEW Tests

| New Test File | Coverage |
|--------------|----------|
| `tests/registry.test.js` | Model registry CRUD, atomic updates, rollback, cross-module validation, duplicate detection. |
| `tests/module-status.test.js` | Status transitions (planned → spec_approved → generated → checked → shipped), invalid transitions, tier completion. |
| `tests/coherence.test.js` | Many2one target validation, computation chain integrity, security scope consistency, spec coverage diffing. |
| `tests/belt-integration.test.js` | Spec.json formatting, registry injection, manifest parsing, registry update from manifest. |

---

## 3. New State Files

These are created/managed by amil in the `.planning/` directory alongside Amil's existing state files.

### 3.1 Model Registry (`.planning/model_registry.json`)

Central cross-module state. Updated after every successful module generation.

```json
{
  "_meta": {
    "version": 12,
    "last_updated": "2026-03-05T10:30:00Z",
    "modules_contributing": ["uni_core", "uni_student", "uni_fee"]
  },
  "models": {
    "uni.student": {
      "module": "uni_student",
      "model_type": "regular",
      "_inherit": ["mail.thread", "mail.activity.mixin"],
      "_inherits": {},
      "fields": {
        "name": {"type": "Char", "required": true, "string": "Student Name"},
        "registration_no": {"type": "Char", "required": true, "unique": true},
        "cgpa": {"type": "Float", "compute": "_compute_cgpa", "store": true, "depends": ["enrollment_ids.grade_point"]},
        "program_id": {"type": "Many2one", "comodel_name": "uni.program", "required": true},
        "enrollment_ids": {"type": "One2many", "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
        "fee_ids": {"type": "One2many", "comodel_name": "uni.fee.line", "inverse_name": "student_id"},
        "scope_institution_id": {"type": "Many2one", "comodel_name": "uni.institution"},
        "scope_campus_id": {"type": "Many2one", "comodel_name": "uni.campus"}
      },
      "methods": ["_compute_cgpa", "action_enroll", "action_graduate"],
      "sql_constraints": [["registration_no_unique", "UNIQUE(registration_no)", "Registration number must be unique"]],
      "security_groups": ["uni_core.group_registrar", "uni_core.group_student"],
      "record_rules": ["uni_student_campus_rule"],
      "mail_thread": true,
      "abstract": false,
      "transient": false
    }
  },
  "security_groups": {
    "uni_core.group_registrar": {
      "module": "uni_core",
      "implied_ids": ["base.group_user"],
      "category": "uni_core.module_category_university"
    }
  },
  "menu_items": {
    "uni_student.menu_student_root": {
      "module": "uni_student",
      "parent": null,
      "groups": ["uni_core.group_registrar"]
    }
  }
}
```

**CLI tooling additions** (in `bin/lib/core.js` or new `bin/lib/registry.js`):
- `amil-tools registry read` — dump full registry
- `amil-tools registry read-model <model_name>` — single model
- `amil-tools registry update <module_name> <manifest_json>` — atomic update from belt manifest
- `amil-tools registry rollback` — restore previous version
- `amil-tools registry validate` — run cross-model consistency checks
- `amil-tools registry stats` — model count, field count, cross-module references

### 3.2 Computation Chains (`.planning/computation_chains.json`)

```json
{
  "chains": {
    "cgpa_chain": {
      "description": "Student CGPA calculation from enrollment grades",
      "steps": [
        {"model": "uni.enrollment", "field": "grade_point", "type": "stored_compute", "module": "uni_enrollment"},
        {"model": "uni.student", "field": "cgpa", "type": "stored_compute", "depends": ["enrollment_ids.grade_point"], "module": "uni_student"},
        {"model": "uni.merit.list", "field": "rank", "type": "stored_compute", "depends": ["student_id.cgpa"], "module": "uni_merit"}
      ],
      "status": "partial",
      "completed_steps": 2,
      "total_steps": 3
    },
    "fee_penalty_chain": {
      "description": "Fee generation → penalty calculation → challan → payment",
      "steps": [
        {"model": "uni.fee.structure", "field": "amount", "type": "config", "module": "uni_fee"},
        {"model": "uni.fee.line", "field": "total_amount", "type": "stored_compute", "module": "uni_fee"},
        {"model": "uni.fee.penalty", "field": "penalty_amount", "type": "cron_compute", "module": "uni_fee"},
        {"model": "uni.challan", "field": "net_amount", "type": "stored_compute", "module": "uni_fee"},
        {"model": "uni.payment", "field": "status", "type": "workflow", "module": "uni_payment"}
      ],
      "status": "planned",
      "completed_steps": 0,
      "total_steps": 5
    }
  }
}
```

### 3.3 Security Scope (`.planning/security_scope.json`)

```json
{
  "framework": "dynamic_rbac",
  "scope_levels": ["institution", "campus", "faculty", "department", "program"],
  "scope_fields": {
    "institution": "scope_institution_id",
    "campus": "scope_campus_id",
    "faculty": "scope_faculty_id",
    "department": "scope_department_id",
    "program": "scope_program_id"
  },
  "groups": {
    "uni_core.group_super_admin": {"scope": "institution", "implied": ["base.group_system"]},
    "uni_core.group_registrar": {"scope": "campus", "implied": ["base.group_user"]},
    "uni_core.group_hod": {"scope": "department", "implied": ["base.group_user"]},
    "uni_core.group_faculty": {"scope": "department", "implied": ["base.group_user"]},
    "uni_core.group_student": {"scope": "program", "implied": ["base.group_portal"]}
  },
  "models_with_scope": ["uni.student", "uni.enrollment", "uni.fee.line", "uni.exam.result"]
}
```

### 3.4 Module Status (`.planning/module_status.json`)

```json
{
  "modules": {
    "uni_core": {"status": "shipped", "tier": 1, "depends": ["base", "mail"], "spec_version": 3, "generated_at": "2026-03-04T10:00:00Z", "checked_at": "2026-03-04T11:00:00Z"},
    "uni_student": {"status": "checked", "tier": 2, "depends": ["uni_core"], "spec_version": 2, "generated_at": "2026-03-04T14:00:00Z", "checked_at": "2026-03-04T15:00:00Z"},
    "uni_fee": {"status": "generated", "tier": 3, "depends": ["uni_core", "uni_student"], "spec_version": 1, "generated_at": "2026-03-05T09:00:00Z"},
    "uni_exam": {"status": "spec_approved", "tier": 3, "depends": ["uni_core", "uni_student"], "spec_version": 1},
    "uni_timetable": {"status": "planned", "tier": 4, "depends": ["uni_core", "uni_student", "uni_faculty"]},
    "uni_notification": {"status": "planned", "tier": 5, "depends": ["uni_core", "uni_student"]}
  },
  "tiers": {
    "1": {"name": "Foundation", "status": "complete", "modules": ["uni_core"]},
    "2": {"name": "Core Academic", "status": "in_progress", "modules": ["uni_student", "uni_faculty", "uni_program"]},
    "3": {"name": "Operations", "status": "planned", "modules": ["uni_fee", "uni_exam", "uni_enrollment"]},
    "4": {"name": "Scheduling", "status": "planned", "modules": ["uni_timetable", "uni_attendance"]},
    "5": {"name": "Communication", "status": "planned", "modules": ["uni_notification", "uni_portal"]}
  }
}
```

### 3.5 Per-Module Artifacts

Each module gets its own directory under `.planning/modules/{module_name}/`:

| File | Created By | Purpose |
|------|-----------|---------|
| `CONTEXT.md` | `/amil:discuss-module` | Implementation decisions from human Q&A |
| `RESEARCH.md` | `/amil:new-erp` or manual | OCA research, pattern analysis |
| `spec.json` | `/amil:plan-module` | Full module specification sent to belt |
| `coherence-report.json` | `/amil:plan-module` | Cross-module coherence check results |
| `generation-manifest.json` | Belt (amil) | What the belt produced: files, models, tests |
| `check-report.json` | `/amil:check-module` | 4-level checker results |

---

## 4. Configuration Extension

Amil's `.planning/config.json` schema is extended:

```json
{
  "mode": "interactive",
  "depth": "standard",
  "profile": "quality",
  "git": {
    "auto_commit": true,
    "conventional_commits": true
  },
  "odoo": {
    "version": "17.0",
    "multi_company": true,
    "localization": "pk",
    "belt_install_path": "~/.claude/amil",
    "default_depends": ["base", "mail"],
    "security_framework": "dynamic_rbac",
    "scope_levels": ["institution", "campus", "faculty", "department", "program"],
    "notification_channels": ["email", "whatsapp"],
    "canvas_integration": true,
    "docker_image": "odoo:19.0",
    "addons_path": "./addons",
    "test_db": "odoo_test",
    "python_path": "python3"
  }
}
```

**Validation rules** (added to `bin/lib/config.js`):
- `odoo.version` must be "17.0" or "18.0"
- `odoo.scope_levels` must be non-empty array of strings
- `odoo.belt_install_path` must exist on filesystem
- `odoo.notification_channels` elements must be from ["email", "whatsapp", "sms"]

---

## 5. Belt Invocation Pattern

This is the critical integration point. Amil's `Task()` mechanism spawns subagents with fresh context. amil uses this to invoke amil.

### 5.1 How Amil spawns subagents (existing pattern)

```
Task(
  prompt: "...",
  subagent_type: "executor",
  model_profile: "quality"
)
```

The agent reads from `.planning/` files, writes output files, and exits. Orchestrator reads the output files.

### 5.2 How amil invokes the belt

```
# Step 1: Prepare belt input
Write spec.json with _available_models injected from registry
Write belt-context.md with module-specific instructions

# Step 2: Invoke belt pipeline as fresh Task()
Task(
  prompt: "Generate Odoo module from spec.json. Follow /amil:generate workflow.
           Read spec.json at .planning/modules/{module}/spec.json.
           Write output to addons/{module_name}/",
  subagent_type: "executor",
  model_profile: "quality"
)

# Step 3: Collect results
Read addons/{module_name}/__manifest__.py → verify generation
Parse generation-manifest.json from belt
Update model_registry.json with new models/fields
Commit: "feat({module_name}): generate module from spec v{version}"
```

### 5.3 Registry update after generation

The belt's generation manifest contains the models it created. amil parses this and updates the registry:

```
# In generate-module workflow, after belt Task() returns:
1. Read generation-manifest.json from belt output
2. For each model in manifest:
   a. If model exists in registry → merge fields (belt output wins for new fields)
   b. If model is new → add to registry
3. Update security_groups if new groups created
4. Update computation_chains if chain steps completed
5. Bump registry version
6. Write updated registry atomically (write to .tmp, rename)
```

---

## 6. CLAUDE.md Specification

The forked CLAUDE.md is the most critical file — it's what Claude Code reads first. It must communicate:

```markdown
# amil

Odoo ERP module orchestrator. Fork of Amil specialized for generating production-ready
Odoo modules at scale from a university ERP PRD.

## Architecture

Three layers:
1. **amil** (this system) — orchestration, decomposition, cross-module state
2. **amil** (extension at ~/.claude/amil/) — single module generation pipeline
3. **amil-utils** (Python CLI) — AST analysis, Docker validation, MCP server

## Critical State Files

- `.planning/model_registry.json` — ALL models across ALL modules. ALWAYS read before generating.
- `.planning/module_status.json` — Per-module status. Check before any module operation.
- `.planning/computation_chains.json` — Cross-module computation chains.
- `.planning/security_scope.json` — Dynamic RBAC configuration.
- `.planning/config.json` — Project config including `odoo` block.

## Commands

/amil:new-erp         — Initialize ERP project, decompose PRD into modules
/amil:map-erp         — Scan existing Odoo codebase, populate registry
/amil:discuss-module   — Module-specific implementation questions
/amil:plan-module      — Generate spec.json, run coherence check
/amil:generate-module  — Invoke belt, update registry
/amil:check-module     — Run 4-level checker
/amil:audit-erp        — Full ERP integration audit
/amil:progress         — Module status + registry stats
/amil:quick            — Quick field/bug/view without full cycle
/amil:complete-phase   — Archive tier, tag release
/amil:pause-work       — Save context and pause
/amil:resume-work      — Reload registry and resume
/amil:debug            — Debug with Odoo context
/amil:settings         — Edit config including Odoo settings
/amil:help             — Show all commands

## Rules

1. NEVER generate Odoo code directly. Always invoke through the belt (amil).
2. ALWAYS read model_registry.json before planning or generating a module.
3. ALWAYS update model_registry.json after successful generation.
4. ALWAYS run coherence check before presenting spec to human.
5. Module generation order follows dependency tiers. Never generate a module before its dependencies.
6. Human approval required at: spec review, generation review, check sign-off.
7. One module at a time through the belt. Parallel only within same tier, one belt invocation at a time.
```

---

## 7. Installation & Dependencies

### 7.1 Install Path

`~/.claude/amil/` (replaces `~/.claude/amil/`)

### 7.2 Install Script Changes

`bin/install.js` modifications:
- Package name: `amil`
- Install path: `~/.claude/amil/`
- Remove multi-runtime support (OpenCode, Gemini CLI, Codex) — Claude Code only
- Add dependency checks:
  - Node.js >= 16.7.0 (keep from Amil)
  - Python 3.8+ (for amil-utils)
  - amil installed at `~/.claude/amil/` (warn if missing, offer install instructions)
  - Docker (optional, for integration testing)
- Register commands under `amil:` prefix
- Generate manifest for Claude Code

### 7.3 amil Path Update

In the amil repo, ONE change:
- `install.sh`: Change Amil dependency check from `~/.claude/amil/` to `~/.claude/amil/`

---

## 8. End-to-End Workflow

```
Human provides university ERP PRD
          │
          ▼
/amil:new-erp
  ├── Ask Odoo config questions → write config.json
  ├── Spawn 4 research agents on PRD (parallel)
  │   ├── Module boundary analysis
  │   ├── OCA registry check
  │   ├── Dependency mapping
  │   └── Computation chain identification
  ├── Merge → module dependency graph
  ├── Human reviews decomposition
  └── Generate ROADMAP.md with tiers as phases
          │
          ▼
For each tier (foundation → core → operations → communication):
  For each module in tier:
    │
    ├── /amil:discuss-module {module}
    │   └── Module-type Q&A → {module}-CONTEXT.md
    │
    ├── /amil:plan-module {module}
    │   ├── Generate spec.json (inject registry)
    │   ├── Run coherence check
    │   └── Human approves spec
    │
    ├── /amil:generate-module {module}
    │   ├── Invoke belt (amil) as Task()
    │   ├── Belt produces module in addons/{module}/
    │   ├── Update model_registry.json
    │   └── Git commit
    │
    └── /amil:check-module {module}
        ├── CHK-01: Structural
        ├── CHK-02: Cross-module
        ├── CHK-03: Spec coverage
        ├── CHK-04: Integration (Docker)
        └── Human sign-off
    │
    ▼
  /amil:complete-phase (after all modules in tier)
    ├── Snapshot registry
    ├── Tag tier release
    └── Update module_status.json
          │
          ▼
/amil:audit-erp (after ALL tiers)
  ├── Docker install all modules together
  ├── Run full integration test suite
  ├── Trace all computation chains end-to-end
  ├── Verify all security scopes
  ├── Check portal routes
  ├── Validate cron jobs
  └── Production readiness checklist
```

---

## 9. File Change Summary

### By change type:

**New files to create:** ~15
- 6 new agents
- 4 new test files
- New `bin/lib/registry.js`
- New state file schemas (documented above)
- New `CLAUDE.md`

**Files to heavy-rewrite:** ~12
- 6 command files (new-erp, map-erp, plan-module, generate-module, check-module, audit-erp)
- 5 workflow files (matching commands)
- `bin/install.js`

**Files to medium-rewrite:** ~10
- 4 command files (discuss-module, complete-phase, progress, quick)
- 5 agent files (researcher, planner, executor, reviewer, verifier)
- `CLAUDE.md`

**Files to light-rewrite (rename + minor additions):** ~30
- Remaining command files (prefix rename)
- Remaining workflow files (prefix rename)
- Templates (add Odoo context)
- Reference docs (add Odoo patterns)
- Hooks (add module status)

**Files to keep as-is:** ~40
- Most of `bin/lib/` (frontmatter, internal utilities)
- Test infrastructure (test runner, CI)
- Build scripts
- Core Amil patterns that don't need Odoo specialization

### By priority (implementation order):

**Phase 1 — Foundation (make it installable)**
1. Fork repo, rename package
2. Rewrite `bin/install.js`
3. Rewrite `CLAUDE.md`
4. Rename all command prefixes to `amil:`
5. Add `odoo` config block to `bin/lib/config.js`
6. Create `bin/lib/registry.js` (model registry CRUD)
7. Update amil's install.sh to reference amil

**Phase 2 — Core workflow (new-erp through generate-module)**
1. `commands/amil/new-erp.md` + `workflows/new-erp.md`
2. New agents: odoo-erp-decomposer, odoo-module-researcher
3. `commands/amil/discuss-module.md` + agent: odoo-module-questioner
4. `commands/amil/plan-module.md` + agents: odoo-spec-generator, odoo-coherence-checker
5. `commands/amil/generate-module.md` + workflow: belt invocation + registry update

**Phase 3 — Verification (check-module through audit-erp)**
1. `commands/amil/check-module.md` + 4-level checker
2. `commands/amil/audit-erp.md` + agent: odoo-audit-agent
3. `commands/amil/complete-phase.md` with registry archival

**Phase 4 — Polish**
1. All remaining command renames
2. Updated hooks (statusline, context monitor)
3. New tests
4. Documentation (README, help text)
5. Agent prompt refinement based on testing

---

## 10. Open Questions

1. **Belt manifest format:** The exact schema of `generation-manifest.json` that amil produces needs to be documented/standardized for reliable registry updates. Currently inferred from belt codebase analysis.

2. **Registry size vs context window:** As the registry grows (20+ modules, 100+ models), it may exceed practical context injection size. May need: selective injection (only models relevant to current module's depends), registry summarization, or tiered injection (full for direct depends, summary for transitive).

3. **Parallel module generation:** Modules within the same tier can theoretically run in parallel, but each belt invocation needs exclusive access to the addons directory and Docker. May need: per-module working directories, merge step after parallel generation.

4. **Error recovery:** When a module fails generation after 3 belt retries, the current plan is skip + manual fix. Need to define: how does a skipped module affect downstream modules that depend on it? Stub models in registry?

5. **Brownfield integration:** `/amil:map-erp` can scan existing modules, but what happens when a generated module needs to extend an existing third-party module (e.g., hr_payroll)? The registry needs to include base Odoo and OCA module models, not just generated ones.
