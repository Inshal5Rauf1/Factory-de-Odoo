# Feature Research

**Domain:** Odoo ERP module orchestration -- AI-driven multi-module generation pipeline with cross-module state management
**Researched:** 2026-03-05
**Confidence:** HIGH (domain is well-defined by PRD; this is a novel system with no direct competitors, so features derive from Odoo development patterns + multi-agent orchestration best practices)

## Feature Landscape

### Table Stakes (Users Expect These)

These are non-negotiable. Without them, the orchestrator cannot produce a coherent multi-module Odoo ERP.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Model Registry (CRUD + versioning)** | Every subsequent module must know what models/fields already exist. Without this, Many2one references break, field names collide, and computed field chains fail. This IS the core value proposition. | HIGH | Atomic updates, rollback support, version tracking. JSON state file with read/write/validate/rollback/stats operations. Must handle 100+ models across 20+ modules. |
| **Module Dependency Graph** | Odoo modules MUST install in dependency order. A module referencing `uni.student` via Many2one cannot generate before `uni_student` exists. The orchestrator must enforce this ordering. | MEDIUM | Topological sort on `depends` from manifests. Tier-based grouping (foundation -> core -> operations -> communication). Circular dependency detection. |
| **Spec Generation (spec.json)** | The belt (amil) consumes a structured spec. Without spec generation, the orchestrator has no way to communicate module requirements to the generation pipeline. | HIGH | Must include: models, fields, business rules, computation chains, workflows, views, security, reports, cron jobs. Must inject `_available_models` from registry. |
| **Cross-Module Coherence Checking** | The defining problem. Generated modules must be referentially consistent: Many2one targets exist, computed field depends chains are intact, security groups are defined, no duplicate model names. | HIGH | Pre-generation check (against spec) and post-generation check (against actual output). Four-level checker: structural, cross-module, spec coverage, integration. |
| **Belt Invocation via Task()** | The orchestrator does not generate Odoo code itself. It must spawn the amil pipeline as a subagent with fresh 200K context per module. This is the core architectural pattern inherited from Amil. | MEDIUM | Load spec.json + inject registry -> spawn Task() -> collect generation manifest -> update registry. Sequential only (one belt invocation at a time). |
| **Module Status Tracking** | Must track each module through its lifecycle: planned -> spec_approved -> generated -> checked -> shipped. Without this, the orchestrator cannot determine what to do next or report progress. | LOW | JSON state file with status transitions. Invalid transition prevention (cannot go from planned to checked). |
| **Registry Injection (Tiered)** | Full registry at 100+ models exceeds practical context for the belt. Must inject tiered context: full models for direct depends, field-list for transitive depends, names-only for the rest. | MEDIUM | Tiering logic based on dependency graph. Must recalculate per module generation. |
| **PRD Decomposition** | The system starts with a university ERP PRD and must decompose it into discrete Odoo modules with clear boundaries, responsibilities, and dependency relationships. | HIGH | 4 parallel research agents: module boundary analysis, OCA registry check, dependency mapping, computation chain identification. Output: module dependency graph. |
| **Human Checkpoints** | Human-in-the-loop at: spec review, generation review, check sign-off. The orchestrator must pause and present structured information for human decision-making. | LOW | Inherited from Amil's interactive mode. Present coherence reports, check results, and spec summaries for approval. |
| **Configuration Management** | Odoo-specific config: version (17.0/18.0), multi-company, localization, security framework, scope levels, belt path, notification channels. | LOW | Extend Amil's `.planning/config.json` with `odoo` block. Schema validation for Odoo-specific fields. |
| **Command Prefix Renaming** | All 32 Amil commands must be renamed from `/amil:` to `/amil:`. Without this, the fork conflicts with Amil if both are installed. | LOW | Mechanical find-and-replace across command files, workflows, agents, and CLAUDE.md. |
| **Per-Module Artifact Directory** | Each module needs its own directory (`.planning/modules/{module_name}/`) for CONTEXT.md, spec.json, coherence reports, generation manifests, and check reports. | LOW | Directory creation and artifact routing. Clean separation of per-module state from global state. |

### Differentiators (Competitive Advantage)

These set amil apart from manual Odoo development, basic scaffolding tools, and single-module AI generators.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Computation Chain Tracking** | Traces multi-model computed field chains (CGPA: enrollment.grade_point -> student.cgpa -> merit_list.rank) across module boundaries. No existing tool does this. Ensures chains remain intact as modules generate sequentially. | HIGH | Separate state file (`computation_chains.json`). Chain steps map to specific models/fields/modules. Completion tracking (partial vs complete). Must validate that chain dependencies are satisfied before generating downstream modules. |
| **Security Scope Framework** | Dynamic RBAC with 5 hierarchical scope levels (institution -> campus -> faculty -> department -> program). Record rules auto-scoped to user's position in hierarchy. No Odoo tool manages this across modules. | HIGH | Separate state file (`security_scope.json`). Scope field injection into models. Record rule generation per scope level. Group hierarchy validation across modules. |
| **On-Demand Third-Party Model Scanning** | When a module declares `depends: ['hr_payroll']`, automatically scan that base/OCA module's models into the registry so coherence checks work against real model schemas, not guesses. | MEDIUM | Parse `__manifest__.py` and Python model files from installed Odoo addons. Lazy loading (only scan when declared as dependency). Must handle base Odoo models and OCA modules. |
| **Module-Type-Specific Discussion Templates** | Different module types need different implementation questions. Fee modules need monetary vs float, penalty methods, payment channels. Exam modules need grading scales, makeup policy. Generic Q&A wastes time. | MEDIUM | Template library per module type (fee, exam, student, faculty, HR, timetable, notification, portal). Agent-driven Q&A with domain expertise. Output: structured CONTEXT.md. |
| **Existing Codebase Scanning (map-erp)** | Scan an existing Odoo installation to populate the registry before generating new modules. Enables brownfield development -- extending an existing ERP rather than building from scratch. | HIGH | 4 specialized agents: manifest parser, model AST analyzer, security scanner, view pattern detector. Can use amil's MCP server for live XML-RPC introspection. |
| **Atomic Registry Updates with Rollback** | Write registry updates to .tmp file then rename. Keep previous version for rollback. If generation fails after partial registry update, roll back to pre-generation state. | LOW | Standard atomic file write pattern. Version numbering. One-level rollback sufficient. |
| **ERP Readiness Percentage** | Progress dashboard showing: modules by status, registry stats (models, fields, cross-references), computation chain completion, tier completion. Gives humans a clear picture of how close the ERP is to done. | LOW | Computed from module_status.json + model_registry.json + computation_chains.json. Simple aggregation. |
| **Tiered Roadmap Generation** | Instead of a flat phase list, generates a dependency-tiered roadmap: foundation tier (uni_core), core academic tier (student, faculty, program), operations tier (fee, exam, enrollment), communication tier (notification, portal). | MEDIUM | Topological sort with tier grouping. Maps to Amil's phase structure. Each tier becomes a milestone, each module a phase within that milestone. |
| **Generation Manifest Parsing** | After the belt produces a module, parse its generation manifest to extract exactly what was created (models, fields, views, security rules) and update the registry accordingly. Belt output drives registry truth. | MEDIUM | Schema adapts to whatever amil produces (belt defines the schema, not amil). Must handle partial generation (some models created, others failed). |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Parallel Module Generation** | Speed -- generating 20 modules sequentially is slow. Multiple belt invocations at once would cut wall-clock time. | Each belt invocation needs exclusive Docker access, exclusive addons directory, and the registry must be updated atomically between generations. Parallel writes to the registry create race conditions. Parallel Docker installs create port/volume conflicts. At 20 modules, the complexity outweighs the time savings. | Sequential generation within tiers. The real bottleneck is human review, not generation time. Optimize by batching human reviews at tier completion instead. |
| **Direct Odoo Code Generation** | Skip the belt, have the orchestrator generate Python/XML directly. Simpler architecture, fewer moving parts. | The belt (amil) has 8 specialized agents, 13 knowledge files, Jinja2 templates, and Docker validation. Reimplementing this in the orchestrator destroys separation of concerns, creates a monolith, and loses the fresh-context advantage of Task() subagents. | Always invoke through the belt. The orchestrator orchestrates; the belt generates. |
| **Auto-Fix Failed Modules** | When generation fails, automatically retry with AI-generated fixes. No human intervention needed. Full automation. | Silent auto-fixes create insidious bugs. A "fixed" module may pass structural checks but have wrong business logic. The human must see failures and decide: retry (same spec), revise (update spec), or skip (manual fix later). | Present structured error reports with retry/revise/skip options. Human decides. |
| **Real-Time Registry Sync** | Keep the registry in sync with the actual Odoo database in real-time via XML-RPC. Always up-to-date. | Adds a runtime dependency on a running Odoo instance during generation. If the instance is down, generation stops. Creates tight coupling between orchestration-time and runtime. The registry is a build artifact, not a runtime mirror. | Populate registry from generation manifests (build-time). Use map-erp for initial brownfield scanning (one-time). |
| **Multi-Runtime Support** | Support OpenCode, Gemini CLI, Codex alongside Claude Code. Wider adoption. | Amil supports multiple runtimes, but amil depends heavily on Claude Code's Task() subagent mechanism for belt invocation. Other runtimes have different (or no) subagent APIs. Supporting them would require abstracting the most critical integration point. | Claude Code only. The Task() pattern is foundational. Revisit if/when other runtimes gain equivalent subagent capabilities. |
| **GUI Dashboard** | Web-based dashboard showing module status, registry visualization, computation chain diagrams. More visual than CLI output. | Adds a web server, frontend framework, real-time update mechanism. Massive scope increase for a tool used by one team. The CLI progress command provides the same information. | Enhance `/amil:progress` with rich terminal output (tables, color coding, ASCII charts). |
| **Automatic Dependency Resolution** | Auto-detect when a module needs a dependency it has not declared and silently add it. | Silent dependency addition can pull in unintended modules, bloat the dependency tree, and create circular dependency risks. Dependencies should be explicit and human-approved. | Coherence checker flags missing dependencies as errors. Human adds them to the spec. |
| **Full Pre-Population of Base Models** | Scan ALL base Odoo models (200+ models) into the registry at project initialization. Complete reference data. | Adds enormous noise to the registry. Most base models are never referenced by the university ERP. Context window bloat. Slow initialization. | On-demand scanning: only scan a base/OCA module when a generated module declares it as a dependency. |

## Feature Dependencies

```
[PRD Decomposition]
    |-- produces --> [Module Dependency Graph]
    |                    |-- orders --> [Belt Invocation]
    |                    |-- feeds --> [Tiered Roadmap Generation]
    |
    |-- triggers --> [Module-Type Discussion Templates]
                         |-- produces --> [Spec Generation]
                                              |-- requires --> [Model Registry]
                                              |-- triggers --> [Coherence Checking]
                                              |                    |-- reads --> [Model Registry]
                                              |                    |-- reads --> [Computation Chain Tracking]
                                              |                    |-- reads --> [Security Scope Framework]
                                              |
                                              |-- feeds --> [Belt Invocation]
                                                               |-- updates --> [Model Registry]
                                                               |-- requires --> [Registry Injection (Tiered)]
                                                               |-- produces --> [Generation Manifest]
                                                               |                    |-- updates --> [Model Registry]
                                                               |
                                                               |-- triggers --> [Module Status Tracking]

[Configuration Management] -- enables --> [PRD Decomposition]

[Existing Codebase Scanning] -- populates --> [Model Registry]
                                          |-- populates --> [Security Scope Framework]

[On-Demand Third-Party Scanning] -- extends --> [Model Registry]
                                             |-- enables --> [Coherence Checking] (against base/OCA models)

[Command Prefix Renaming] -- independent (no dependencies)
[Per-Module Artifact Directory] -- independent (structural, needed by all commands)
[Human Checkpoints] -- embedded in [Spec Generation], [Belt Invocation], [Coherence Checking]
```

### Dependency Notes

- **Spec Generation requires Model Registry:** The spec must inject `_available_models` from the registry so the belt knows what models exist. Registry must be initialized (even if empty) before any spec can be generated.
- **Coherence Checking reads Registry + Chains + Scopes:** All three state files must exist for coherence checking to work. They can be empty initially, but the checking logic must handle empty state gracefully.
- **Belt Invocation requires Spec + Registry:** The belt consumes the spec and needs the registry for context. Both must be complete and approved before invocation.
- **Generation Manifest updates Registry:** This is a write-after-read cycle. The manifest parser must handle partial outputs (some models created, others failed).
- **On-Demand Third-Party Scanning extends Registry:** When a spec declares `depends: ['hr_payroll']`, the coherence checker needs hr_payroll's models in the registry. Scanning must happen between spec creation and coherence checking.
- **PRD Decomposition requires Configuration:** Odoo version, multi-company, and localization settings influence module boundary decisions.

## MVP Definition

### Launch With (v1)

Minimum viable system to generate one complete Odoo module through the full pipeline.

- [x] **Command Prefix Renaming** -- baseline to make fork functional as independent tool
- [x] **Configuration Management** -- Odoo config block, installer rewrite
- [x] **Model Registry (CRUD + versioning)** -- core state management, read/write/validate/stats
- [x] **Module Status Tracking** -- lifecycle state machine (planned -> shipped)
- [x] **Per-Module Artifact Directory** -- structural requirement for all module operations
- [x] **PRD Decomposition** -- new-erp command, 4 research agents, dependency graph
- [x] **Module Dependency Graph** -- topological sort, tier grouping
- [x] **Module-Type Discussion Templates** -- discuss-module command, at least 3 module types (core, student, fee)
- [x] **Spec Generation** -- plan-module command, spec.json with registry injection
- [x] **Cross-Module Coherence Checking** -- pre-generation validation (Many2one targets, duplicates, scope fields)
- [x] **Registry Injection (Tiered)** -- full/field-list/names-only injection for belt context
- [x] **Belt Invocation via Task()** -- generate-module command, registry update from manifest
- [x] **Human Checkpoints** -- pause at spec review, generation review

### Add After Validation (v1.x)

Features to add once the first full tier of modules has been generated successfully.

- [ ] **Computation Chain Tracking** -- add once multiple dependent modules are generating and chain integrity matters
- [ ] **Security Scope Framework** -- add once dynamic RBAC patterns are validated with first 2-3 modules
- [ ] **Generation Manifest Parsing** -- improve beyond basic manifest reading to handle partial outputs, field-level diffing
- [ ] **ERP Readiness Percentage** -- add once enough modules exist for percentage to be meaningful
- [ ] **Atomic Registry Updates with Rollback** -- add once registry corruption has been observed as a real risk
- [ ] **Tiered Roadmap Generation** -- add once the basic roadmap structure is validated

### Future Consideration (v2+)

Features to defer until the system has been used for at least one complete ERP generation.

- [ ] **Existing Codebase Scanning (map-erp)** -- defer because the university ERP is greenfield. Add for brownfield projects later.
- [ ] **On-Demand Third-Party Model Scanning** -- defer because initial modules (uni_core, uni_student) depend only on base/mail which are well-known. Add when modules need hr_payroll, account, etc.
- [ ] **Full ERP Audit (audit-erp)** -- defer to verification milestone (Phase 3 of PRD)
- [ ] **Quick Fix Command** -- defer until enough modules exist for quick-fix to be useful
- [ ] **Complete Phase with Registry Archival** -- defer to verification milestone

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Model Registry (CRUD) | HIGH | MEDIUM | P1 |
| Module Dependency Graph | HIGH | LOW | P1 |
| Spec Generation | HIGH | HIGH | P1 |
| Cross-Module Coherence Checking | HIGH | HIGH | P1 |
| Belt Invocation via Task() | HIGH | MEDIUM | P1 |
| Module Status Tracking | MEDIUM | LOW | P1 |
| Registry Injection (Tiered) | HIGH | MEDIUM | P1 |
| PRD Decomposition | HIGH | HIGH | P1 |
| Human Checkpoints | MEDIUM | LOW | P1 |
| Configuration Management | MEDIUM | LOW | P1 |
| Command Prefix Renaming | LOW | LOW | P1 |
| Per-Module Artifact Directory | LOW | LOW | P1 |
| Module-Type Discussion Templates | MEDIUM | MEDIUM | P1 |
| Computation Chain Tracking | HIGH | HIGH | P2 |
| Security Scope Framework | HIGH | HIGH | P2 |
| Generation Manifest Parsing (advanced) | MEDIUM | MEDIUM | P2 |
| ERP Readiness Percentage | LOW | LOW | P2 |
| Atomic Registry Rollback | MEDIUM | LOW | P2 |
| Tiered Roadmap Generation | MEDIUM | MEDIUM | P2 |
| Existing Codebase Scanning | MEDIUM | HIGH | P3 |
| On-Demand Third-Party Scanning | MEDIUM | MEDIUM | P3 |
| Full ERP Audit | HIGH | HIGH | P3 |

**Priority key:**
- P1: Must have for launch -- system cannot orchestrate module generation without these
- P2: Should have, add after first tier validates -- increases reliability and traceability
- P3: Nice to have, future milestones -- enables brownfield and verification workflows

## Competitor Feature Analysis

There are no direct competitors doing "AI-orchestrated multi-module Odoo ERP generation." The closest comparisons are partial:

| Feature | Odoo Scaffold (built-in) | OCA maintainer-tools | Workik (AI code gen) | Gemini-Odoo-Module-Generator | amil (our approach) |
|---------|-------------------------|---------------------|---------------------|----------------------------|------------------------|
| Module scaffolding | Basic directory structure only | Template-based with OCA conventions | AI-generated boilerplate | Single-module scaffold | Spec-driven multi-pass generation via belt |
| Cross-module coherence | None | None | None | None | Model registry + coherence checker |
| Dependency ordering | Manual | Manual | N/A | N/A | Automatic topological sort with tier grouping |
| Multi-module state | None | None | None | None | Registry, computation chains, security scopes, module status |
| Human-in-the-loop | N/A | N/A | None (fully automated) | None | Checkpoints at spec, generation, and check |
| Business logic quality | N/A (scaffold only) | N/A (tooling only) | Generic (version-blind, context-vacuum) | Basic | 8 specialized agents with domain knowledge, Docker validation |
| Security management | Manual | Manual | Generic | Basic | Dynamic RBAC with hierarchical scopes |

The key insight: existing tools either scaffold (empty structure) or generate single modules in isolation. None manage cross-module state or enforce coherence across a 20+ module ERP. This is amil's entire reason for existing.

## Sources

- [Odoo Module Dependencies Forum Discussion](https://www.odoo.com/forum/help-1/when-is-it-required-to-add-a-module-as-a-dependency-to-another-module-125784)
- [Odoo 17.0 Registries Documentation](https://www.odoo.com/documentation/17.0/developer/reference/frontend/registries.html)
- [OCA Maintainer Tools](https://github.com/OCA/maintainer-tools)
- [Gemini Odoo Module Generator](https://github.com/jeevanism/Gemini-Odoo-Module-Generator)
- [Workik Odoo ERP Code Generator](https://workik.com/odoo-erp-code-generator)
- [AI Agent Orchestration Patterns - Microsoft](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [Conductors to Orchestrators: Future of Agentic Coding - O'Reilly](https://www.oreilly.com/radar/conductors-to-orchestrators-the-future-of-agentic-coding/)
- [Beyond Code Generation: AI in Odoo Development Lifecycle](https://oduist.com/blog/odoo-experience-2025-ai-summaries-2/305-beyond-code-generation-integrating-ai-into-odoo-s-development-lifecycle-lessons-learned-306)
- [Developing Odoo modules using AI: practical guide](https://oduist.com/blog/odoo-experience-2025-ai-summaries-2/357-developing-odoo-modules-using-ai-a-practical-guide-358)
- [Odoo Module Dependencies Order](https://www.odoo.com/forum/help-1/modules-order-of-dependencies-159563)

---
*Feature research for: Odoo ERP module orchestration (amil)*
*Researched: 2026-03-05*
