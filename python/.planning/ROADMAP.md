# Roadmap: Agentic Odoo Module Development Workflow

## Milestones

- **v1.0 Odoo Module Automation MVP** — Phases 1-9 (shipped 2026-03-03) | [Archive](milestones/v1.0-ROADMAP.md)
- **v1.1 Tech Debt Cleanup** — Phases 10-11 (shipped 2026-03-03)
- **v1.2 Template Quality** — Phases 12-14 (shipped 2026-03-04) | [Archive](milestones/v1.2-ROADMAP.md)
- **v2.0 Environment-Aware Generation** — Phases 15-17 (shipped 2026-03-04)
- **v2.1 Auto-Fix & Enhancements** — Phases 18-19 (shipped 2026-03-04) | [Archive](milestones/v2.1-ROADMAP.md)
- **v3.0 Bug Fixes & Tech Debt** — Phases 20-25 (shipped 2026-03-05) | [Archive](milestones/v3.0-ROADMAP.md)
- **v3.1 Design Flaws & Feature Gaps** — Phases 26-35 (shipped 2026-03-05)
- **v3.2 Security, Business Logic & Context7** — Phases 36-44 (shipped 2026-03-07) | [Archive](milestones/v3.2-ROADMAP.md)
- **v3.3 Test Fixes, Domain Patterns & Architecture** — Phases 45-54 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-9) — SHIPPED 2026-03-03</summary>

- [x] Phase 1: Amil Extension + Odoo Foundation (4/4 plans) — completed 2026-03-01
- [x] Phase 2: Knowledge Base (3/3 plans) — completed 2026-03-01
- [x] Phase 3: Validation Infrastructure (3/3 plans) — completed 2026-03-01
- [x] Phase 4: Input & Specification (2/2 plans) — completed 2026-03-02
- [x] Phase 5: Core Code Generation (3/3 plans) — completed 2026-03-02
- [x] Phase 6: Security & Test Generation (2/2 plans) — completed 2026-03-02
- [x] Phase 7: Human Review & Quality Loops (3/3 plans) — completed 2026-03-03
- [x] Phase 8: Search & Fork-Extend (3/3 plans) — completed 2026-03-03
- [x] Phase 9: Edition & Version Support (3/3 plans) — completed 2026-03-03

**Total:** 9 phases, 26 plans, 68 requirements | 139 commits | 4,150 LOC Python | 243 tests

</details>

<details>
<summary>v1.1 Tech Debt Cleanup (Phases 10-11) — SHIPPED 2026-03-03</summary>

- [x] Phase 10: Environment & Dependencies — completed 2026-03-03
- [x] Phase 11: Live Integration Testing & i18n — completed 2026-03-03

</details>

<details>
<summary>v1.2 Template Quality (Phases 12-14) — SHIPPED 2026-03-04</summary>

- [x] Phase 12: Template Correctness & Auto-Fix (2/2 plans) — completed 2026-03-03
- [x] Phase 13: Golden Path Regression Testing (1/1 plan) — completed 2026-03-03
- [x] Phase 14: Cleanup/Debug the Tech Debt (1/1 plan) — completed 2026-03-04

**Total:** 3 phases, 4 plans, 12 requirements | 29 commits

</details>

<details>
<summary>v2.0 Environment-Aware Generation (Phases 15-17) — SHIPPED 2026-03-04</summary>

- [x] Phase 15-17: 3 phases, 6 plans — completed 2026-03-04

</details>

<details>
<summary>v2.1 Auto-Fix & Enhancements (Phases 18-19) — SHIPPED 2026-03-04</summary>

- [x] Phase 18-19: 2 phases, 5 plans — completed 2026-03-04

</details>

<details>
<summary>v3.0 Bug Fixes & Tech Debt (Phases 20-25) — SHIPPED 2026-03-05</summary>

- [x] Phase 20-25: 6 phases, 11 plans — completed 2026-03-05

</details>

<details>
<summary>v3.1 Design Flaws & Feature Gaps (Phases 26-35) — SHIPPED 2026-03-05</summary>

- [x] Phase 26-35: 10 phases, 12 plans — completed 2026-03-05

</details>

<details>
<summary>v3.2 Security, Business Logic & Context7 (Phases 36-44) — SHIPPED 2026-03-07</summary>

- [x] Phase 36-44: 9 phases, 15 plans — completed 2026-03-07

</details>

### v3.3 Test Fixes, Domain Patterns & Architecture (In Progress)

**Milestone Goal:** Fix all 36 broken tests, add domain-specific generation patterns (documents, Pakistan/HEC, academic calendar), strengthen architecture (Pydantic validation, model registry, semantic validation, generation manifest, checkpoint hooks, state persistence), and add developer tooling (Mermaid graphs).

**Parallel execution:** Two-track git worktree strategy (infra track + features track) with strict file ownership.

- [x] **Phase 45: Preprocessor Split** - Extract 1,715-line preprocessors.py into preprocessors/ package with decorator-based registry (completed 2026-03-07)
- [x] **Phase 46: Test Infrastructure** - Fix 36 broken tests and pin dependency upper bounds (completed 2026-03-07)
- [x] **Phase 47: Pydantic Spec Validation** - Pydantic v2 spec schema with protected_namespaces, backward-compatible defaults, JSON Schema export (gap closure: model_dump regression fix) (completed 2026-03-08)
- [x] **Phase 48: Model Registry** - Cross-module model registry with JSON persistence, comodel validation, cycle detection (completed 2026-03-08)
- [x] **Phase 49: Pakistan/HEC Localization** - CNIC, phone, PKR, NTN/STRN, HEC fields as generation patterns (completed 2026-03-08)
- [x] **Phase 50: Academic Calendar** - academic.year, academic.term, academic.batch models with overlap prevention (completed 2026-03-08)
- [x] **Phase 51: Semantic Validation** - Pre-Docker AST + XML cross-check catching 60-70% of bugs in <1 second (completed 2026-03-08)
- [x] **Phase 52: Document Management** - Document types, Binary storage, verification workflow, Odoo 18 discuss.channel gate (completed 2026-03-08)
- [x] **Phase 53: Mermaid Graphs** - Module dependency DAG and model ER diagrams as .mmd files (completed 2026-03-08)
- [x] **Phase 54: Pipeline Quality of Life** - Generation manifest, checkpoint hooks, and state persistence with resume (completed 2026-03-08)

## Phase Details

### Phase 45: Preprocessor Split
**Goal**: Preprocessors live in a dedicated package with a decorator-based registry, unblocking domain pattern phases that would otherwise push a 1,715-line monolith past 2,500 lines
**Depends on**: Nothing (first phase of v3.3)
**Requirements**: INFR-01
**Success Criteria** (what must be TRUE):
  1. `preprocessors/` package exists with each preprocessor in its own file, importable via `from amil_utils.preprocessors import run_preprocessors`
  2. A decorator-based registry (`@register_preprocessor`) controls preprocessor discovery and ordering without manual import lists
  3. All existing tests pass without modification -- zero behavior change for the render pipeline
  4. Adding a new preprocessor requires only creating a new file with the decorator -- no edits to `__init__.py` or registry configuration
**Plans:** 2/2 plans complete
Plans:
- [ ] 45-01-PLAN.md — Create registry infrastructure, split preprocessors into domain files with decorators
- [ ] 45-02-PLAN.md — Wire renderer to use run_preprocessors(), delete old monolith, full regression

### Phase 46: Test Infrastructure
**Goal**: CI is green with all 36 previously broken tests passing or properly skipped, and dependency pins prevent future silent breakage
**Depends on**: Nothing (independent of Phase 45)
**Requirements**: TFIX-01, TFIX-02
**Success Criteria** (what must be TRUE):
  1. All 21 MCP server test errors are resolved via proper import path resolution (not by deleting or skipping the tests)
  2. Search index tests with optional PyGithub dependency use `pytest.importorskip` guards and pass in both with-dep and without-dep environments
  3. Verifier integration tests skip cleanly when Docker is not running (via `conftest.py` fixture), and pass when Docker is available
  4. `pyproject.toml` pins `mcp>=1.9,<2.0`, `pytest-asyncio>=1.0,<2.0`, and `chromadb>=1.5,<2.0` with upper bounds
  5. `pytest` run with no Docker reports 0 failures and 0 errors (skips are acceptable)
**Plans:** 1/1 plans complete
Plans:
- [ ] 46-01-PLAN.md — Fix import guards, add pytest.importorskip to test files, create conftest.py Docker skip fixture, pin dependency upper bounds

### Phase 47: Pydantic Spec Validation
**Goal**: Module specs are validated against a typed Pydantic v2 schema before preprocessing, catching malformed input early while remaining backward-compatible with all existing specs
**Depends on**: Phase 45 (preprocessor package must exist for pipeline integration point)
**Requirements**: ARCH-01
**Success Criteria** (what must be TRUE):
  1. `validate_spec()` runs BEFORE preprocessors in `render_module()` and returns a validated Pydantic model with defaults filled for all optional fields
  2. All Pydantic models use `ConfigDict(protected_namespaces=())` so Odoo's `model_name`, `model_description` etc. work without conflict
  3. Existing spec fixtures (spec_v1.json, spec_v2.json, and all test specs) validate successfully with no modifications -- `extra="allow"` ensures backward compatibility
  4. `amil export-schema` outputs a JSON Schema file that provides autocomplete in VS Code / any JSON-aware editor
  5. Validation failures produce hard errors (not warnings) -- bad specs fail early before wasting Docker time (user decision overrides original criteria #5)
**Plans:** 3/3 plans complete
Plans:
- [x] 47-01-PLAN.md — Create spec_schema.py with Pydantic models, validate_spec(), format_validation_errors(), and TDD tests
- [x] 47-02-PLAN.md — Wire validation into renderer.py, add export-schema CLI command, full regression
- [ ] 47-03-PLAN.md — Fix model_dump() regression: exclude_none=True + update mutation-dependent test

### Phase 48: Model Registry
**Goal**: The system tracks all generated models across modules, enabling comodel validation and depends inference without requiring a running Odoo instance
**Depends on**: Nothing (independent of Phase 47)
**Requirements**: ARCH-02
**Success Criteria** (what must be TRUE):
  1. After generating a module, its models are registered in `.amil-registry.json` with model names, field definitions, and module membership
  2. When a spec references a comodel (Many2one, One2many, Many2many), the registry validates that the comodel exists and warns if it does not
  3. `depends` list in `__manifest__.py` is automatically inferred from comodel references found in the registry (no manual depends required for registered modules)
  4. Circular dependency between modules is detected and reported before generation proceeds
  5. Registry operations are called from the CLI layer (not inside render pipeline) -- render_module() has no knowledge of the registry
**Plans:** 2/2 plans complete
Plans:
- [ ] 48-01-PLAN.md — Registry core module + known_odoo_models.json + TDD tests
- [ ] 48-02-PLAN.md — CLI command group + post-render hook + gitignore fix

### Phase 49: Pakistan/HEC Localization
**Goal**: Specs requesting Pakistan localization generate models with properly validated CNIC, phone, NTN/STRN, PKR currency, and HEC academic fields -- covering the first Pakistan-specific Odoo generation capability in the ecosystem
**Depends on**: Phase 45 (preprocessor package for domain preprocessor registration), Phase 47 (Pydantic schema for localization spec keys)
**Requirements**: DOMN-02
**Success Criteria** (what must be TRUE):
  1. A spec with `localization: pakistan` generates CNIC fields with normalize-then-validate logic handling all 5 edge cases (no-dash, province code, gender digit, old format, NICOP)
  2. Pakistani phone fields use the `phonenumbers` library for validation, supporting mobile (03XX), landline, and international (+92) formats
  3. PKR currency is injected via `res.currency` reference (not hardcoded symbol), and NTN/STRN tax identifier fields are generated for FBR compliance
  4. HEC fields (registration number, GPA on 4.0 scale, credit hours, recognition status) are generated when `hec: true` is present in the localization config
  5. All Pakistan-specific logic lives in `preprocessors/pakistan_hec.py` -- zero changes to core preprocessor files
**Plans:** 2/2 plans complete
Plans:
- [ ] 49-01-PLAN.md — Pakistan/HEC preprocessor with TDD: CNIC, phone, NTN/STRN, HEC fields, PKR flag, pyproject.toml extras
- [ ] 49-02-PLAN.md — Renderer integration: extra_data_files extension point, PKR XML rendering, template pk_* branch, E2E tests

### Phase 50: Academic Calendar
**Goal**: Specs requesting academic calendar generate a complete semester/term management system with overlap prevention and automatic term generation, following OpenEduCat naming conventions
**Depends on**: Phase 45 (preprocessor package), Phase 47 (Pydantic schema for academic_calendar spec key)
**Requirements**: DOMN-03
**Success Criteria** (what must be TRUE):
  1. A spec with `academic_calendar: true` generates `academic.year`, `academic.term`, and `academic.batch` models with proper relationships (term belongs to year, batch belongs to term)
  2. `@api.constrains` on date fields prevents overlapping terms within the same academic year and overlapping academic years
  3. `term_structure` Selection field on academic year (e.g., semester, trimester, quarter) drives automatic term generation with computed date splits
  4. Academic year is a Char field (e.g., "2025-2026"), not a Many2one to `account.fiscal.year`
  5. All academic calendar logic lives in `preprocessors/academic_calendar.py` -- zero changes to core preprocessor files
**Plans:** 2/2 plans complete
Plans:
- [ ] 50-01-PLAN.md — Academic calendar preprocessor with TDD: 3 model builders, overlap constraints, term auto-generation, config handling
- [ ] 50-02-PLAN.md — Renderer integration: ac_* and ac_action_* template branches, needs_api extension, E2E tests, registry count update

### Phase 51: Semantic Validation
**Goal**: A pre-Docker validation pass catches field reference errors, XML ID conflicts, ACL mismatches, and manifest gaps in under 1 second -- eliminating the 30-60 second Docker round-trip for the majority of bugs
**Depends on**: Phase 48 (model registry for cross-model reference validation)
**Requirements**: ARCH-03
**Success Criteria** (what must be TRUE):
  1. AST-parsed generated Python files are cross-checked against the spec: every field referenced in views exists in the model, every comodel in relational fields is defined or registered
  2. XML IDs across all generated XML files are unique within the module -- duplicates are reported as errors
  3. ACL CSV entries reference models that actually exist in the generated module (no typos in `model_id:id` column)
  4. Manifest `depends` list is validated for completeness: if generated code imports from `odoo.addons.X`, then `X` must appear in depends
  5. Full semantic validation completes in under 2 seconds for a typical module (5 models, 10 views)
**Plans:** 2/2 plans complete
Plans:
- [ ] 51-01-PLAN.md — Semantic validation module with all 10 checks (E1-E6, W1-W4) + TDD tests
- [ ] 51-02-PLAN.md — CLI integration with --skip-validation flag + E2E tests

### Phase 52: Document Management
**Goal**: Specs requesting document management generate a complete document lifecycle system with type classification, file storage, verification workflow, and Odoo 18 discuss.channel compatibility
**Depends on**: Phase 45 (preprocessor package), Phase 47 (Pydantic schema for document spec keys)
**Requirements**: DOMN-01, DOMN-04
**Success Criteria** (what must be TRUE):
  1. A spec with `documents: true` generates document type classification model, Binary file storage fields with `attachment=True` (never in-database), and metadata fields (upload date, file size, mime type)
  2. Document models have a `verification_state` field (separate from approval `state`) with its own button group and workflow transitions (draft/pending/verified/rejected)
  3. Simple version tracking is generated: new uploads create version records, previous versions remain accessible
  4. Templates generate `mail.channel` references for Odoo 17.0 and `discuss.channel` for Odoo 18.0 via version-conditional blocks
  5. All document management logic lives in `preprocessors/document_management.py` -- zero changes to core preprocessor files
**Plans:** 2/2 plans complete
Plans:
- [ ] 52-01-PLAN.md — Document management preprocessor TDD: model builders, verification workflow, version tracking, security roles, file validation
- [ ] 52-02-PLAN.md — Renderer integration: template field kwargs + doc_* constraint dispatch + VERSION_GATES + E2E tests + registry count

### Phase 53: Mermaid Graphs
**Goal**: Developers can visualize module dependencies and model relationships as Mermaid diagrams renderable in GitHub and VS Code
**Depends on**: Phase 48 (model registry provides the data for dependency graphs)
**Requirements**: TOOL-01
**Success Criteria** (what must be TRUE):
  1. `amil mermaid --module <name>` generates `.mmd` files with a directed acyclic graph of module dependencies and an ER diagram
  2. `amil mermaid --project` generates project-level diagrams from the full registry
  3. Generated `.mmd` files render correctly in GitHub markdown preview and VS Code Mermaid extension without manual editing
  4. Node names with dots (e.g., `res.partner`) are sanitized to valid Mermaid identifiers with display labels preserving the original name
**Plans:** 2/2 plans complete
Plans:
- [x] 53-01-PLAN.md — Core mermaid.py module TDD: _mermaid_id, generate_dependency_dag, generate_er_diagram, field filtering, file writing
- [ ] 53-02-PLAN.md — CLI mermaid command + auto-generation hook in render_module_cmd + integration tests

### Phase 54: Pipeline Quality of Life
**Goal**: The generation pipeline produces a manifest of what it generated, supports human checkpoint callbacks at key stages, and can resume from where it left off after interruption
**Depends on**: Phase 45 (preprocessor package for hook integration points), Phase 47 (Pydantic for manifest schema)
**Requirements**: ARCH-04, ARCH-05, ARCH-06
**Success Criteria** (what must be TRUE):
  1. After generation, `.amil-manifest.json` sidecar contains file paths, SHA256 checksums, template versions used, and list of preprocessors that ran
  2. `RenderHook` Protocol in `renderer.py` defines `on_preprocess_complete`, `on_stage_complete`, `on_render_complete` callbacks -- when `hooks=None` (default), zero overhead
  3. Amil workflows can instantiate a hook object that pauses for human review at configured pipeline stages (post-preprocess, post-stage, post-render)
  4. `GenerationSession` dataclass tracks which stages have completed, persisted to the artifact state sidecar
  5. `render_module(resume_from=<stage>)` skips already-completed stages and resumes from the specified point, enabling recovery from interruptions
**Plans:** 2/2 plans complete
Plans:
- [ ] 54-01-PLAN.md — Generation manifest + RenderHook protocol + GenerationSession dataclass TDD
- [ ] 54-02-PLAN.md — CLI integration: resume_from parameter, hook instantiation, state persistence

## Progress

**Execution Order:**
Phases execute sequentially: 45 -> 46 -> 47 -> 48 -> 49 -> 50 -> 51 -> 52 -> 53 -> 54

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-9 | v1.0 | 26/26 | Complete | 2026-03-03 |
| 10-11 | v1.1 | - | Complete | 2026-03-03 |
| 12-14 | v1.2 | 4/4 | Complete | 2026-03-04 |
| 15-17 | v2.0 | 6/6 | Complete | 2026-03-04 |
| 18-19 | v2.1 | 5/5 | Complete | 2026-03-04 |
| 20-25 | v3.0 | 11/11 | Complete | 2026-03-05 |
| 26-35 | v3.1 | 12/12 | Complete | 2026-03-05 |
| 36-44 | v3.2 | 15/15 | Complete | 2026-03-07 |
| 45. Preprocessor Split | 2/2 | Complete    | 2026-03-07 | - |
| 46. Test Infrastructure | 1/1 | Complete    | 2026-03-07 | - |
| 47. Pydantic Spec Validation | 3/3 | Complete    | 2026-03-08 | - |
| 48. Model Registry | 2/2 | Complete    | 2026-03-08 | - |
| 49. Pakistan/HEC Localization | 2/2 | Complete    | 2026-03-08 | - |
| 50. Academic Calendar | 2/2 | Complete    | 2026-03-08 | - |
| 51. Semantic Validation | 2/2 | Complete    | 2026-03-08 | - |
| 52. Document Management | 2/2 | Complete    | 2026-03-08 | - |
| 53. Mermaid Graphs | 2/2 | Complete    | 2026-03-08 | - |
| 54. Pipeline Quality of Life | 2/2 | Complete    | 2026-03-08 | - |

---
*Roadmap created: 2026-03-01*
*v1.0 shipped: 2026-03-03*
*v1.1 shipped: 2026-03-03*
*v1.2 shipped: 2026-03-04*
*v2.0 shipped: 2026-03-04*
*v2.1 shipped: 2026-03-04*
*v3.0 shipped: 2026-03-05*
*v3.1 shipped: 2026-03-05*
*v3.2 shipped: 2026-03-07*
*v3.3 roadmap created: 2026-03-07*
