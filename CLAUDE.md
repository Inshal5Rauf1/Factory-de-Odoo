## Compact Instructions

Your context window will be automatically compacted as it approaches its limit,
allowing you to continue working indefinitely from where you left off.
Therefore, do not stop tasks early due to token budget concerns.
As you approach your token budget limit, save your current progress and state
to memory before the context window refreshes. Always be as persistent and
autonomous as possible and complete tasks fully, even if the end of your budget
is approaching. Never artificially stop any task early regardless of context remaining.

Auto-compact triggers at ~95% capacity. Manual `/compact` at logical breakpoints
is preferred to prevent mid-task disruption.

---

## Factory de Odoo

### Project
- **Repo:** https://github.com/Inshal5Rauf1/Factory-de-Odoo
- **Purpose:** PRD-to-ERP pipeline for generating 90+ Odoo modules
- **Branch:** `factory-upgrades` (based off `main`)
- **Guide:** `FACTORY-UPGRADE-BUILD-GUIDE.md` — master implementation spec

### Architecture
```
orchestrator/          — JS: state, phases, agents, dependency graph, coherence
pipeline/              — Python: Jinja2 templates, pylint-odoo, Docker validation, MCP
```

### Key Paths
| Component | Path |
|-----------|------|
| Orchestrator lib | `orchestrator/odoo-gsd/bin/lib/` |
| Orchestrator tests | `orchestrator/tests/` |
| Commands | `orchestrator/commands/odoo-gsd/` |
| Workflows | `orchestrator/odoo-gsd/workflows/` |
| Python src | `pipeline/python/src/odoo_gen_utils/` |
| Templates 17.0 | `pipeline/python/src/odoo_gen_utils/templates/17.0/` |
| Templates 18.0 | `pipeline/python/src/odoo_gen_utils/templates/18.0/` |
| Templates 19.0 | `pipeline/python/src/odoo_gen_utils/templates/19.0/` |
| Templates shared | `pipeline/python/src/odoo_gen_utils/templates/shared/` |
| Auto-fix | `pipeline/python/src/odoo_gen_utils/auto_fix.py` |
| MCP server | `pipeline/python/src/odoo_gen_utils/mcp/server.py` |
| Renderer context | `pipeline/python/src/odoo_gen_utils/renderer_context.py` |

### Current State (factory-upgrades branch)
All 8 fixes committed. All 8 gaps implemented. Ralph Loop docs complete.
- 797 orchestrator tests passing, 94 pipeline tests passing
- Ready to commit and merge to main

### Odoo Patterns
- `self.env._()` not standalone `_()` in model methods (W8161)
- Manifest load order: security → data → wizard views → model views → dashboard → menu
- Chatter uses `{% if chatter %}` flag, not `'mail' in depends`
- Python 3.12 (works across Odoo 17.0-19.0)
