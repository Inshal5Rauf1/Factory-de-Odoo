# Contributing to Odoo Module Automation

Thank you for your interest in contributing! This guide covers development setup, coding standards, and how to submit contributions.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Architecture](#project-architecture)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Contributing Code](#contributing-code)
- [Contributing Knowledge](#contributing-knowledge)
- [Contributing Agents](#contributing-agents)
- [Contributing Templates](#contributing-templates)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)

## Development Setup

### Prerequisites

- **Python 3.12** (not 3.13+ — Odoo 17 compatibility)
- **[uv](https://docs.astral.sh/uv/)** package manager
- **Docker** (for validation tests)
- **Git**
- **Amil** orchestrator installed (for full integration testing)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/TIFAQM/Factory-de-Odoo.git
cd Factory-de-Odoo

# Create virtual environment and install dependencies
cd python
uv venv --python 3.12
uv pip install -e ".[test,search]"

# Verify installation
uv run amil-utils --version
# → amil-utils, version 0.1.0

# Run tests
uv run pytest tests/ -v
# → ~2,900 passed
```

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GITHUB_TOKEN` | For search features | GitHub API access for OCA repository search |
| `ODOO_VERSION` | No | Override default Odoo version (19.0) |

### Docker Setup

Docker is required for module validation tests:

```bash
# Verify Docker is available
docker compose version

# The project includes a Docker Compose file for Odoo 19 + PostgreSQL 16
cat docker/dev/docker-compose.yml
```

## Project Architecture

```
Layer 1: Amil Orchestration    ← Inherited, don't modify
Layer 2: Odoo Extension       ← agents/, commands/, knowledge/, workflows/
Layer 3: Python Utilities     ← python/src/amil_utils/
Layer 4: AI Assistant         ← User's environment
```

### Key Modules

| Module | Responsibility | Key Functions |
|--------|---------------|---------------|
| `cli.py` | Click CLI commands | `main()`, `render()`, `validate()` |
| `renderer.py` | Jinja2 template rendering | `render_module()`, `create_versioned_renderer()` |
| `auto_fix.py` | Automated code fixing | `run_pylint_fix_loop()`, `run_docker_fix_loop()` |
| `validation/docker_runner.py` | Docker orchestration | `docker_install_module()`, `docker_run_tests()` |
| `validation/pylint_runner.py` | pylint-odoo linting | `run_pylint_odoo()` |
| `i18n_extractor.py` | Translation extraction | `extract_translatable_strings()`, `generate_pot()` |
| `search/index.py` | ChromaDB indexing | `build_oca_index()` |
| `search/query.py` | Semantic search | `search_modules()` |
| `search/fork.py` | Module forking | `clone_oca_module()` |

### Data Flow

```
Natural Language Input
  → Spec Parser (structured JSON)
  → Semantic Search (ChromaDB)
  → Template Renderer (Jinja2)
  → Validation (pylint + Docker)
  → Auto-Fix Loop
  → Output Module
```

## Coding Standards

### Python Style

- **Python 3.12** — use modern syntax (match/case, type unions with `|`)
- **Ruff** for linting and formatting (line length: 120)
- **Type hints** on all public functions
- **Docstrings** on public classes and functions

### Immutability

Always create new objects; never mutate in place:

```python
# WRONG
def update_spec(spec, key, value):
    spec[key] = value  # Mutation!
    return spec

# CORRECT
def update_spec(spec, key, value):
    return {**spec, key: value}  # New dict
```

### File Organization

- **200-400 lines typical**, 800 max per file
- One class per file when possible
- Group by feature/domain, not by type

### Error Handling

```python
# Always handle errors explicitly
try:
    result = docker_install_module(module_path)
except DockerError as e:
    logger.error("Docker install failed: %s", e)
    raise ValidationError(f"Module failed to install: {e}") from e
```

### Auto-Fix Pattern

All auto-fix functions follow the immutable read-transform-write pattern:

```python
def fix_something(file_path: Path) -> bool:
    """Fix X in the given file. Returns True if changes were made."""
    content = file_path.read_text()
    new_content = transform(content)  # Pure transformation
    if new_content == content:
        return False  # No changes needed
    file_path.write_text(new_content)
    return True
```

## Testing

### Test-Driven Development (Required)

All contributions must follow TDD:

1. **RED** — Write a failing test first
2. **GREEN** — Write minimal code to pass
3. **REFACTOR** — Clean up while tests pass
4. **COVERAGE** — Maintain 80%+ coverage

### Running Tests

```bash
cd python

# All tests
uv run pytest tests/ -v

# Unit tests only (no Docker, no GitHub)
uv run pytest tests/ -m "not docker and not e2e" -v

# With coverage report
uv run pytest tests/ --cov=amil_utils --cov-report=term-missing

# Single test file
uv run pytest tests/test_renderer.py -v

# Single test function
uv run pytest tests/test_renderer.py::TestRenderModule::test_mail_thread_inherit -v
```

### Test Markers

| Marker | When to Use | Skip Command |
|--------|-------------|-------------|
| `@pytest.mark.e2e` | Tests requiring GitHub API | `-m "not e2e"` |
| `@pytest.mark.e2e_slow` | Full OCA index build (3-5 min) | `-m "not e2e_slow"` |
| `@pytest.mark.docker` | Tests requiring Docker daemon | `-m "not docker"` |

### Writing Tests

```python
import pytest
from pathlib import Path
from amil_utils.renderer import render_module

class TestMyFeature:
    """Tests for the new feature."""

    def test_basic_behavior(self, tmp_path: Path):
        """Descriptive test name explaining what is being tested."""
        # Arrange
        spec = {"name": "test_module", "depends": ["base"]}

        # Act
        result = render_module(spec, template_dir, tmp_path)

        # Assert
        assert (result / "__manifest__.py").exists()
        assert "test_module" in (result / "__manifest__.py").read_text()

    def test_edge_case(self):
        """Test edge case with empty input."""
        with pytest.raises(ValueError, match="spec cannot be empty"):
            render_module({}, template_dir, tmp_path)
```

### Golden Path Test

The golden path test (`test_golden_path.py`) is the primary regression guard. It renders a realistic module spec, Docker-installs it, and runs its tests. If you modify templates or rendering logic, this test must still pass:

```bash
# Run golden path (requires Docker)
uv run pytest tests/test_golden_path.py -v
```

## Contributing Code

### Adding a New CLI Command

1. Add the Click command in `python/src/amil_utils/cli.py`
2. Write tests in `python/tests/test_cli_*.py`
3. Create the Amil command definition in `commands/your_command.md`

### Adding a New Auto-Fix

1. Add the fix function in `python/src/amil_utils/auto_fix.py`
2. Follow the read-transform-write pattern (see [Auto-Fix Pattern](#auto-fix-pattern))
3. Wire into `run_pylint_fix_loop()` or `run_docker_fix_loop()` as appropriate
4. Add tests in `python/tests/test_auto_fix.py`
5. Update the dispatch dict in the relevant fix loop

### Adding a New Template

1. Create the Jinja2 template in `python/src/amil_utils/templates/`
   - `shared/` for version-independent templates
   - `17.0/` or `18.0/` for version-specific templates
2. Wire into `renderer.py` if needed
3. Add rendering tests in `tests/test_renderer.py`
4. Verify the golden path test still passes

### Adding a New Validation Check

1. Add the check function in `python/src/amil_utils/validation/`
2. Wire into the validation pipeline in `cli.py`
3. Add error patterns in `error_patterns.py` if needed
4. Write tests

## Contributing Knowledge

The knowledge base is the most impactful place to contribute. Each knowledge file uses a structured format:

### File Structure

```markdown
# Topic Name

## Overview
Brief description of the Odoo concept.

## Rules

### Rule 1: Descriptive Name

## WRONG
```python
# Anti-pattern with explanation
incorrect_code_here()
```

## CORRECT
```python
# Best practice with explanation
correct_code_here()
```

## Why
Explanation of why the correct pattern matters.
```

### Adding Custom Knowledge

Add files to `knowledge/custom/` — they are automatically included in agent context:

```bash
# Create a custom knowledge file
cat > knowledge/custom/my_pattern.md << 'EOF'
# Custom Pattern: Inventory Valuation

## Rules

### Rule 1: Always use FIFO for inventory valuation
...
EOF
```

### Knowledge File Guidelines

- Use WRONG/CORRECT example pairs (agents learn from contrast)
- Include Odoo version specifics (17.0 vs 18.0 differences)
- Reference official Odoo documentation where applicable
- Keep examples minimal but complete (runnable snippets)
- One concept per section; avoid mixing unrelated topics

## Contributing Agents

Agents are markdown files that define specialized AI behaviors:

### Agent File Structure

```markdown
# Agent Name

## Role
One-sentence description of what this agent does.

## Knowledge
@knowledge/models.md
@knowledge/views.md

## Instructions
Step-by-step instructions for the agent.

## Examples
Input/output examples showing expected behavior.
```

### Guidelines

- Each agent should have a single, focused responsibility
- Reference relevant knowledge files with `@knowledge/` includes
- Include concrete examples of expected input and output
- Test by invoking through your AI coding assistant

## Contributing Templates

### Jinja2 Template Guidelines

- Use version-specific directories (`17.0/`, `18.0/`) for version-dependent code
- Use `shared/` for templates that work across versions
- The `FileSystemLoader` fallback means shared templates are used when version-specific ones don't exist
- Available Jinja2 filters: `model_ref`, `to_class`, `to_python_var`, `to_xml_id`

### Template Variables

Templates receive context variables from `renderer.py:_build_model_context()`:

| Variable | Type | Description |
|----------|------|-------------|
| `name` | str | Module technical name |
| `model_name` | str | Model technical name |
| `inherit_list` | list | Inheritance chain (e.g., `['mail.thread']`) |
| `needs_api` | bool | Whether to import `api` from odoo |
| `fields` | list | Model field definitions |
| `depends` | list | Module dependencies |

## Commit Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

<optional body>
```

**Types:**
- `feat` — New feature
- `fix` — Bug fix
- `test` — Adding/updating tests
- `docs` — Documentation changes
- `refactor` — Code restructuring (no behavior change)
- `chore` — Maintenance tasks
- `perf` — Performance improvements

**Examples:**
```
feat: add auto-fix for missing mail.thread inheritance
fix: conditional api import in 18.0 templates
test: add golden path E2E regression test
docs: update knowledge base with mail.thread rules
```

## Pull Request Process

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
3. **Write tests first** (TDD) — ensure they fail before implementing
4. **Implement** the minimal code to pass tests
5. **Run the full test suite:**
   ```bash
   cd python && uv run pytest tests/ -v
   ```
6. **Verify golden path** (if templates/rendering changed):
   ```bash
   uv run pytest tests/test_golden_path.py -v
   ```
7. **Commit** with conventional commit messages
8. **Push** and create a Pull Request against `main`

### PR Checklist

- [ ] Tests written first (TDD)
- [ ] All tests pass (`uv run pytest tests/ -v`)
- [ ] Golden path test passes (if templates changed)
- [ ] No hardcoded secrets or API keys
- [ ] Type hints on public functions
- [ ] Code follows immutability patterns
- [ ] Commit messages follow conventional commits
- [ ] Knowledge base updated (if adding Odoo patterns)

### What We Look For

- **Correctness** — Does it work with real Odoo 17.0/18.0?
- **Test coverage** — 80%+ with meaningful assertions
- **OCA compliance** — Does generated code pass pylint-odoo?
- **Immutability** — No mutation of shared state
- **Simplicity** — Minimal code to solve the problem

## Questions?

Open an issue on [GitHub](https://github.com/TIFAQM/Factory-de-Odoo/issues) or reach out through the repository discussions.
