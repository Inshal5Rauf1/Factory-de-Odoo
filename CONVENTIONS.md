# Conventions

Naming and structure rules for Factory de Odoo. Follow these patterns for all new files.

## Directory Structure

Root-level directories mirror the `~/.claude/` install layout:

| Directory | Installed to | Purpose |
|-----------|-------------|---------|
| `agents/` | `~/.claude/agents/` | AI agent definitions (28 total) |
| `amil/` | `~/.claude/amil/` | Workflows, references, templates, knowledge |
| `commands/` | `~/.claude/commands/` | Slash commands (`/amil:*`) |
| `hooks/` | `~/.claude/hooks/` | Event hooks |
| `python/` | *(pip install)* | Python package — NOT installed to `~/.claude/` |

`python/` is the only root directory not copied by `install.py`.

## Naming Rules

| Category | Convention | Example |
|----------|-----------|---------|
| Python modules | `snake_case.py` | `dependency_graph.py` |
| Python classes | `PascalCase` | `GenerationManifest` |
| Python constants | `UPPER_SNAKE_CASE` | `FIXABLE_PYLINT_CODES` |
| Python packages | `snake_case/` | `logic_writer/` |
| Agent files | `amil-<purpose>.md` | `amil-scaffold.md` |
| Command files | `<command-name>.md` | `generate-module.md` |
| Workflow files | `<verb-noun>.md` | `execute-phase.md` |
| Document templates | `<purpose>.md` (lowercase) | `debug.md` |
| Jinja2 templates | `<artifact>.{ext}.j2` | `model.py.j2` |
| Knowledge files | `<topic>.md` (lowercase) | `models.md` |
| Hook files | `amil-<purpose>.py` | `amil-statusline.py` |
| Test files | `test_<module>.py` | `test_registry.py` |

## File Size Limits

| Artifact | Limit |
|----------|-------|
| Python files | 800 lines max, 200-400 typical |
| Functions | 50 lines max |
| Knowledge files | 500 lines max |
| Nesting depth | 4 levels max |

## Python Conventions

- **Immutability** — create new objects, never mutate existing
- **Atomic writes** — write complete JSON files, never partial updates
- **Error handling** — handle errors explicitly at every level
- **Input validation** — validate at system boundaries using Pydantic
- **No `console.log`** — use proper logging

## Test Conventions

- Tests mirror `src/` structure: `src/amil_utils/registry.py` → `tests/test_registry.py`
- Orchestrator tests in `tests/orchestrator/`
- Test fixtures in `tests/fixtures/`
- Markers: `@pytest.mark.docker`, `@pytest.mark.e2e`, `@pytest.mark.e2e_slow`

## Agent Conventions

- All agents prefixed with `amil-`
- Agents reference knowledge via `@~/.claude/amil/knowledge/<topic>.md`
- Orchestrator agents handle cross-module concerns (planning, verification, research)
- Pipeline agents handle single-module generation (scaffold, model, view, security, test)
