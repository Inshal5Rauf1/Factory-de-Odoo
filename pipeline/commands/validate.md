---
name: amil:validate
description: Run pylint-odoo and Docker-based validation on an Odoo module
argument-hint: "<module_path>"
---
<objective>
Run comprehensive validation on an Odoo module using pylint-odoo for static analysis and Docker-based Odoo 17.0 for installation and runtime testing. Produces a structured report with violations, install result, test results, and actionable error diagnosis.
</objective>

<usage>
## Basic Usage

Validate a module (full pipeline):
```bash
amil-utils validate /path/to/my_module
```

## Options

| Option | Description |
|--------|-------------|
| `--pylint-only` | Run only pylint-odoo static analysis (skip Docker install/test) |
| `--json` | Output machine-readable JSON report instead of markdown |
| `--pylintrc PATH` | Path to custom .pylintrc-odoo config file |

## Examples

Full validation (pylint + Docker install + Docker tests):
```bash
amil-utils validate ./my_module
```

Quick static analysis only (no Docker needed):
```bash
amil-utils validate ./my_module --pylint-only
```

JSON output for automated processing:
```bash
amil-utils validate ./my_module --json
```

With custom pylint config:
```bash
amil-utils validate ./my_module --pylintrc ./my_module/.pylintrc-odoo
```
</usage>

<report_format>
## Report Structure

The validation report contains three main sections plus optional diagnosis:

### 1. pylint-odoo Violations
A table of static analysis findings sorted by severity:
- **File:Line** -- Location of the issue
- **Rule** -- pylint-odoo rule code (e.g., C8101, W8106)
- **Severity** -- error, warning, convention, refactor, info
- **Message** -- Description of the violation

### 2. Docker Install
Result of installing the module in Odoo 17.0:
- **PASS** -- Module installed successfully
- **FAIL** -- Installation failed (with error details)
- **Skipped** -- Docker not available

### 3. Test Results
Per-test pass/fail results from `--test-enable`:
- **Test** -- Test method name
- **Status** -- PASS or FAIL
- **Error** -- Error message (if failed)

### 4. Diagnosis (when errors occur)
Pattern-matched explanations for common Odoo errors with suggested fixes. Covers 25 error patterns across model/field errors, XML issues, security problems, import failures, and deprecated Odoo 17.0 API usage.
</report_format>

<requirements>
## Requirements

- **pylint-odoo**: Installed automatically with amil-utils
- **Docker** (optional): Required for install and test validation. If Docker is not available, pylint-odoo still runs and Docker sections show "Skipped"
- **Module must have __manifest__.py**: The validate command requires a valid Odoo module directory

## Exit Codes

- **0**: No violations, install passed, all tests passed
- **1**: At least one violation, install failure, or test failure found
</requirements>
