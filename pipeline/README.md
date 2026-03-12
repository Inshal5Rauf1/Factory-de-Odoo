# Odoo Module Automation

An AI-powered system that automates Odoo 17.0, 18.0, and 19.0 module development end-to-end. Describe a business need in natural language, and the system produces OCA-grade Odoo modules — complete with models, views, security, tests, and i18n.

## How It Works

```
You: "I need a module to track employee training courses and sessions"
                    |
        +-----------v-----------+
        |  Semantic Search OCA  |  Search 200+ OCA repos for similar modules
        +-----------+-----------+
                    |
          Match found?  No match?
              |              |
     Fork & Extend     Build from Scratch
              |              |
        +-----v--------------v-----+
        |   8 Specialized Agents   |  Model, View, Security, Test, i18n...
        +-----+--------------------+
              |
        +-----v--------------------+
        |   Jinja2 Template Engine |  24 templates (17.0 / 18.0 / shared)
        +-----+--------------------+
              |
        +-----v--------------------+
        |   Validation Pipeline    |  pylint-odoo + Docker install + test
        +-----+--------------------+
              |
        +-----v--------------------+
        |   Auto-Fix Loops         |  Fix imports, add mail.thread, etc.
        +--------------------------+
              |
           Module
```

## Features

- **Natural Language to Module** — Describe what you need; the system asks follow-up questions, generates a structured spec, and produces a complete Odoo module
- **Semantic Search** — ChromaDB-powered vector search across 200+ OCA repositories to find and fork existing modules
- **8 Specialized AI Agents** — Model generation, view generation, security patterns, test generation, validation, search, scaffolding, fork-and-extend
- **24 Jinja2 Templates** — Version-aware templates for Odoo 17.0, 18.0, and 19.0 with shared fallback
- **Validation Pipeline** — pylint-odoo linting + Docker-based Odoo installation + test execution
- **Auto-Fix** — Automatically fixes pylint violations, missing `mail.thread` inheritance, unused imports (AST-based), XML parse errors, missing ACLs, manifest load order — with configurable 5-iteration caps
- **Knowledge Base** — 13 domain files with 80+ WRONG/CORRECT example pairs preventing AI hallucinations
- **Context7 Integration** — Live Odoo documentation queries via Context7 REST API with graceful fallback
- **Artifact State Tracking** — Generation pipeline observability with JSON sidecar persistence and CLI display
- **MCP Server** — 6 tools for live Odoo introspection (list_models, get_model_fields, check_module_dependency, etc.)
- **Human Review** — 3 checkpoint-based review gates before code generation
- **Edition Support** — Community and Enterprise, Odoo 19.0 (primary), 18.0, and 17.0

## Prerequisites

- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **Python 3.12** (Odoo 17.0-19.0 supports 3.10-3.12; 3.13+ breaks validation)
- **Docker + Docker Compose v2** (for module validation and dev instance)
- **GitHub Token** (optional, for OCA search: `export GITHUB_TOKEN=...`)
- An AI coding assistant: [Claude Code](https://claude.ai/code), Gemini, Codex, or OpenCode

## Installation

```bash
# Clone the repository
git clone git@github.com:Inshal5Rauf1/Odoo-Development-Automation.git ~/.claude/amil

# Run the installer
cd ~/.claude/amil
bash install.sh
```

The installer:
1. Verifies Python 3.12 is available
2. Creates a Python virtual environment with `uv`
3. Installs the `amil-utils` package (editable)
4. Registers 13 commands as `/amil:*` in your AI assistant
5. Symlinks 8 agent definitions
6. Installs the knowledge base
7. Writes an installation manifest at `~/.claude/amil-manifest.json`

## Quick Start

All commands are invoked through your AI coding assistant using the `/amil:` prefix.

### Create a New Module

```
/amil:new
> "I need a module to manage employee training courses with sessions,
>  attendance tracking, and completion certificates"
```

The system will:
1. Ask Odoo-specific follow-up questions (dependencies, field types, etc.)
2. Parse your input into a structured JSON specification
3. Present the spec for your review (checkpoint 1)
4. Search OCA for similar modules
5. Generate the complete module (checkpoint 2)
6. Validate with pylint-odoo and Docker (checkpoint 3)

### Validate an Existing Module

```
/amil:validate my_module --auto-fix
```

Runs the full validation pipeline:
- pylint-odoo linting (with auto-fix for common violations)
- Docker installation test (Odoo 19.0 + PostgreSQL 16)
- Docker test execution
- Auto-fix for structural issues (missing `mail.thread`, unused imports)

### Search for Existing Modules

```
/amil:search "inventory barcode scanning"
```

Semantic search across 200+ OCA repositories using ChromaDB vector embeddings.

### Fork and Extend a Module

```
/amil:extend OCA/stock-logistics-workflow
```

Clones an OCA module and sets up a companion `_ext` module for customization.

## Commands

| Command | Description |
|---------|-------------|
| `/amil:new` | Scaffold a new module from natural language |
| `/amil:validate` | Run pylint-odoo + Docker validation |
| `/amil:search` | Semantic search OCA for similar modules |
| `/amil:extend` | Fork and extend an existing module |
| `/amil:plan` | Plan module architecture before generation |
| `/amil:research` | Research Odoo patterns and solutions |
| `/amil:index` | Build/update ChromaDB index of OCA modules |
| `/amil:phases` | Show generation phases and progress |
| `/amil:status` | Show current module generation status |
| `/amil:resume` | Resume interrupted module generation |
| `/amil:config` | View/edit Odoo-specific settings |
| `/amil:history` | Show generation history |
| `/amil:help` | Show available commands and usage |

### Observability Commands

| Command | Description |
|---------|-------------|
| `amil-utils show-state ./module` | Show artifact generation state with status icons |
| `amil-utils context7-status` | Check Context7 API configuration and Odoo library resolution |

## Architecture

```
Layer 1: Orchestrator (Factory de Odoo)
  Context management, state persistence, cross-module coherence,
  phase/wave execution, checkpoint-based human review, Git integration

Layer 2: Pipeline (THIS COMPONENT)
  8 specialized agents, 13 commands, Jinja2 templates,
  knowledge base, workflows

Layer 3: Python Utilities (amil-utils)
  Jinja2 rendering engine, pylint-odoo integration,
  Docker validation, ChromaDB search, auto-fix pipeline

Layer 4: AI Coding Assistant (USER'S ENVIRONMENT)
  Claude Code, Gemini, Codex, OpenCode — orchestrator + pipeline installed
```

## Project Structure

```
amil/
├── install.sh              # 10-step installer
├── defaults.json           # Default config (Odoo 17.0, Community, LGPL-3)
├── agents/                 # 8 AI agent definitions
│   ├── amil-scaffold.md
│   ├── amil-model-gen.md
│   ├── amil-view-gen.md
│   ├── amil-test-gen.md
│   ├── amil-security-gen.md
│   ├── amil-validator.md
│   ├── amil-search.md
│   └── amil-extend.md
├── commands/               # 13 command definitions
├── knowledge/              # Odoo domain knowledge base
│   ├── MASTER.md           # Integration guide
│   ├── models.md           # ORM models, fields, computed
│   ├── views.md            # Forms, trees, kanban, search
│   ├── security.md         # ACLs, record rules, groups
│   ├── manifest.md         # __manifest__.py structure
│   ├── inheritance.md      # Model/view inheritance
│   ├── testing.md          # Test structure, assertions
│   ├── i18n.md             # Translation strings
│   ├── wizards.md          # Transient models
│   ├── controllers.md      # HTTP controllers
│   ├── actions.md          # Action windows
│   ├── data.md             # XML/CSV data files
│   └── custom/             # User-extensible knowledge
├── templates/              # Jinja2 templates
│   ├── 17.0/               # Odoo 17 specific
│   ├── 18.0/               # Odoo 18 specific
│   ├── 19.0/               # Odoo 19 specific
│   └── shared/             # Common (fallback)
├── workflows/              # Workflow configs
├── docker/                 # Docker Compose (Odoo 19 + PostgreSQL 16)
│   └── docker-compose.yml
└── python/                 # Python package
    ├── pyproject.toml
    ├── src/amil_utils/
    │   ├── cli.py          # Click CLI entry point
    │   ├── renderer.py     # Jinja2 rendering engine
    │   ├── auto_fix.py     # pylint + Docker fix loops
    │   ├── i18n_extractor.py
    │   ├── edition.py
    │   ├── kb_validator.py
    │   ├── search/         # ChromaDB, GitHub, fork
    │   └── validation/     # Docker, pylint, reports
    └── tests/              # 444 tests (pytest)
```

## Python Utilities (amil-utils)

The `amil-utils` CLI provides the underlying Python tooling:

```bash
# Render a single template
amil-utils render --template model.py.j2 --var name=hr_training

# List available templates
amil-utils list-templates --version 17.0

# Validate a module
amil-utils validate /path/to/module --auto-fix

# Build search index
amil-utils build-index

# Search modules
amil-utils search-modules "inventory management"

# Extract translations
amil-utils extract-i18n /path/to/module
```

## Testing

```bash
cd python/

# Run all unit tests (494 tests, ~3s)
uv run pytest tests/ -v

# Skip Docker tests (when Docker unavailable)
uv run pytest tests/ -m "not docker" -v

# Skip E2E tests (require GitHub token)
uv run pytest tests/ -m "not e2e" -v

# Run with coverage
uv run pytest tests/ --cov=amil_utils --cov-report=html

# Run golden path E2E (render + Docker install + test)
uv run pytest tests/test_golden_path.py -v
```

**Test markers:**
- `@pytest.mark.e2e` — Requires `GITHUB_TOKEN` environment variable
- `@pytest.mark.e2e_slow` — Full OCA index build (200+ repos, 3-5 min)
- `@pytest.mark.docker` — Requires Docker daemon running

## Dev Instance

A persistent Odoo 19 CE development instance is available for local development and MCP server integration. It runs separately from the ephemeral validation Docker setup.

### Prerequisites

- **Docker** and **Docker Compose v2** (`docker compose` subcommand, not standalone `docker-compose`) are required. See [Docker installation docs](https://docs.docker.com/get-docker/).

### Quick Start

```bash
# Start the Odoo 19 CE dev instance
scripts/odoo-dev.sh start

# Stop the instance (data is preserved)
scripts/odoo-dev.sh stop

# View logs
scripts/odoo-dev.sh logs

# Check status and XML-RPC connectivity
scripts/odoo-dev.sh status

# Reset (destroys all data)
scripts/odoo-dev.sh reset
```

### Access

| Property | Value |
|----------|-------|
| URL | `http://localhost:8069` |
| Database | `odoo_dev` |
| Username | `admin` |
| Password | `admin` |

The port is configurable via the `ODOO_DEV_PORT` environment variable.

### Verify Connectivity

Run the XML-RPC smoke test to verify the instance is running and accessible:

```bash
scripts/verify-odoo-dev.py
```

This performs XML-RPC authentication against the dev instance and checks that all required modules are installed.

### Pre-installed Modules

The following modules are automatically installed on first start:

- `base` -- Core framework
- `mail` -- Messaging and activity tracking
- `sale` -- Sales management
- `purchase` -- Purchase management
- `hr` -- Human resources
- `account` -- Accounting and invoicing

## Configuration

Default settings in `defaults.json`:

```json
{
  "odoo": {
    "odoo_version": "19.0",
    "edition": "community",
    "license": "LGPL-3",
    "output_dir": "."
  }
}
```

Override via `/amil:config` or environment variables:
- `GITHUB_TOKEN` — GitHub API access for OCA search
- `ODOO_VERSION` — Target Odoo version (17.0, 18.0, or 19.0)
- `CONTEXT7_API_KEY` — Context7 API key for live Odoo documentation queries (optional)

## Knowledge Base

The knowledge base contains 13 domain files covering Odoo development patterns. Each file uses WRONG/CORRECT example pairs to guide AI agents:

```markdown
## WRONG
fields.Char('Name')  # Positional string deprecated in Odoo 17

## CORRECT
fields.Char(string='Name')  # Named parameter required
```

Extend the knowledge base by adding files to `knowledge/custom/`. These are automatically included in agent context.

## Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.0 | MVP | 1-9 | Shipped 2026-03-03 |
| v1.1 | Tech Debt Cleanup | 10-11 | Shipped 2026-03-03 |
| v1.2 | Template Quality | 12-14 | Shipped 2026-03-04 |
| v2.0 | Environment-Aware Generation | 15-17 | Shipped 2026-03-04 |
| v2.1 | Auto-Fix & Enhancements | 18-19 | Shipped 2026-03-04 |
| v3.0 | Bug Fixes & Tech Debt | 20-25 | Shipped 2026-03-05 |

**Stats:** 25 phases, 56 plans, 325+ commits, 18,400 LOC Python, 494 tests

## License

LGPL-3.0

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and contribution guidelines.
