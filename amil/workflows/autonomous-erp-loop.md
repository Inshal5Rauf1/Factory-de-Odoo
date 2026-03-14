# Ralph Loop — Autonomous ERP Generation

## Overview

Ralph Loop (`/ralph-loop`) feeds the SAME prompt to Claude repeatedly. Each
iteration reads file state, picks the next action from the priority table,
executes it, and loops. Context resets are handled via the compact summary
header in ERP_CYCLE_LOG.md.

## Prerequisites

- Ralph Loop Claude Code plugin installed from `https://github.com/frankbria/ralph-claude-code`
- `/ralph-loop` and `/cancel-ralph` slash commands available in Claude Code
- Persistent Docker instance running
- PRD decomposition completed (modules exist in module_status.json)

## The Prompt

```
/ralph-loop "
You are the Factory de Odoo orchestrator. Run /amil:run-prd to
execute the next iteration of the ERP generation cycle.

BEFORE EACH ITERATION:
1. Read .planning/ERP_CYCLE_LOG.md — ONLY the compact summary (first 15 lines)
2. Read .planning/module_status.json for current state
3. The run-prd workflow will select the right action automatically

RULES:
- Follow the priority table in the run-prd workflow
- NEVER skip human interaction points — wait for answers
- Log every action to the cycle log
- After every 10 modules shipped: trigger live UAT checkpoint
- If all modules shipped: output <promise>ERP COMPLETE</promise>
- If context resets: read ERP_CYCLE_LOG.md compact summary first — it has enough to resume
- If 3+ modules blocked in a row: STOP and ask human for guidance

COHERENCE:
- After every generation: run coherence check
- If forward reference found: check provisional registry
- If circular dep detected: follow circular-dep-breaker resolution

DOCKER: ensure factory Docker is running before first generation.
User verifies at http://localhost:8069 during live UAT checkpoints.
" --completion-promise "ERP COMPLETE" --max-iterations 500
```

## How It Works

1. Claude receives the prompt
2. Reads file state (module_status.json, ERP_CYCLE_LOG.md compact summary)
3. Picks the next action from the priority table
4. Executes it
5. Claude tries to exit -> stop hook re-feeds the prompt
6. Next iteration sees updated files

## Why Ralph Works Here

| Ralph Feature | How It Helps |
|--------------|-------------|
| Same prompt repeated | Each iteration reads file state — naturally picks up where last left off |
| Self-referential via files | module_status.json, cycle log, registries all persist between iterations |
| Completion promise | `<promise>ERP COMPLETE</promise>` when all modules shipped |
| Max iterations cap | Safety net — 500 iterations for 90+ modules |
| Stop hook intercept | Keeps the loop going without manual re-invocation |
| Human input pauses | Ralph naturally pauses when Claude asks a question |

## Context Reset Handling

At 90+ modules, context resets **will** happen frequently (every ~15-20
iterations). The compact summary header is the lifeline:

```
<!-- COMPACT-SUMMARY-START -->
## Quick Resume
- **Last Iteration:** 147
- **Shipped:** 52/92
- **In Progress:** 1
- **Blocked:** 3
- **Next Action:** generate-module for uni_portal
- **Current Wave:** 4
- **Coherence Warnings:** 2
<!-- COMPACT-SUMMARY-END -->
```

After context reset, the first thing Claude does is read this header.
That's enough to know exactly where to resume — no conversation history needed.
