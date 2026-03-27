---
name: amil:validate-module
description: Run pylint-odoo + Docker installation/test validation on a generated module
argument-hint: "{module_name}"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Write
  - Agent
---
<context>
Validates a generated Odoo module using two passes: static analysis (pylint-odoo with OCA rules) and dynamic validation (Docker-based installation and test execution). Produces a structured validation report.

**Requires:** Generated module directory in addons path
**Produces:** `.planning/modules/{module}/validation-report.json`
</context>

<objective>
Run full validation on a generated Odoo module: pylint-odoo static analysis + Docker installation/test verification. Produce structured validation report.

**After this command:** Fix reported issues, then re-validate or proceed to `/amil:live-uat`.
</objective>

<execution_context>
Spawn the `amil-validator` pipeline agent to execute validation.
</execution_context>

<process>
1. Verify module exists in addons directory
2. Spawn `amil-validator` agent with module path
3. Agent runs pylint-odoo static analysis (OCA ruleset)
4. Agent runs Docker-based installation and `--test-tags={module}` execution
5. Collect and present structured validation report
6. Save report to `.planning/modules/{module}/validation-report.json`
</process>
