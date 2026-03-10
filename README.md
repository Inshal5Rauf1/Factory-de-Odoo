<p align="center">
  <img src="orchestrator/assets/factory-logo.svg" alt="Factory de Odoo" width="500"/>
</p>

<h1 align="center">Factory de Odoo</h1>

<p align="center">
  <strong>The AI-Powered Odoo Module Factory</strong><br/>
  Describe a business need in natural language. Get production-grade Odoo modules — complete with models, views, security, tests, and i18n.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#commands">Commands</a> &bull;
  <a href="#testing">Testing</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Odoo-17.0%20%7C%2018.0-875A7B?logo=odoo&logoColor=white" alt="Odoo Version"/>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Node.js-20+-339933?logo=node.js&logoColor=white" alt="Node.js"/>
  <img src="https://img.shields.io/badge/Tests-3027%20passing-brightgreen" alt="Tests"/>
  <img src="https://img.shields.io/badge/License-MIT%20%2F%20LGPL--3-blue" alt="License"/>
</p>

---

## What Is This?

**Factory de Odoo** is a monorepo containing two tightly integrated systems that together form a complete Odoo module generation pipeline:

| Component | Role | Tech |
|-----------|------|------|
| **[Orchestrator](#orchestrator)** (`orchestrator/`) | Decomposes an ERP into 20+ modules, manages cross-module state, drives sequential generation | Node.js (CJS), 747 tests |
| **[Pipeline](#pipeline)** (`pipeline/`) | Renders individual Odoo modules from specs using 8 AI agents, Jinja2 templates, and Docker validation | Python 3.12, 2284 tests |

Together: **3,027 tests**, **23,500+ LOC Python**, **43 CJS modules**, **24 Jinja2 templates**, **8 specialized AI agents**, **13 Odoo knowledge files**.

---

## How It Works

```
                          YOU
                           |
                    "Build me a university ERP with
                     fee management, timetabling,
                     student records, and exams"
                           |
              +------------v-----------+
              |      ORCHESTRATOR      |  Decomposes PRD into 20+ modules
              |  (Cross-Module Brain)  |  Orders by dependency graph
              +------------+-----------+  Maintains model registry
                           |
           For each module, sequentially:
                           |
              +------------v-----------+
              |       PIPELINE         |  8 agents generate code
              | (Single-Module Belt)   |  Jinja2 renders templates
              +------------+-----------+  Docker validates output
                           |
              +------------v-----------+
              |    COHERENCE CHECK     |  Many2one targets valid?
              |  (Back to Orchestrator)|  No duplicate models?
              +------------+-----------+  Security groups exist?
                           |
                    Production-Grade
                     Odoo Modules
```

### The Key Innovation: Cross-Module Coherence

Most code generators produce isolated modules. Factory de Odoo maintains a **Model Registry** — a central database of every model, field, and relation across all generated modules. When generating module #15, the system knows about all 14 previously generated modules and ensures:

- Every `Many2one` points to a model that actually exists
- No two modules define the same model name
- Computed field dependencies resolve across module boundaries
- Security groups referenced in ACLs are defined somewhere
- Menu hierarchies are consistent

---

## Quick Start

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.12 (not 3.13+) | Pipeline rendering, validation |
| **Node.js** | 20+ | Orchestrator CLI |
| **Docker + Compose v2** | Latest | Module validation |
| **uv** | Latest | Python package manager |
| **An AI coding assistant** | Any | Claude Code, Gemini, Codex, or OpenCode |

> **Why Python 3.12?** Odoo 17.0 supports 3.10-3.12 only. Python 3.13+ introduces breaking changes in `ast` and `importlib` that cause validation failures.

### Installation

```bash
# Clone the repo
git clone https://github.com/Inshal5Rauf1/Factory-de-Odoo.git
cd Factory-de-Odoo

# Install the orchestrator
cd orchestrator
npm install  # dev dependencies only (0 runtime deps)
cd ..

# Install the pipeline
cd pipeline
bash install.sh  # Sets up Python venv, installs odoo-gen-utils, links agents
cd ..
```

### Configuration

The orchestrator needs to know where the pipeline lives. In your ERP project's `.planning/config.json`:

```json
{
  "odoo": {
    "gen_path": "/path/to/Factory-de-Odoo/pipeline",
    "odoo_version": "17.0",
    "edition": "community",
    "addons_path": "./addons"
  }
}
```

Or set the environment variable:

```bash
export ODOO_GEN_PATH="/path/to/Factory-de-Odoo/pipeline"
```

### Your First Module

```
/odoo-gsd:new-erp
> "I need a university ERP with student registration,
>  fee invoicing, exam scheduling, and timetable management"
```

The orchestrator will:
1. Decompose your description into individual modules
2. Build a dependency graph (which modules depend on which)
3. Generate each module sequentially through the pipeline
4. Validate cross-module coherence at every step

For a single module without orchestration:

```
/odoo-gen:new
> "Employee training course tracker with sessions and certificates"
```

---

## Architecture

```
Factory-de-Odoo/
|
+-- orchestrator/                 # Cross-module brain
|   +-- odoo-gsd/bin/lib/         # 43 CJS modules (registry, coherence, status)
|   +-- agents/                   # 20 orchestration agents
|   +-- commands/odoo-gsd/        # 30 slash commands (/odoo-gsd:*)
|   +-- tests/                    # 747 tests (Node.js native test runner)
|   +-- .planning/                # State files (config, roadmap, registry)
|
+-- pipeline/                     # Single-module generation belt
    +-- python/src/odoo_gen_utils/ # Rendering engine, validation, search
    +-- agents/                   # 8 specialized generation agents
    +-- commands/                 # 13 slash commands (/odoo-gen:*)
    +-- knowledge/                # 13 Odoo knowledge files (80+ examples)
    +-- templates/                # 24 Jinja2 templates (17.0 / 18.0 / shared)
    +-- docker/                   # Odoo 17 + PostgreSQL 16 validation
    +-- python/tests/             # 2284 tests (pytest)
```

### Orchestrator Deep Dive

The orchestrator manages the full ERP lifecycle — module decomposition, cross-module state tracking, and sequential generation through the pipeline.

**Module Lifecycle:**
```
planned --> spec_approved --> generated --> checked --> shipped
```

**Key Components:**

| Component | File | Purpose |
|-----------|------|---------|
| Model Registry | `lib/registry.cjs` | Central model/field tracking with atomic writes, versioning, rollback |
| Coherence Checker | `lib/coherence.cjs` | 4 structural checks (Many2one targets, duplicates, dependencies, security) |
| Module Status | `lib/module-status.cjs` | State machine with valid transitions |
| Dependency Graph | `lib/dependency-graph.cjs` | Topological sort for generation order |
| Spec Generator | `agents/odoo-gsd-spec-generator.md` | Produces `spec.json` from module discussions |
| Belt Executor | `agents/odoo-gsd-belt-executor.md` | Invokes pipeline, captures output |

**PRD Decomposition (4 parallel agents):**
1. Module Boundary Analyzer — functional domains, model proposals
2. OCA Registry Checker — build/extend/skip recommendations
3. Dependency Mapper — cross-domain references, circular risk
4. Computation Chain Identifier — data flow across models

### Pipeline Deep Dive

The pipeline generates a single Odoo module from a JSON specification.

**8 Specialized AI Agents:**

| Agent | Role |
|-------|------|
| `odoo-scaffold` | Initial module structure |
| `odoo-model-gen` | Python model classes with ORM fields |
| `odoo-view-gen` | XML views (form, tree, kanban, search) |
| `odoo-security-gen` | ACLs, record rules, security groups |
| `odoo-test-gen` | Python test cases |
| `odoo-validator` | pylint-odoo + Docker validation |
| `odoo-search` | ChromaDB semantic search across OCA |
| `odoo-extend` | Fork-and-extend existing modules |

**Validation Pipeline:**
```
pylint-odoo --> Docker Install --> Docker Tests --> Auto-Fix Loop (5 iterations max)
```

**Auto-Fix Capabilities:**
- Missing `mail.thread` inheritance (when chatter XML exists)
- Unused Python imports (AST-based removal)
- XML parse errors
- Missing ACL entries
- Manifest load order issues
- pylint-odoo violations

**24 Jinja2 Templates** covering:
- Model classes (`model.py.j2`)
- Form/tree/search views (`view_form.xml.j2`)
- Security groups and ACLs
- Cron jobs, reports, wizards
- Portal controllers
- i18n extraction
- Docker Compose for dev

---

## Commands

### Orchestrator Commands (`/odoo-gsd:*`)

| Command | Description |
|---------|-------------|
| `new-erp` | Initialize ERP project, decompose PRD into modules |
| `discuss-module` | Module-specific Q&A with domain question templates |
| `plan-module` | Generate `spec.json` with coherence check |
| `generate-module` | Invoke pipeline belt, update registry |
| `progress` | Module status dashboard + registry stats |
| `plan-phase` | Create detailed phase plan |
| `execute-phase` | Execute plans with wave-based parallelization |
| `verify-work` | Validate completed work through conversational UAT |
| `health` | Diagnose planning directory health |
| `help` | Show all available commands |

### Pipeline Commands (`/odoo-gen:*`)

| Command | Description |
|---------|-------------|
| `new` | Scaffold module from natural language |
| `validate` | Run pylint-odoo + Docker validation |
| `search` | Semantic search across 200+ OCA repositories |
| `extend` | Fork and extend an existing OCA module |
| `plan` | Plan module architecture before generation |
| `research` | Research Odoo patterns and solutions |
| `index` | Build/update ChromaDB search index |
| `phases` | Show generation phases and progress |
| `status` | Current module generation status |
| `config` | View/edit Odoo settings |

---

## Testing

### Orchestrator Tests (Node.js)

```bash
cd orchestrator/
npm test                    # 747 tests
npm run test:coverage       # With coverage (80%+ required)
```

### Pipeline Tests (Python)

```bash
cd pipeline/python/

# All unit tests (~2284 tests, ~27s)
uv run pytest tests/ -v

# Skip Docker tests
uv run pytest tests/ -m "not docker" -v

# Skip E2E tests (require GITHUB_TOKEN)
uv run pytest tests/ -m "not e2e" -v

# Golden path E2E (render + Docker install + test)
uv run pytest tests/test_golden_path.py -v

# Integration E2E (full schema alignment verification)
uv run pytest tests/test_integration_e2e.py -v

# Coverage report
uv run pytest tests/ --cov=odoo_gen_utils --cov-report=html
```

**Test Markers:**
- `@pytest.mark.docker` — Requires Docker daemon
- `@pytest.mark.e2e` — Requires `GITHUB_TOKEN`
- `@pytest.mark.e2e_slow` — Full OCA index build (200+ repos, 3-5 min)

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ODOO_GEN_PATH` | No | Config file | Path to pipeline directory |
| `GITHUB_TOKEN` | No | — | GitHub API for OCA search (10 req/min) |
| `CONTEXT7_API_KEY` | No | — | Context7 API for live Odoo docs |
| `ODOO_VERSION` | No | `17.0` | Target Odoo version |
| `ODOO_DEV_PORT` | No | `8069` | Dev instance port |

---

## Dev Instance

A persistent Odoo 17 CE development instance for testing:

```bash
cd pipeline/

# Start Odoo 17 + PostgreSQL 16
scripts/odoo-dev.sh start

# Access at http://localhost:8069
# Credentials: admin / admin

# Stop (data preserved)
scripts/odoo-dev.sh stop

# Reset (destroys all data)
scripts/odoo-dev.sh reset
```

Pre-installed modules: `base`, `mail`, `sale`, `purchase`, `hr`, `account`.

---

## Knowledge Base

13 domain files with 80+ WRONG/CORRECT example pairs that prevent AI hallucinations:

```
pipeline/knowledge/
+-- MASTER.md        # Integration guide
+-- models.md        # ORM fields, computed, constraints
+-- views.md         # Forms, trees, kanban, search
+-- security.md      # ACLs, record rules, groups
+-- manifest.md      # __manifest__.py patterns
+-- inheritance.md   # Model/view inheritance
+-- testing.md       # Test assertions, mocking
+-- i18n.md          # Translation extraction
+-- wizards.md       # Transient models
+-- controllers.md   # HTTP controllers
+-- actions.md       # Window actions
+-- data.md          # XML/CSV data files
+-- custom/          # Your own knowledge (auto-included)
```

Extend the knowledge base by adding `.md` files to `knowledge/custom/`.

---

## Project Stats

| Metric | Value |
|--------|-------|
| Total Tests | **3,027** (747 orchestrator + 2,284 pipeline) |
| Python LOC | **23,500+** |
| CJS Modules | **43** |
| Jinja2 Templates | **24** (17.0 / 18.0 / shared) |
| AI Agents | **28** (20 orchestrator + 8 pipeline) |
| Slash Commands | **43** (30 orchestrator + 13 pipeline) |
| Knowledge Files | **13** (80+ example pairs) |
| Milestones Shipped | **6** (v1.0 through v3.0) |
| Commits | **325+** |

---

## Roadmap

- [x] Module decomposition and dependency ordering
- [x] Cross-module model registry with coherence checking
- [x] Single-module generation belt (8 agents, 24 templates)
- [x] Docker-based validation pipeline
- [x] Semantic search across 200+ OCA repositories
- [x] Auto-fix pipeline (imports, mail.thread, ACLs, XML)
- [x] Belt integration (orchestrator calls pipeline)
- [x] E2E integration tests (schema alignment verification)
- [ ] Enterprise edition templates
- [ ] Multi-company module generation
- [ ] RL-based agent optimization (Agent Lightning)
- [ ] Knowledge graph pipeline (Cognee-inspired)

---

## Contributing

See [pipeline/CONTRIBUTING.md](pipeline/CONTRIBUTING.md) for development setup, coding standards, and contribution guidelines.

### Key Rules

1. **Sequential generation** — one module at a time through the belt
2. **Atomic writes** — write complete JSON files, never partial updates
3. **Immutable data** — create new objects, never mutate existing
4. **Zero runtime deps** — orchestrator uses only Node.js built-ins
5. **80%+ test coverage** — enforced on both components

---

## License

- **Orchestrator**: MIT
- **Pipeline**: LGPL-3.0

---

<p align="center">
  Built with AI-assisted development using <a href="https://claude.ai/code">Claude Code</a>
</p>
