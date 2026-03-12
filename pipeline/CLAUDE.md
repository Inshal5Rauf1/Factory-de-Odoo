# Odoo Module Automation

## Project Status
- Phase: Roadmap rebuilt — ready for `/odoo-gsd:plan-phase 1`
- Directory: /home/inshal-rauf/Factory-de-Odoo/pipeline
- Remote: https://github.com/Inshal5Rauf1/Factory-de-Odoo.git
- Architecture: **Pipeline component** of Factory de Odoo monorepo
- Roadmap: 9 phases, 68 Odoo-specific requirements

## Architecture

```
Layer 1: Orchestrator (Factory de Odoo)
  Context management, state, phases, agents, checkpoints, git

Layer 2: Pipeline (THIS COMPONENT)
  Agents, workflows, commands, templates, knowledge base

Layer 3: Python Utilities (odoo-gen-utils)
  Jinja2 rendering, pylint-odoo, Docker validation, ChromaDB search

Layer 4: AI Coding Assistant (USER'S ENVIRONMENT)
  Claude Code, Gemini, Codex, OpenCode — orchestrator + pipeline installed
```

## Key Decisions
| Decision | Rationale | Status |
|----------|-----------|--------|
| Monorepo component (not standalone CLI) | Orchestrator provides cross-module coherence, context, state management | Decided |
| Integrated with orchestrator | Single repo, shared state, coordinated generation | Decided |
| Clone-based install (~/.claude/) | Works with any AI coding assistant | Decided |
| Odoo 19.0 primary target | Latest stable, strong OCA support, backward compatible with 17.0/18.0 | Decided |
| Fork-and-extend strategy | Leverage existing OCA/GitHub modules as foundation | Decided |
| Semantic search (ChromaDB + sentence-transformers) | Intent-based matching, not just keywords | Decided |
| Python 3.12 for utilities | Odoo 17.0-19.0 supports 3.10-3.12; 3.13+ breaks validation | Decided |
| Checkpoint-based human review | Orchestrator provides mechanism; we wire Odoo checkpoints | Decided |
| OCA quality as the bar | pylint-odoo, i18n, full security, tests | Decided |
| Docker for validation | Only way to truly verify module installs and tests pass | Decided |
| UI UX Pro Max Skill pattern | Reasoning engine + hierarchical system + rule library for skill architecture | Decided |

## Prior Art
| Project | Role | Use |
|---------|------|-----|
| **Orchestrator** | BUILT | Full orchestration layer (formerly based on GSD, now standalone) |
| **erp_claude** | ADOPT KNOWLEDGE | Odoo 17 model/view skills → knowledge base |
| **UI UX Pro Max Skill** | ADOPT PATTERN | Reasoning engine, hierarchical system, rule library |
| **Ralph** | REFERENCE | Fresh context loop, confirms orchestration approach |
| **Cognee** | REFERENCE | Knowledge graph pipeline for KB design |
| **LangExtract** | REFERENCE | Source-grounded extraction for spec parsing |
| **Agent Lightning** | FUTURE | RL agent optimization → v2+ |
| **Gemini-Odoo-Module-Generator** | COMPETITOR | Baseline we must exceed |
| **Ruflo** | SKIP | Over-engineered (60+ agents, Byzantine consensus) |
| **LobeHub** | SKIP | Web chat platform, different product |

## Mistakes Log
<!-- Track mistakes made during development to avoid repeating them -->

1. **Built standalone CLI plans before confirming architecture** — Spent time planning Typer CLI, custom config, custom state management when the actual vision was an orchestrator-integrated pipeline. Wasted Phase 1 planning cycle. Lesson: confirm the product form factor FIRST.
2. **Assumed sentence-transformers was required for ChromaDB** — Included ~200MB sentence-transformers + torch as dependencies when ChromaDB ships its own 22MB ONNX embedding model. Discovered in Phase 10; removed both deps. Lesson: verify what a library actually uses before adding its transitive deps.
3. **Mocked Docker tests gave false confidence** — Original `test_docker_runner.py` mocked `_run_compose()` which hid two real bugs: (a) `exec` causes race condition with entrypoint server on same DB, and (b) log parser regex didn't match Odoo 17's actual test output format (`Starting ClassName.test_method ...` not `test_method ... ok`). Only discovered when Phase 11 added unmocked live Docker tests. Lesson: mocked tests validate logic, not integration — always add real integration tests for Docker/container workflows.
4. **Docker `exec` into running Odoo container causes serialization failures** — Two Odoo processes (entrypoint server + exec'd process) write to the same PostgreSQL database simultaneously, causing `psycopg2.errors.SerializationFailure`. Fix: use `docker compose run --rm` (fresh container, no entrypoint server) and `--test-tags` to filter only target module tests. Lesson: `exec` into a service container means TWO processes share the same DB.
5. **`--test-enable` runs ALL module tests, not just the target** — Without `--test-tags={module}`, Odoo runs tests for base + all dependencies (938 tests for a simple module). This takes 30+ seconds and is fragile. Lesson: always use `--test-tags` when running Odoo tests in Docker.
6. **Planner agent sometimes produces no output on first invocation** — During Phase 11 planning, the planner agent ran 29 tool uses (49k tokens) but created no PLAN.md files. Required resuming the agent. Lesson: always spot-check that plan files exist after planner returns; be prepared to resume.
7. **AskUserQuestion tool silently drops selections** — During Phase 11 discussion, multi-select questions returned empty answers (".") even though user made selections. Workaround: re-ask questions individually. Lesson: if AskUserQuestion returns empty, re-ask — don't assume user skipped.

## Lessons Learned

- Multi-agent systems fail 41-86.7% of the time in production, mostly from coordination issues
- Fork-and-extend becomes worse than scratch when >40% of module is modified
- Docker validation gives false confidence (tests run as admin, empty DB, missing cross-module interactions)
- GitHub code search API: 10 req/min, 1000 result cap — need local index strategy
- The orchestrator handles ~19% of requirements (orchestration, context, checkpoints, state)
- 81% of requirements are pure Odoo domain work — handled by the pipeline

## Commands

All commands are invoked as `/odoo-gen:<command>` through the AI coding assistant.

| Command | Description | Phase |
|---------|-------------|-------|
| `new` | Scaffold a new Odoo module from natural language description | 1 |
| `validate` | Run pylint-odoo + Docker validation on a module | 3 |
| `search` | Semantically search GitHub/OCA for similar modules | 8 |
| `research` | Research Odoo patterns and existing solutions for a need | 2 |
| `plan` | Plan module architecture before generation | 4 |
| `phases` | Show generation phases and progress for current module | 1 |
| `config` | View/edit Odoo-specific settings | 1 |
| `status` | Show current module generation status | 1 |
| `resume` | Resume interrupted module generation | 1 |
| `index` | Build/update local ChromaDB index of Odoo modules | 8 |
| `extend` | Fork and extend an existing module | 8 |
| `history` | Show generation history and past modules | 7 |
| `help` | Show available commands and usage | 1 |

**Wrapper commands** (`config`, `status`, `resume`): These provide Odoo-specific context on top of orchestrator equivalents. Users interact with `/odoo-gen:status` (not bare `/odoo-gsd:progress`), keeping the experience unified within the Odoo domain.

## Roadmap Overview
| # | Phase | Requirements |
|---|-------|-------------|
| 1 | Orchestrator Integration + Odoo Foundation | EXT-01..05 |
| 2 | Knowledge Base | KNOW-01..04 |
| 3 | Validation Infrastructure | QUAL-01..05, 07, 08 |
| 4 | Input & Specification | INPT-01..04 |
| 5 | Core Code Generation | CODG-01..10 |
| 6 | Security & Test Generation | SECG-01..05, TEST-01..06 |
| 7 | Human Review & Quality Loops | REVW-01..06, QUAL-06, 09, 10 |
| 8 | Search & Fork-Extend | SRCH, REFN, FORK (12 reqs) |
| 9 | Edition & Version Support | VERS-01..06 |

## File Structure
```
.planning/
├── PROJECT.md          # Project context (pipeline architecture)
├── config.json         # Workflow preferences
├── REQUIREMENTS.md     # 68 Odoo-specific requirements
├── ROADMAP.md          # 9-phase roadmap
├── STATE.md            # Project state tracking
├── research/
│   ├── STACK.md        # Technology recommendations
│   ├── FEATURES.md     # Feature landscape
│   ├── ARCHITECTURE.md # System architecture patterns
│   ├── PITFALLS.md     # Common mistakes to avoid
│   ├── SUMMARY.md      # Synthesized findings (updated with new repos)
│   └── PRIOR_ART.md    # Analysis of 7 additional repos
└── phases/
    └── 01-orchestrator-integration/  # Ready for planning
```

## Development Notes
- Git initialized locally, remote is empty
- Greenfield project — no existing code
- Config: interactive mode, comprehensive depth, parallel execution, quality model profile (Opus)
- gh CLI not authenticated — need `gh auth login` for GitHub API access
- Orchestrator must be installed before pipeline can be used for multi-module generation
- Old Phase 1 plans (standalone CLI) deleted — they were for wrong architecture

---
*Last updated: 2026-03-10 — removed GSD dependency references (orchestrator is standalone)*
