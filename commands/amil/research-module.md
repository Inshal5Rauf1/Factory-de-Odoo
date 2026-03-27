---
name: amil:research-module
description: Research Odoo patterns and existing solutions before designing a module
argument-hint: "<module need description>"
allowed-tools:
  - Read
  - Bash
  - Write
  - Agent
  - WebSearch
  - WebFetch
---
<context>
Researches Odoo patterns, OCA conventions, and existing solutions before designing a module. Compiles a research report covering relevant Odoo models, patterns, pitfalls, and recommendations.

**Requires:** Natural language description of the module need
**Produces:** `.planning/modules/{module}/research-report.md`
</context>

<objective>
Research Odoo patterns, OCA conventions, and existing solutions for a module need. Compile research report to inform module design.

**After this command:** Review research report, then run `/amil:discuss-module {module}`.
</objective>

<execution_context>
Spawn the `amil-module-researcher` agent with knowledge base access.
</execution_context>

<process>
1. Parse module need description
2. Spawn `amil-module-researcher` agent
3. Agent researches Odoo patterns, OCA conventions, existing solutions
4. Compile research report: models, patterns, pitfalls, recommendations
5. Save to `.planning/modules/{module}/research-report.md`
</process>
