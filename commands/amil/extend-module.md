---
name: amil:extend-module
description: Fork an existing module and generate companion _ext module with delta code
argument-hint: "{base_module_name}"
allowed-tools:
  - Read
  - Bash
  - Write
  - Agent
---
<context>
Forks an existing Odoo module and generates a companion `{module}_ext` module containing only delta code. Uses `_inherit` model extension and xpath view patterns to minimize code while maximizing upstream compatibility.

**Requires:** Base module accessible (OCA, GitHub, or local), extension requirements
**Produces:** Generated `{module}_ext` module in addons directory
</context>

<objective>
Fork an existing module and generate a companion _ext module with delta code using _inherit and xpath patterns.

**After this command:** Validate with `/amil:validate-module {module}_ext`.
</objective>

<execution_context>
Spawn the `amil-extend` pipeline agent to execute extension generation.
</execution_context>

<process>
1. Identify base module (local, OCA, or GitHub)
2. Analyze base module structure and models
3. Spawn `amil-extend` agent with base module path and requirements
4. Agent generates companion _ext module with _inherit + xpath patterns
5. Register new module in model_registry.json
6. Run coherence check against existing modules
</process>
