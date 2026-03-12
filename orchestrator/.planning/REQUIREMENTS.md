# Requirements: amil

**Defined:** 2026-03-05
**Core Value:** Cross-module coherence — every generated Odoo module must be referentially consistent with all other modules

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Fork Foundation

- [x] **FORK-01**: All 32 command files renamed from `/amil:` to `/amil:` prefix with zero remaining `/amil:` references
- [x] **FORK-02**: All workflow files updated to reference `amil` commands instead of `gsd` commands
- [x] **FORK-03**: All agent files updated to reference `amil` paths and commands
- [x] **FORK-04**: 233+ hardcoded path references to `get-shit-done` renamed to `amil` across all files
- [x] **FORK-05**: `bin/install.js` rewritten for Claude Code only (remove OpenCode, Gemini, Codex runtime support)
- [x] **FORK-06**: `bin/install.js` checks for amil at `~/.claude/amil/` (warn if missing, offer instructions)
- [x] **FORK-07**: `bin/install.js` checks for Python 3.8+ (required by amil-utils)
- [x] **FORK-08**: `CLAUDE.md` rewritten as Odoo ERP orchestrator context document with command reference, architecture description, state file locations, and rules
- [x] **FORK-09**: `package.json` renamed to `amil` with updated description and repository URL
- [x] **FORK-10**: Verification grep confirms zero remaining `get-shit-done` or `/amil:` references in codebase

### Configuration

- [x] **CONF-01**: `bin/lib/config.js` extended with `odoo` config block schema (version, multi_company, localization, belt_install_path, default_depends, security_framework, scope_levels, notification_channels, canvas_integration, docker_image, addons_path, test_db)
- [x] **CONF-02**: Odoo config validation rules enforced (version must be 17.0 or 18.0, scope_levels non-empty array, belt_install_path existence check, notification_channels from allowed set)
- [x] **CONF-03**: `new-erp` command collects Odoo-specific config via interactive questions and writes `odoo` block to config.json

### Model Registry

- [x] **REG-01**: `bin/lib/registry.js` (or `registry.cjs`) created with model registry CRUD operations (read full, read single model, update from manifest, validate, stats)
- [x] **REG-02**: Registry atomic writes implemented (write to .tmp file, rename to target)
- [x] **REG-03**: Registry versioning implemented (_meta.version incremented on each update, _meta.last_updated timestamp, _meta.modules_contributing list)
- [x] **REG-04**: Registry rollback implemented (previous version preserved, one-level undo on failed generation)
- [x] **REG-05**: Registry validation checks implemented (Many2one targets exist, no duplicate model names, required fields present)
- [x] **REG-06**: Registry stats command returns model count, field count, cross-module reference count
- [x] **REG-07**: CLI subcommands registered: `registry read`, `registry read-model`, `registry update`, `registry rollback`, `registry validate`, `registry stats`
- [x] **REG-08**: Tiered registry injection implemented (full models for direct depends, field-list-only for transitive depends, names-only for rest)

### Module Status

- [x] **STAT-01**: `module_status.json` state file created with per-module status and tier structure
- [x] **STAT-02**: Module status transitions enforced (planned -> spec_approved -> generated -> checked -> shipped) with invalid transition rejection
- [x] **STAT-03**: Tier status computed from constituent module statuses (complete when all modules shipped)
- [x] **STAT-04**: Per-module artifact directory created at `.planning/modules/{module_name}/` with CONTEXT.md, spec.json, coherence-report.json, generation-manifest.json, check-report.json slots

### Dependency Graph

- [x] **DEPG-01**: Module dependency graph constructed from module manifests (depends field)
- [x] **DEPG-02**: Topological sort implemented to determine generation order
- [x] **DEPG-03**: Circular dependency detection with clear error reporting
- [x] **DEPG-04**: Tier grouping implemented (foundation -> core -> operations -> communication) based on dependency depth
- [x] **DEPG-05**: Generation blocked if a module's dependencies have not reached "generated" status

### PRD Decomposition (new-erp)

- [x] **NWRP-01**: `/amil:new-erp` command and workflow created
- [x] **NWRP-02**: Odoo-specific config questions asked at project init (version, multi_company, localization, module scope, notification channels, deployment target)
- [x] **NWRP-03**: 4 parallel research agents spawned on PRD (module boundary analysis, OCA registry check, dependency mapping, computation chain identification)
- [x] **NWRP-04**: Research outputs merged into module dependency graph with phased generation order
- [x] **NWRP-05**: Human reviews and approves module decomposition before roadmap generation
- [x] **NWRP-06**: ROADMAP.md generated with dependency tiers as phases, each module as a phase detail section
- [x] **NWRP-07**: New agents created: `odoo-erp-decomposer`, `odoo-module-researcher`

### Module Discussion (discuss-module)

- [x] **DISC-01**: `/amil:discuss-module` command and workflow created
- [x] **DISC-02**: Module type detected from name/description (fee, exam, student, faculty, HR, timetable, notification, portal, core)
- [x] **DISC-03**: Module-type-specific question templates loaded (fee: monetary vs float, penalty method, payment channels; exam: grading scales, makeup policy; student: enrollment states, academic holds)
- [x] **DISC-04**: `odoo-module-questioner` agent created with per-type expertise
- [x] **DISC-05**: Q&A output written to `.planning/modules/{module}/CONTEXT.md`

### Spec Generation (plan-module)

- [x] **SPEC-01**: `/amil:plan-module` command and workflow created
- [x] **SPEC-02**: `odoo-spec-generator` agent created that produces spec.json from CONTEXT.md + RESEARCH.md + registry
- [x] **SPEC-03**: spec.json includes: models, fields, business_rules, computation_chains, workflow, view_hints, reports, notifications, cron_jobs, security, portal, api_endpoints
- [x] **SPEC-04**: `_available_models` injected from registry into spec.json (using tiered injection)
- [x] **SPEC-05**: `odoo-coherence-checker` agent created that validates spec against registry
- [x] **SPEC-06**: Coherence check validates: Many2one targets exist in registry, no duplicate model names, computed field depends chains have sources, security groups are defined
- [x] **SPEC-07**: Coherence report presented to human with pass/fail per check
- [x] **SPEC-08**: Human approves spec before generation proceeds; module status updated to "spec_approved"

### Belt Invocation (generate-module)

- [ ] **BELT-01**: `/amil:generate-module` command and workflow created
- [ ] **BELT-02**: spec.json loaded and registry injected as `_available_models` for belt context
- [ ] **BELT-03**: amil pipeline spawned as `Task()` subagent with fresh context
- [ ] **BELT-04**: On success: generation manifest parsed, model registry updated atomically with new models/fields, module status updated to "generated"
- [ ] **BELT-05**: On failure: structured error report presented with retry/revise-spec/skip options
- [ ] **BELT-06**: Failed module blocks entire tier until manually resolved (no silent skip)
- [ ] **BELT-07**: Git commit created per successful generation: `feat({module_name}): generate module from spec v{version}`

### Existing Agents Rewrite

- [x] **AGNT-01**: `researcher.md` agent specialized for Odoo research (OCA module registry, Odoo docs, field type patterns)
- [x] **AGNT-02**: `planner.md` agent specialized for Odoo module planning (spec.json structure, model decomposition, dependency analysis)
- [ ] **AGNT-03**: `executor.md` agent specialized for belt orchestration (loading spec, injecting registry, invoking amil)
- [x] **AGNT-04**: `reviewer.md` agent specialized for Odoo review (model naming, security patterns, pylint-odoo rules)
- [ ] **AGNT-05**: `verifier.md` agent specialized for Odoo verification (Docker install test, cross-module validation)

### Progress & Status

- [ ] **PROG-01**: `/amil:progress` command extended with module status table (planned/spec_approved/generated/checked/shipped per module)
- [ ] **PROG-02**: Progress includes registry stats (total models, total fields, cross-module references)
- [ ] **PROG-03**: Progress includes tier completion status and overall ERP readiness percentage

### Testing

- [x] **TEST-01**: `tests/registry.test.js` created covering registry CRUD, atomic updates, rollback, cross-module validation, duplicate detection
- [x] **TEST-02**: `tests/module-status.test.js` created covering status transitions, invalid transitions, tier completion
- [x] **TEST-03**: `tests/coherence.test.js` created covering Many2one target validation, computation chain integrity, spec coverage diffing
- [ ] **TEST-04**: `tests/belt-integration.test.js` created covering spec.json formatting, registry injection, manifest parsing, registry update from manifest
- [x] **TEST-05**: Existing Amil tests updated to pass with renamed command prefix and new config schema
- [ ] **TEST-06**: 80%+ test coverage across new code (registry, module-status, coherence, belt-integration)

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Verification & Checking

- **CHCK-01**: `/amil:check-module` command with 4-level checker (structural, cross-module, spec coverage, Docker integration)
- **CHCK-02**: `/amil:audit-erp` command with full ERP integration audit (Docker install all, integration tests, production checklist)
- **CHCK-03**: `/amil:complete-phase` with registry archival and tier release tagging

### Advanced State

- **ADVS-01**: Computation chain tracking (`computation_chains.json`) with chain step completion and integrity validation
- **ADVS-02**: Security scope framework (`security_scope.json`) with dynamic RBAC, 5 scope levels, record rule templates
- **ADVS-03**: On-demand third-party model scanning (base/OCA models into registry when depends declared)

### Brownfield & Utilities

- **BRWN-01**: `/amil:map-erp` command (manifest parser, model AST analyzer, security scanner, view pattern detector)
- **BRWN-02**: `/amil:quick` command (quick field addition, bug fix, view modification with registry update)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Parallel module generation | Docker exclusivity, registry race conditions, complexity outweighs benefit at 20 modules |
| Direct Odoo code generation | Belt (amil) handles code gen; orchestrator orchestrates only |
| Auto-fix failed modules | Silent fixes create insidious bugs; human must decide retry/revise/skip |
| Real-time registry sync via XML-RPC | Registry is build artifact, not runtime mirror; adds fragile runtime dependency |
| Multi-runtime support (OpenCode, Gemini, Codex) | Task() subagent pattern is Claude Code specific and foundational |
| GUI dashboard | Massive scope increase for CLI tool used by one team; enhance progress command instead |
| Automatic dependency resolution | Silent dependency addition risks circular deps and bloat; coherence checker flags, human adds |
| Full base Odoo model pre-population | 200+ models adds noise; on-demand scanning (v2) is sufficient |
| amil belt development | Separate repo, separate concern |
| amil-utils Python CLI | Separate repo, separate concern |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FORK-01 | Phase 1 | Complete |
| FORK-02 | Phase 1 | Complete |
| FORK-03 | Phase 1 | Complete |
| FORK-04 | Phase 1 | Complete |
| FORK-05 | Phase 1 | Complete |
| FORK-06 | Phase 1 | Complete |
| FORK-07 | Phase 1 | Complete |
| FORK-08 | Phase 1 | Complete |
| FORK-09 | Phase 1 | Complete |
| FORK-10 | Phase 1 | Complete |
| CONF-01 | Phase 1 | Complete |
| CONF-02 | Phase 1 | Complete |
| CONF-03 | Phase 2 | Complete |
| REG-01 | Phase 1 | Complete |
| REG-02 | Phase 1 | Complete |
| REG-03 | Phase 1 | Complete |
| REG-04 | Phase 1 | Complete |
| REG-05 | Phase 1 | Complete |
| REG-06 | Phase 1 | Complete |
| REG-07 | Phase 1 | Complete |
| REG-08 | Phase 2 | Complete |
| STAT-01 | Phase 1 | Complete |
| STAT-02 | Phase 1 | Complete |
| STAT-03 | Phase 1 | Complete |
| STAT-04 | Phase 1 | Complete |
| DEPG-01 | Phase 1 | Complete |
| DEPG-02 | Phase 1 | Complete |
| DEPG-03 | Phase 1 | Complete |
| DEPG-04 | Phase 1 | Complete |
| DEPG-05 | Phase 1 | Complete |
| NWRP-01 | Phase 2 | Complete |
| NWRP-02 | Phase 2 | Complete |
| NWRP-03 | Phase 2 | Complete |
| NWRP-04 | Phase 2 | Complete |
| NWRP-05 | Phase 2 | Complete |
| NWRP-06 | Phase 2 | Complete |
| NWRP-07 | Phase 2 | Complete |
| DISC-01 | Phase 3 | Complete |
| DISC-02 | Phase 3 | Complete |
| DISC-03 | Phase 3 | Complete |
| DISC-04 | Phase 3 | Complete |
| DISC-05 | Phase 3 | Complete |
| SPEC-01 | Phase 4 | Complete |
| SPEC-02 | Phase 4 | Complete |
| SPEC-03 | Phase 4 | Complete |
| SPEC-04 | Phase 4 | Complete |
| SPEC-05 | Phase 4 | Complete |
| SPEC-06 | Phase 4 | Complete |
| SPEC-07 | Phase 4 | Complete |
| SPEC-08 | Phase 4 | Complete |
| BELT-01 | Phase 5 | Pending |
| BELT-02 | Phase 5 | Pending |
| BELT-03 | Phase 5 | Pending |
| BELT-04 | Phase 5 | Pending |
| BELT-05 | Phase 5 | Pending |
| BELT-06 | Phase 5 | Pending |
| BELT-07 | Phase 5 | Pending |
| AGNT-01 | Phase 3 | Complete |
| AGNT-02 | Phase 4 | Complete |
| AGNT-03 | Phase 5 | Pending |
| AGNT-04 | Phase 4 | Complete |
| AGNT-05 | Phase 5 | Pending |
| PROG-01 | Phase 5 | Pending |
| PROG-02 | Phase 5 | Pending |
| PROG-03 | Phase 5 | Pending |
| TEST-01 | Phase 1 | Complete |
| TEST-02 | Phase 1 | Complete |
| TEST-03 | Phase 4 | Complete |
| TEST-04 | Phase 5 | Pending |
| TEST-05 | Phase 1 | Complete |
| TEST-06 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 71 total
- Mapped to phases: 71
- Unmapped: 0

---
*Requirements defined: 2026-03-05*
*Last updated: 2026-03-05 after roadmap creation*
