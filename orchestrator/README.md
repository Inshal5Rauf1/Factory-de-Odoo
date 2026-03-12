# amil

**Odoo ERP Module Orchestrator** — A Claude Code extension that decomposes a university ERP PRD into 20+ modules and drives the [amil](https://github.com/Inshal5Rauf1/Odoo-Development-Automation) belt to generate them sequentially with cross-module coherence.

## Architecture

```
amil (this repo)
  │  Orchestrates module decomposition, dependency ordering,
  │  cross-module state (model registry), human checkpoints
  │
  └── amil (separate repo — single-module generation pipeline)
        │  8 agents, 13 knowledge files, Jinja2 templates, Docker validation
        │
        └── amil-utils (Python CLI)
              AST analysis, ChromaDB search, MCP server, Docker ops
```

## Core Value

**Cross-module coherence**: every generated Odoo module is referentially consistent with all other modules in the project (model references, security rules, menu hierarchies, view inheritance).

## Module Lifecycle

```
planned → spec_approved → generated → checked → shipped
```

Modules progress through these states sequentially. Only one module generates at a time (the amil belt needs exclusive Docker access).

## Commands

| Command | Purpose |
|---------|---------|
| `/amil:new-erp` | Initialize ERP project, decompose PRD into modules |
| `/amil:discuss-module` | Module-specific implementation Q&A |
| `/amil:plan-module` | Generate spec.json, run coherence check |
| `/amil:generate-module` | Invoke belt, update registry |
| `/amil:progress` | Module status + registry stats |
| `/amil:help` | Show all available commands |

## Key Components

### Model Registry (`model_registry.json`)
Central cross-module state tracking all models/fields across all generated modules. Atomic writes with rollback support, versioning, and tiered injection (full/field-list/names-only based on dependency distance).

### Coherence Checker (`coherence.cjs`)
4 deterministic structural checks against spec.json + registry:
- Many2one target validation
- Duplicate model detection
- Computed field dependency resolution
- Security group verification

### Module Decomposition
4 parallel research agents analyze the PRD:
1. **Module Boundary Analyzer** — functional domains, model proposals
2. **OCA Registry Checker** — build/extend/skip recommendations
3. **Dependency Mapper** — cross-domain references, circular risk detection
4. **Computation Chain Identifier** — data flow chains across models

### Question Templates
9 domain-specific + 1 generic question template for interactive module discussions (fee, exam, student, faculty, HR, timetable, notification, portal, core).

## v1.0 Progress

| Phase | Status | What it delivers |
|-------|--------|-----------------|
| 1. Fork Foundation | ✓ Complete | CLI rename, registry CRUD, status tracking, dependency graph |
| 2. PRD Decomposition | ✓ Complete | new-erp command, 4 research agents, module decomposition |
| 3. Module Discussion | ✓ Complete | discuss-module command, question templates, questioner agent |
| 4. Spec Generation | ✓ Complete | plan-module command, coherence checker, spec generator |
| 5. Belt Integration | Pending | generate-module command, belt invocation, progress dashboard |

**Tests:** 743 passing, 0 failures

## State Files

| File | Purpose |
|------|---------|
| `config.json` | Profile, workflow toggles, Odoo config block |
| `STATE.md` | Current position, decisions, blockers |
| `ROADMAP.md` | Phase definitions, plan progress |
| `model_registry.json` | Central registry of all Odoo models across modules |
| `module_status.json` | Per-module lifecycle state tracking |

## Development

```bash
npm test                    # Run all tests (743 tests)
npm run test:coverage       # Run with coverage (80%+ required)
```

### Rules

1. **Sequential generation only** — one module at a time through the belt
2. **All state changes through CLI subcommands** — never edit state files manually
3. **Atomic writes for JSON state** — write complete files, never partial updates
4. **CJS module format** — all lib modules use CommonJS
5. **Zero npm runtime dependencies** — only Node.js built-ins

## License

MIT
