---
name: amil:new
description: Scaffold a new Odoo 17.0 module from a natural language description
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
Scaffold a complete Odoo 17.0 module from a natural language description.

The user provides a plain-English description of the module they need. The system parses this description, infers a module specification (name, models, fields, views, security groups), shows it for user confirmation, and then generates a fully functional Odoo 17.0 module that installs and runs out of the box.

Output follows OCA directory structure with real content (not stubs): models, views, security, tests, data, i18n, static/description, and README.
</objective>

<execution_context>
@~/.claude/amil/workflows/scaffold.md
</execution_context>

<process>
1. Parse module description from $ARGUMENTS
2. Infer module specification:
   - Module technical name (snake_case)
   - Human-readable module name
   - Models with fields, relationships, and computed fields
   - Views needed (form, list, search per model)
   - Security groups (User/Manager hierarchy)
   - Menu structure
3. Show inferred specification for user confirmation
4. On approval, render all templates via amil-utils:
   - `__manifest__.py` with correct metadata and dependencies
   - `__init__.py` files for package structure
   - Model Python files (one per model)
   - View XML files (form, list, search, actions, menus)
   - Security CSV and group XML
   - Test files with real assertions
   - Demo data with sample records
   - `README.rst` with module description
5. Report created files and next steps
</process>
