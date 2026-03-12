# Roadmap: amil

## Overview

Transform the Amil CLI framework into an Odoo ERP module orchestrator that decomposes a university ERP PRD into 20+ modules and drives the amil belt to generate them sequentially with cross-module coherence. The build progresses from fork renaming and state infrastructure, through PRD decomposition and module planning workflows, to belt integration and generation. Each phase delivers a complete, verifiable capability that unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Fork Foundation and State Infrastructure** - Rename fork, build registry, status tracking, dependency graph, and config (completed 2026-03-05)
- [ ] **Phase 2: PRD Decomposition and ERP Init** - new-erp command with research agents, tiered registry injection, module decomposition
- [ ] **Phase 3: Module Discussion** - discuss-module command with type-specific question templates and researcher agent
- [ ] **Phase 4: Spec Generation and Coherence** - plan-module command with spec.json generation, coherence checking, and human approval
- [ ] **Phase 5: Belt Integration and Generation Pipeline** - generate-module command, belt invocation, progress dashboard, and end-to-end testing

## Phase Details

### Phase 1: Fork Foundation and State Infrastructure
**Goal**: A working amil CLI with all references renamed, Odoo config management, model registry CRUD with atomic writes and rollback, module status tracking, dependency graph with topological sort, and tests proving it all works
**Depends on**: Nothing (first phase)
**Requirements**: FORK-01, FORK-02, FORK-03, FORK-04, FORK-05, FORK-06, FORK-07, FORK-08, FORK-09, FORK-10, CONF-01, CONF-02, REG-01, REG-02, REG-03, REG-04, REG-05, REG-06, REG-07, STAT-01, STAT-02, STAT-03, STAT-04, DEPG-01, DEPG-02, DEPG-03, DEPG-04, DEPG-05, TEST-01, TEST-02, TEST-05
**Success Criteria** (what must be TRUE):
  1. Running any `/amil:` command routes correctly and zero references to `amil:` or `get-shit-done` remain in the codebase (verified by grep)
  2. User can run `registry read`, `registry validate`, `registry stats`, `registry rollback` and get correct JSON output from a populated model_registry.json
  3. Module status transitions enforce the planned->spec_approved->generated->checked->shipped lifecycle, rejecting invalid transitions
  4. Dependency graph produces a topological generation order and rejects circular dependencies with a clear error message
  5. All tests pass (`node --test`) with 80%+ coverage across registry, module-status, and dependency-graph code
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Fork rename: directory structure, CLI entry point, all 233+ references, install.js rewrite, CLAUDE.md
- [ ] 01-02-PLAN.md — Odoo config extension and model registry CRUD with atomic writes, rollback, validation, stats
- [ ] 01-03-PLAN.md — Module status lifecycle state machine and dependency graph with toposort, tiers, generation blocking

### Phase 2: PRD Decomposition and ERP Init
**Goal**: User can initialize an Odoo ERP project from a PRD, have it decomposed into modules by parallel research agents, review the dependency graph, and approve a tiered roadmap with modules as phases
**Depends on**: Phase 1
**Requirements**: CONF-03, REG-08, NWRP-01, NWRP-02, NWRP-03, NWRP-04, NWRP-05, NWRP-06, NWRP-07
**Success Criteria** (what must be TRUE):
  1. Running `/amil:new-erp` asks Odoo-specific config questions and writes the `odoo` block to config.json
  2. Four parallel research agents analyze the PRD and produce a merged module dependency graph with tier assignments
  3. Human is presented with the module decomposition for review and can approve or request changes before roadmap generation
  4. Tiered registry injection works (full models for direct depends, field-list for transitive, names-only for rest)
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — Tiered registry injection (REG-08) and config validation extensions for new Odoo keys
- [ ] 02-02-PLAN.md — new-erp command, workflow (Stage A + B), and 2 dedicated agent files
- [ ] 02-03-PLAN.md — Merge logic, human approval, module init, and ROADMAP.md generation with tests

### Phase 3: Module Discussion
**Goal**: User can run an interactive discussion for any module that asks domain-specific questions based on module type, producing a rich CONTEXT.md that captures design decisions before spec generation
**Depends on**: Phase 2
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, AGNT-01
**Success Criteria** (what must be TRUE):
  1. Running `/amil:discuss-module {module}` detects module type and loads type-specific question templates (fee, exam, student, etc.)
  2. Q&A session output is written to `.planning/modules/{module}/CONTEXT.md` with structured answers
  3. The `odoo-module-questioner` and `researcher` agents are Odoo-specialized and produce domain-relevant questions and research
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — Wave 0 test scaffold and module-questions.json with 10 type templates (9 types + generic)
- [ ] 03-02-PLAN.md — Questioner agent creation and researcher agent enhancement with per-domain Odoo knowledge
- [ ] 03-03-PLAN.md — discuss-module command and workflow wiring type detection, template loading, and agent spawning

### Phase 4: Spec Generation and Coherence
**Goal**: User can generate a complete spec.json for any module from its CONTEXT.md and registry context, have it validated for cross-module coherence, review the results, and approve the spec before generation proceeds
**Depends on**: Phase 3
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05, SPEC-06, SPEC-07, SPEC-08, AGNT-02, AGNT-04, TEST-03
**Success Criteria** (what must be TRUE):
  1. Running `/amil:plan-module {module}` produces a spec.json with models, fields, business_rules, computation_chains, workflow, view_hints, reports, notifications, cron_jobs, security, portal, and api_endpoints
  2. Registry context is injected into spec.json as `_available_models` using tiered injection from Phase 2
  3. Coherence checker validates Many2one targets exist, no duplicate model names, computed field chains have sources, and security groups are defined -- presenting a pass/fail report to the human
  4. Human approves the spec and module status transitions to "spec_approved"
  5. Coherence tests pass covering Many2one validation, computation chain integrity, and spec coverage diffing
**Plans**: 3 plans

Plans:
- [ ] 04-01-PLAN.md — Coherence checker CJS library with 4 structural checks, tests, and CLI registration
- [ ] 04-02-PLAN.md — Spec generator agent and spec reviewer agent creation with frontmatter tests
- [ ] 04-03-PLAN.md — plan-module command and 10-step workflow wiring agents, coherence, and human approval

### Phase 5: Belt Integration and Generation Pipeline
**Goal**: User can generate an Odoo module by invoking the amil belt via Task(), have the registry updated from the generation manifest, track progress across the entire ERP, and have end-to-end test coverage
**Depends on**: Phase 4
**Requirements**: BELT-01, BELT-02, BELT-03, BELT-04, BELT-05, BELT-06, BELT-07, AGNT-03, AGNT-05, PROG-01, PROG-02, PROG-03, TEST-04, TEST-06
**Success Criteria** (what must be TRUE):
  1. Running `/amil:generate-module {module}` spawns the amil belt as a Task() subagent with spec.json and registry context, then parses the generation manifest on success
  2. On successful generation, model registry is atomically updated with new models/fields from the manifest and module status transitions to "generated"
  3. On failure, a structured error report is presented with retry/revise-spec/skip options and the entire tier is blocked until resolution
  4. Running `/amil:progress` shows module status table, registry stats (models/fields/references), tier completion, and overall ERP readiness percentage
  5. Belt integration tests and 80%+ coverage across all new code (registry, module-status, coherence, belt-integration)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Fork Foundation and State Infrastructure | 3/3 | Complete   | 2026-03-05 |
| 2. PRD Decomposition and ERP Init | 2/3 | In Progress|  |
| 3. Module Discussion | 1/3 | In Progress|  |
| 4. Spec Generation and Coherence | 0/3 | Not started | - |
| 5. Belt Integration and Generation Pipeline | 0/3 | Not started | - |
