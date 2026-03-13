---
name: amil:coherence-report
description: Analyze cross-module coherence for the full ERP
allowed-tools:
  - Read
  - Bash
  - Glob
---
<context>
Performs comprehensive cross-module coherence analysis across the entire ERP project. Runs 4 check categories against model_registry.json: Many2one target validity, duplicate model detection, computed field dependency chains, and security group consistency.

**Requires:** `model_registry.json` with registered modules
**Produces:** Coherence report to stdout, optionally saved to `.planning/coherence-report.json`
</context>

<objective>
Run full cross-module coherence analysis. Execute all 4 checks (Many2one targets, duplicate models, computed depends, security groups) across the entire model_registry.json. Report violations by severity and module pair.

**After this command:** Fix reported coherence violations before proceeding with further module generation.
</objective>

<process>

## Step 1: Load model registry

Read `model_registry.json` from `.planning/`. Verify it contains registered modules.

If empty or missing:
```
No model registry found. Run /amil:generate-module for at least one module first.
```
Exit.

## Step 2: Run coherence checks

Execute all 4 check categories using the CLI tool:

```bash
amil-utils orch coherence --cwd .
```

**Check 1: Many2one Target Validity** — verify target models exist in registry.
**Check 2: Duplicate Model Detection** — scan for models in multiple modules (excluding `_inherit`).
**Check 3: Computed Field Dependencies** — trace `depends=` chains, flag circular deps.
**Check 4: Security Group Consistency** — verify groups referenced in views/rules exist.

## Step 3: Report

```
## Cross-Module Coherence Report

**Modules analyzed:** {count}
**Models registered:** {count}

### Critical ({count})
| Module A | Module B | Issue | Field/Model |
|----------|----------|-------|-------------|

### Warning ({count})
| Module | Issue | Detail |
|--------|-------|--------|

**Overall coherence score:** {score}%
```

## Step 4: Save report (optional)

Write structured JSON to `.planning/coherence-report.json`.

</process>
