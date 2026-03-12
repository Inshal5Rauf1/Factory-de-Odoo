---
name: odoo-gsd:plan-module
description: Generate spec.json for a module from CONTEXT.md and registry context
argument-hint: "{module_name}"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<context>
Runs the 10-step spec generation pipeline: validates module status, loads context, spawns researcher, builds tiered registry, generates spec.json via spec-generator agent, runs coherence check, presents review via spec-reviewer agent, and obtains human approval.

**Requires:** Module at "planned" status with CONTEXT.md (from /odoo-gsd:discuss-module)
**Produces:** `.planning/modules/{module}/spec.json`, `.planning/modules/{module}/coherence-report.json`
</context>

<objective>
Generate a complete spec.json for the specified module from CONTEXT.md and registry context.

**After this command:** Review spec.json, then run `/odoo-gsd:generate-module {module}` to generate code.
</objective>

<execution_context>
@~/.claude/odoo-gsd/workflows/plan-module.md
</execution_context>

<process>
Execute the plan-module workflow end-to-end for the specified module.
</process>
