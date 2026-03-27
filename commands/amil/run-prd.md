---
name: amil:run-prd
description: Run full PRD-to-ERP generation cycle
argument-hint: "<path-to-prd>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
  - Skill
---
<context>
Runs one iteration of the autonomous PRD-to-ERP generation pipeline. Reads module_status.json and ERP_CYCLE_LOG.md, applies priority table to select the highest-priority action, executes it, logs the result, runs coherence check, and handles errors with retry/block logic.

**Requires:** `.planning/PRD.md`, initialized ERP project (from /amil:new-erp)
**Produces:** Module state transitions, ERP_CYCLE_LOG.md updates, coherence reports
</context>

<objective>
Execute one cycle of the PRD-to-ERP pipeline: select highest-priority action from module_status.json, execute it, verify coherence, log result.

**After this command:** Check ERP_CYCLE_LOG.md for progress. Run again for next cycle, or use Ralph Loop for autonomous iteration.
</objective>

<execution_context>
@~/.claude/amil/workflows/run-prd.md
</execution_context>

<process>
Execute the run-prd workflow end-to-end. The workflow handles priority selection, action dispatch, coherence verification, and error recovery.
</process>
