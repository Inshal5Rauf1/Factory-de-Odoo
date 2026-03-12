---
name: odoo-gsd:new-erp
description: Initialize an Odoo ERP project from a PRD document
argument-hint: ""
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<context>
Collects Odoo-specific configuration (version, localization, modules, integrations) then analyzes a PRD document with 4 parallel research agents to produce module decomposition artifacts.

**Requires:** `.planning/PRD.md` (or user provides PRD content during workflow)
**Produces:** `.planning/research/module-boundaries.json`, `oca-analysis.json`, `dependency-map.json`, `computation-chains.json`
</context>

<objective>
Initialize an Odoo ERP project by collecting config and decomposing a PRD into module boundaries, OCA analysis, dependency maps, and computation chains.

**After this command:** Review decomposition output, then run merge and approval steps.
</objective>

<execution_context>
@~/.claude/odoo-gsd/workflows/new-erp.md
</execution_context>

<process>
Execute the new-erp workflow end-to-end.
</process>
