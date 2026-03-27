---
name: amil:generate-module
description: Generate an Odoo module from its approved spec.json using the amil belt
argument-hint: "{module_name}"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<context>
Runs the 10-step module generation pipeline: validates module status (spec_approved), loads spec.json, reads amil config, spawns belt executor agent to render module via amil CLI, validates output structure, updates model registry from spec models, spawns belt verifier for post-generation checks, and transitions module to "generated" status.

**Requires:** Module at "spec_approved" status with spec.json (from /amil:plan-module)
**Produces:** Generated Odoo module in addons directory, updated model_registry.json
</context>

<objective>
Generate a complete Odoo module from the approved spec.json using the amil rendering pipeline.

**After this command:** Review generated module, then validate with Docker or proceed to next module.
</objective>

<execution_context>
@~/.claude/amil/workflows/generate-module.md
</execution_context>

<process>
Execute the generate-module workflow end-to-end for the specified module.
</process>
