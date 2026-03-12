# Project Research Summary

**Project:** amil (Odoo ERP Module Orchestrator)
**Domain:** CLI-based AI orchestration system for multi-module Odoo ERP generation
**Researched:** 2026-03-05
**Confidence:** HIGH

## Executive Summary

amil is a fork of the Amil (Get Shit Done) CLI framework, repurposed to orchestrate the generation of 20+ interdependent Odoo ERP modules through an AI-powered belt pipeline (amil). The core technical challenge is not code generation -- that is delegated to amil via Claude Code's Task() subagent mechanism -- but cross-module coherence: ensuring that Many2one references resolve, computed field dependency chains remain intact, and security scopes are consistent across modules generated sequentially in isolation. The recommended approach is a zero-dependency Node.js CJS system (inherited from Amil's 5400 LOC codebase) with JSON state files for the model registry, module status, computation chains, and security scopes.

The architecture is a three-tier system: orchestration (amil CLI + state management), generation (amil belt invoked per module via Task()), and utilities (amil-utils for AST analysis). The model registry is the keystone component -- nearly every workflow reads or writes it. All state mutations must use atomic write-then-rename patterns with one-level rollback. Registry injection into belt contexts must be tiered from day one (full models for direct depends, field-list for transitive, names-only for rest) to prevent context window exhaustion at scale.

The three highest risks are: (1) fork rename incompleteness -- 233+ hardcoded path references must all be updated or the system fails silently mid-workflow; (2) belt integration against an unfinalized contract -- amil is not yet installed, so all integration code is built on assumptions that need a mock belt and adapter pattern to derisk; (3) cross-module coherence drift -- the registry must reflect what was actually generated (not just what was specified), requiring post-generation AST reconciliation. All three risks have concrete mitigation strategies detailed in the pitfalls research.

## Key Findings

### Recommended Stack

amil inherits Amil's zero-dependency Node.js CJS architecture. This is not a technology choice but a constraint: the fork must maintain compatibility with 34 workflow files, 12 lib modules, and the entire command/agent/workflow architecture. The zero-dependency model enables `git clone` installation with no build step, no `node_modules`, and no version conflicts in the `~/.claude/` directory.

**Core technologies:**
- **Node.js 25.x (CJS):** Runtime inherited from Amil. All code uses `require`/`module.exports`. No ESM conversion.
- **JSON state files:** `model_registry.json`, `module_status.json`, `computation_chains.json`, `security_scope.json`. Machine-facing state in JSON; human-facing state in Markdown (inherited Amil pattern).
- **Node.js built-in test runner:** `node --test` with `assert/strict` and built-in mocking. Zero test dependencies.
- **Inline algorithms:** Topological sort (20 LOC), JSON validation (50 LOC), atomic writes (5 LOC). Each replaces an npm package.
- **Claude Code Task():** Subagent mechanism for belt invocation with fresh 200K context per module.

### Expected Features

**Must have (table stakes):**
- Model Registry with CRUD, atomic updates, versioning, and rollback -- the central state that everything depends on
- Module Dependency Graph with topological sort and tier grouping -- enforces correct generation order
- Spec Generation (spec.json) with registry injection -- the communication contract with the belt
- Cross-Module Coherence Checking -- the defining value proposition (Many2one targets, duplicate models, scope fields)
- Belt Invocation via Task() -- the generation mechanism, one module at a time
- Module Status Tracking -- lifecycle state machine (planned through shipped)
- Tiered Registry Injection -- prevents context window exhaustion at scale
- PRD Decomposition -- 4 parallel research agents decompose the university ERP PRD into modules
- Human Checkpoints -- pause for spec review, generation review, check sign-off
- Configuration Management, Command Prefix Renaming, Per-Module Artifact Directories

**Should have (add after first tier validates):**
- Computation Chain Tracking -- multi-model computed field dependency chains across modules
- Security Scope Framework -- dynamic RBAC with 5 hierarchical scope levels
- Advanced Generation Manifest Parsing -- field-level diffing, partial output handling
- ERP Readiness Percentage -- progress dashboard
- Tiered Roadmap Generation -- dependency-aware roadmap structure

**Defer (v2+):**
- Existing Codebase Scanning (map-erp) -- project is greenfield
- On-Demand Third-Party Model Scanning -- initial modules depend only on well-known base/mail
- Full ERP Audit -- verification milestone concern

### Architecture Approach

A three-layer orchestration system where the CLI Router dispatches commands to lib modules, workflows coordinate multi-step operations via markdown instructions, and agents are spawned as Task() subagents with fresh context. The Registry Manager (`registry.cjs`) is the new keystone component handling all model state CRUD. State flows through JSON files in `.planning/`, with per-module artifacts in `.planning/modules/{module_name}/`. The belt boundary is crossed exclusively through Task() with file-based communication (spec.json in, generation-manifest.json out).

**Major components:**
1. **Registry Manager** (`bin/lib/registry.cjs`) -- Model CRUD, atomic writes, rollback, validation, tiered injection
2. **CLI Router** (`bin/gsd-tools.cjs`) -- Command dispatch, JSON output, state manipulation entry point
3. **Workflow Files** (`workflows/*.md`) -- Multi-step orchestration scripts coordinating agents, state, and human checkpoints
4. **Coherence Checker** (agent + lib) -- Validates referential integrity across all registered modules
5. **Belt Invoker** (within generate-module workflow) -- Prepares context, spawns amil Task(), parses manifest, updates registry
6. **Module Status Tracker** -- Lifecycle state machine with transition gates

### Critical Pitfalls

1. **Fork rename minefield (233+ references)** -- Create a canonical rename manifest before touching files. Build a verification script that greps for ALL old patterns. Rename in layers (paths, prefixes, identifiers) and test each independently.
2. **Registry JSON grows beyond context budget** -- Implement tiered injection from day one. Set hard token budgets per tier (20K direct, 5K transitive, 1K rest). Add `registry stats` command to make size growth visible.
3. **Cross-module coherence breaks silently** -- After each generation, parse actual generated code and update registry with what was produced (not just specified). Block tier progression on coherence failure.
4. **Belt integration against unfinalized contract** -- Create a mock belt and belt adapter module. Define a draft contract even if it changes. Ship a canary integration test early.
5. **State file corruption from non-atomic writes** -- Use write-then-rename pattern from the start. Keep `.bak` files. Add auto-recovery from backup on parse failure.
6. **Security scope explosion (300-800 rules)** -- Use security scope templates that modules reference. Generate security as a separate pass after all models are registered.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Fork Foundation and State Infrastructure
**Rationale:** Everything depends on the renamed fork being functional and the registry being operational. The fork rename must come first (233+ references), followed by the registry which is read/written by every subsequent workflow. Configuration must be extended before any Odoo-specific workflow can operate.
**Delivers:** A working amil CLI fork with model registry CRUD, module status tracking, atomic writes, and Odoo configuration management. Mock belt for testing.
**Addresses:** Command Prefix Renaming, Configuration Management, Model Registry (CRUD + versioning), Module Status Tracking, Per-Module Artifact Directories, Atomic Registry Updates
**Avoids:** Fork rename minefield (Pitfall 1), State file corruption (Pitfall 5), Registry growth without visibility (Pitfall 2)

### Phase 2: PRD Decomposition and Module Planning
**Rationale:** Before any module can be generated, the university ERP PRD must be decomposed into modules with clear boundaries, dependencies, and tier assignments. This phase also establishes the discuss-module and plan-module workflows that produce specs.
**Delivers:** `new-erp` command with 4 parallel research agents, `discuss-module` with type-specific templates, `plan-module` with spec generation and coherence checking. ROADMAP.md with tiered structure.
**Addresses:** PRD Decomposition, Module Dependency Graph, Module-Type Discussion Templates, Spec Generation, Cross-Module Coherence Checking, Registry Injection (Tiered), Human Checkpoints
**Avoids:** Cross-module incoherence (Pitfall 3), Full registry injection anti-pattern (Pitfall 2)

### Phase 3: Belt Integration and Module Generation
**Rationale:** With specs approved and coherence validated, this phase connects to the actual belt (amil) for module generation. This is the highest-risk phase -- it crosses the amil/amil boundary. All Phase 1 and 2 components must be solid.
**Delivers:** `generate-module` command with belt invocation via Task(), manifest parsing, post-generation registry update, and post-generation coherence reconciliation.
**Addresses:** Belt Invocation via Task(), Generation Manifest Parsing, Post-generation registry reconciliation
**Avoids:** Belt contract assumptions (Pitfall 4), Spec-vs-reality drift (Pitfall 3)

### Phase 4: Verification and Quality Assurance
**Rationale:** After modules are generated, they need multi-level checking (structural, cross-module, spec coverage, integration/Docker). This phase also adds progress visibility and tier completion workflows.
**Delivers:** `check-module` command with 4-level verification, `progress` command with ERP readiness stats, `complete-phase` command with registry archival.
**Addresses:** Module verification, ERP Readiness Percentage, tier completion tracking
**Avoids:** Security scope explosion (Pitfall 6) -- security validation is part of check-module

### Phase 5: Advanced Features and Polish
**Rationale:** After the core pipeline works end-to-end, add computation chain tracking, security scope framework, hooks, and remaining polish.
**Delivers:** Computation chain tracking, security scope framework with templates, statusline hooks, context monitoring, install.js rewrite.
**Addresses:** Computation Chain Tracking, Security Scope Framework, Tiered Roadmap Generation, hooks and polish
**Avoids:** Premature complexity -- these features are validated only after the base pipeline works

### Phase Ordering Rationale

- **Foundation first** because 233+ hardcoded references must be renamed before any new code is added, and the registry is the dependency for every workflow.
- **Planning before generation** because specs must be validated for coherence before belt invocation. Generating against bad specs wastes expensive belt context.
- **Belt integration is isolated** in its own phase because it is the highest-risk component with the most unknowns (amil is not installed). Isolation allows the mock belt to derisk before real integration.
- **Verification after generation** because check-module needs actual generated artifacts to validate against.
- **Advanced features last** because computation chains and security scopes add value only after multiple modules exist and cross-module interactions are real.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (PRD Decomposition):** The 4 parallel research agent pattern for module boundary analysis is novel. Needs research into how to merge conflicting agent outputs and how to handle PRDs that don't decompose cleanly into Odoo modules.
- **Phase 3 (Belt Integration):** amil is not installed. The belt contract, manifest schema, and Task() invocation pattern all need validation against the actual belt. A canary integration test is mandatory before building the full workflow.
- **Phase 4 (Verification):** Docker integration testing patterns for Odoo modules need research -- how to set up test databases, handle module install ordering in Docker, and validate cross-module record rules.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Fork renaming, JSON file CRUD, atomic writes, and CLI command routing are all well-established patterns with clear implementations from the STACK and ARCHITECTURE research.
- **Phase 5 (Advanced Features):** Computation chain tracking is a directed graph problem with known algorithms. Security scope templates follow documented Odoo RBAC patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero-dependency CJS is inherited from Amil, confirmed by direct codebase inspection of 96 files. No technology decisions needed -- only implementation patterns. |
| Features | HIGH | Features derived from authoritative PRD + Odoo domain patterns. Competitor analysis confirms no existing tool does cross-module coherence. Feature prioritization is well-justified. |
| Architecture | HIGH | Architecture directly extends Amil's proven command/workflow/agent pattern. Component boundaries and data flows are well-defined. Build order reflects real dependencies. |
| Pitfalls | HIGH | Pitfalls backed by direct codebase inspection (233 reference count), ecosystem research (fork maintenance studies, context window research), and Odoo-specific failure modes (forum posts on dependency/security issues). |

**Overall confidence:** HIGH

### Gaps to Address

- **Belt contract:** amil is not installed. The spec.json schema, generation-manifest.json format, and Task() invocation parameters are all assumptions. Must create mock belt and validate with canary test in Phase 3.
- **Odoo 17 model schemas:** Pre-built registry snapshots for base modules (base, mail, account, hr) need verification against actual Odoo 17.0 source. Training data may reflect Odoo 16 field names.
- **Task() subagent limits:** The research assumes Task() provides a full fresh 200K context. Need to verify actual available context after Claude Code overhead, system prompts, and tool definitions.
- **Amil upstream evolution:** The fork diverges immediately. No strategy exists for incorporating future Amil improvements. FORK_DIFF.md is recommended but the merge-forward process is undefined.

## Sources

### Primary (HIGH confidence)
- Amil codebase -- Direct inspection of `bin/lib/*.cjs` (5400 LOC), 96 files, zero npm dependencies confirmed
- AMIL_PRD.md -- Authoritative project specification with architecture, state schemas, and workflow definitions
- Odoo 17.0 Documentation -- Module manifests, field types, security model, model inheritance

### Secondary (MEDIUM confidence)
- EclipseSource VS Code fork analysis -- Fork maintenance burden patterns applicable to Amil fork
- Maxim/Factory.ai context window research -- Context management strategies for registry injection
- TOON vs JSON research (jduncan.io) -- JSON token inefficiency quantification (40% structural overhead)
- Odoo community forums -- Module dependency ordering, Many2one field bugs, interdependency problems
- Microsoft/Google multi-agent architecture guides -- Orchestration patterns, state-based context isolation

### Tertiary (LOW confidence)
- Odoo 17 field-level details from training data -- May reflect Odoo 16 schemas; needs verification during Phase 3

---
*Research completed: 2026-03-05*
*Ready for roadmap: yes*
