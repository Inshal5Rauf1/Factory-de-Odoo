---
name: amil:live-uat
description: Interactive browser-based UAT verification for shipped modules
allowed-tools:
  - Read
  - Bash
  - Glob
  - Write
  - AskUserQuestion
---
<context>
Guides the user through browser-based User Acceptance Testing of generated Odoo modules. Verifies Docker instance is running, presents key flows per module for manual testing, records pass/fail results, and generates a UAT report.

**Requires:** Generated modules deployed in Docker instance
**Produces:** `.planning/modules/{module}/uat-report.json`
</context>

<objective>
Conduct interactive browser-based UAT for Odoo modules. Verify Docker instance is running, guide user through key flows, record pass/fail results, generate UAT report.

**After this command:** Review UAT report. Modules passing UAT can transition to "shipped" status.
</objective>

<execution_context>
@~/.claude/amil/workflows/live-uat.md
</execution_context>

<process>
Execute the live-uat workflow end-to-end. The workflow handles Docker verification, flow presentation, result recording, and report generation.
</process>
