# amil

## What This Is

A fork of Amil (Get Shit Done) specialized for orchestrating Odoo ERP module generation at scale. It takes a university ERP PRD, decomposes it into 20+ modules, and drives the amil belt to produce production-ready Odoo modules with cross-module coherence. Built for TIFAQM Engineering.

## Core Value

Cross-module coherence — every generated Odoo module must be structurally valid, referentially consistent with all other modules (Many2one targets exist, computation chains intact, security scopes complete), and installable together in a single Odoo instance.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Fork Amil repo and rename all entry points from `gsd` to `amil`
- [ ] Rewrite `bin/install.js` for Claude Code only, with amil dependency check
- [ ] Rewrite `CLAUDE.md` as Odoo ERP orchestrator context document
- [ ] Extend `bin/lib/config.js` with `odoo` config block (version, multi_company, localization, belt path, security framework, scope levels, notification channels)
- [ ] Create `bin/lib/registry.js` for model registry CRUD (read, update, rollback, validate, stats)
- [ ] Rename all 32 command files from `amil:` to `amil:` prefix
- [ ] Create `model_registry.json` state file with atomic update pattern
- [ ] Create `module_status.json` state file with status transitions (planned -> spec_approved -> generated -> checked -> shipped)
- [ ] Create `computation_chains.json` state file
- [ ] Create `security_scope.json` state file
- [ ] Heavy-rewrite `new-erp` command/workflow (Odoo config questions, 4 parallel research agents on PRD, module dependency graph, tiered roadmap)
- [ ] Heavy-rewrite `plan-module` command/workflow (spec.json generation, registry injection, coherence check)
- [ ] Heavy-rewrite `generate-module` command/workflow (belt invocation via Task(), registry update from manifest)
- [ ] Heavy-rewrite `map-erp` command/workflow (manifest parser, model AST analyzer, security scanner, view pattern detector)
- [ ] Medium-rewrite `discuss-module` command/workflow (module-type-specific question templates)
- [ ] Medium-rewrite `progress` command (module status table, registry stats, ERP readiness %)
- [ ] Create 6 new agents (odoo-module-researcher, odoo-spec-generator, odoo-coherence-checker, odoo-module-questioner, odoo-erp-decomposer, odoo-audit-agent)
- [ ] Rewrite 5 existing agents for Odoo context (researcher, planner, executor, reviewer, verifier)
- [ ] Implement tiered registry injection (full for direct depends, field-list for transitive, names for rest)
- [ ] Implement on-demand third-party model scanning (scan base/OCA models into registry when depends declared)
- [ ] Extend hooks (statusline with module progress, context monitor with registry size tracking)
- [ ] Create per-module artifact directory structure (.planning/modules/{module_name}/)
- [ ] Write tests for registry CRUD, module status transitions, coherence checking, belt integration

### Out of Scope

- amil belt development — separate repo, built independently
- amil-utils Python CLI — separate repo
- Verification/checker phase (Phase 3 of PRD) — deferred to next milestone
- Polish phase (Phase 4 of PRD) — deferred to next milestone
- Multi-runtime support (OpenCode, Gemini, Codex) — Claude Code only
- Parallel module generation — sequential only for this milestone
- `audit-erp` command — deferred to verification milestone
- `complete-phase` with registry archival — deferred to verification milestone
- Belt manifest schema definition — will adapt to what amil produces

## Context

This is a three-layer architecture:
1. **amil** (this repo) — orchestration, module decomposition, cross-module state management
2. **amil** (separate repo at ~/.claude/amil/) — single-module generation pipeline with 8 agents, 13 knowledge files, Jinja2 templates, Docker validation
3. **amil-utils** (Python CLI) — AST analysis, ChromaDB search, MCP server, Docker ops

amil currently extends Amil. After this fork, amil's install references change from `~/.claude/get-shit-done/` to `~/.claude/amil/`. amil itself stays in its own repo, untouched except for this path change.

The university ERP targets Odoo 17.0 with dynamic RBAC, multi-company support, Pakistani localization, and 5 scope levels (institution, campus, faculty, department, program).

amil is not yet installed — amil will be built first, integration tested later.

## Constraints

- **Architecture**: Must maintain Amil's Task() subagent pattern for belt invocation — fresh 200K context per module generation
- **Sequential generation**: One module at a time through the belt, no parallel generation
- **Error recovery**: Failed module blocks entire tier until manually fixed
- **Registry injection**: Tiered — full models for direct depends, field-list for transitive, names-only for rest
- **Third-party models**: On-demand scanning — scan base/OCA models into registry when a module declares depends on them
- **Belt manifest**: Schema defined by amil, not amil — adapt to whatever the belt produces
- **Odoo version**: 17.0
- **Install path**: ~/.claude/amil/

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork Amil rather than extend | Need deep structural changes (module-as-phase, registry, coherence) that would break Amil's generic use case | — Pending |
| Sequential module generation | Belt needs exclusive addons dir + Docker access; parallel adds complexity with little benefit at 20 modules | — Pending |
| Block tier on failure | Downstream modules depend on failed module's models; stubs risk cascading incoherence | — Pending |
| Tiered registry injection | Full registry at 100+ models exceeds practical context; selective injection keeps context lean | — Pending |
| On-demand third-party scanning | Pre-populating all base Odoo models adds noise; deferring breaks coherence checks; on-demand is the sweet spot | — Pending |
| Belt manifest schema defined by amil | amil knows what it produces; amil should adapt, not prescribe | — Pending |
| Phase 1+2 scope for first milestone | Foundation + core workflow gives a usable system; verification/polish can follow | — Pending |

---
*Last updated: 2026-03-05 after initialization*
