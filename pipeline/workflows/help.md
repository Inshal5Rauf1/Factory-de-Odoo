# Help Workflow

Help content for the `/amil:help` command. Lists all available commands with status and usage examples.

---

## Available Commands

| Command | Description | Status | Phase |
|---------|-------------|--------|-------|
| `/amil:new` | Scaffold a new Odoo module from a natural language description | Active | 1 |
| `/amil:help` | Show this help | Active | 1 |
| `/amil:config` | View or edit Odoo-specific configuration | Active | 1 |
| `/amil:status` | Show current module generation status | Active | 1 |
| `/amil:resume` | Resume an interrupted module generation | Active | 1 |
| `/amil:phases` | Show generation phases and progress | Active | 1 |
| `/amil:validate` | Run pylint-odoo and Docker-based module validation | Planned | 3 |
| `/amil:research` | Research Odoo patterns and existing solutions | Planned | 2 |
| `/amil:plan` | Plan module architecture before generation | Planned | 4 |
| `/amil:search` | Semantically search GitHub/OCA for existing modules | Planned | 8 |
| `/amil:extend` | Fork and extend an existing Odoo module | Planned | 8 |
| `/amil:history` | Show generation history and past modules | Planned | 7 |

**Status Legend:**
- **Active** -- Fully implemented and ready to use
- **Planned** -- Registered but not yet implemented (see Phase column)

## Usage Examples

### Scaffold a new module

```
/amil:new "inventory tracking with stock moves and warehouse locations"
```

The system will:
1. Parse your description to infer a module specification
2. Present the spec (module name, models, fields, dependencies) for your review
3. On confirmation, generate a complete Odoo 17.0 module with OCA structure

### View or edit configuration

```
/amil:config
/amil:config odoo_version 17.0
/amil:config license LGPL-3
/amil:config author "My Company"
```

### Check generation status

```
/amil:status
```

### Resume interrupted generation

```
/amil:resume
```

### Show generation phases

```
/amil:phases
```

## Architecture

amil is a **Amil extension**. It inherits orchestration, state management, checkpoints, and agent coordination from Amil. All Odoo-specific logic lives in `~/.claude/amil/`.

### Extension Structure

```
~/.claude/amil/
  install.sh          # Extension installer
  VERSION             # Version tracking
  defaults.json       # Odoo-specific configuration
  bin/
    amil-utils    # Python CLI wrapper
  agents/
    amil-scaffold.md  # Module scaffolding agent
    amil-model-gen.md # Model generation specialist (Phase 5)
    amil-view-gen.md  # View generation specialist (Phase 5)
    amil-security-gen.md  # Security generation specialist (Phase 6)
    amil-test-gen.md  # Test generation specialist (Phase 6)
    amil-validator.md # Validation agent (Phase 3)
  commands/
    new.md, help.md, config.md, status.md, resume.md, phases.md
    validate.md, search.md, research.md, plan.md, extend.md, history.md
  workflows/
    scaffold.md       # End-to-end scaffold workflow
    help.md           # This file
  python/
    src/amil_utils/  # Python utility package
      cli.py           # Click CLI entry point
      renderer.py      # Jinja2 rendering engine
      templates/       # 15 Odoo 17.0 Jinja2 templates
```

### Key Technologies

- **Python 3.12** with uv for package management
- **Jinja2** for template rendering
- **Click** for CLI interface
- **Odoo 17.0** as the primary target

For Amil commands, use `/amil:help`.
