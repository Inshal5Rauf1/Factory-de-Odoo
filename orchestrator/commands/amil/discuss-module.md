---
name: amil:discuss-module
description: Run interactive module discussion to capture design decisions
argument-hint: "{module_name}"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<context>
Runs a module-type-aware Q&A session producing structured CONTEXT.md. The workflow detects the module type from its name, loads the corresponding question template from module-questions.json, and spawns a questioner agent for interactive discussion.

**Requires:** Module initialized in module_status.json (status: planned)
**Produces:** `.planning/modules/{module}/CONTEXT.md`
</context>

<objective>
Capture module design decisions through interactive discussion.

**After this command:** Review CONTEXT.md, then run `/amil:plan-module {module}` to generate spec.
</objective>

<execution_context>
@~/.claude/amil/workflows/discuss-module.md
</execution_context>

<process>
Execute the discuss-module workflow end-to-end for the specified module.
</process>
