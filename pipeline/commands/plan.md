---
name: amil:plan
description: Plan and specify an Odoo 17.0 module from a natural language description
argument-hint: "<module description>"
agent: amil-scaffold
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Task
---
<objective>
Create a detailed module specification from a natural language description. The system asks targeted Odoo-specific follow-up questions, produces a structured JSON specification, and presents it for user approval before any code generation begins.

Unlike `/amil:new` (which scaffolds immediately), `/amil:plan` produces a thorough, reviewed specification that becomes the generation contract. The approved spec.json is committed to git and serves as the single source of truth for subsequent code generation.
</objective>

<execution_context>
@~/.claude/amil/workflows/spec.md
</execution_context>

<process>
1. Parse module description from $ARGUMENTS
2. Infer draft specification (module name, models, fields, dependencies) using keyword-to-type mapping and knowledge base patterns
3. Ask tiered Odoo-specific follow-up questions:
   - Tier 1 (always): 3-5 questions about models, user groups, integrations, workflow
   - Tier 2 (conditional): 0-3 deeper questions triggered by complexity signals (approval chains, multi-company, inheritance, portal, reporting, integration, automation)
4. Generate structured module specification (JSON) extending the render-module format
5. Validate spec: model names in dot-notation, field types from known set, relational fields have comodel_name
6. Render human-readable markdown summary of the specification
7. Present for user approval (approve / request changes / edit directly)
8. On approval, write spec.json to ./module_name/spec.json and commit to git as the generation contract
</process>
