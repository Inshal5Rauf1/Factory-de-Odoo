# Generate Workflow

End-to-end code generation from an approved spec.json.
Called from spec.md after user approval. NOT called by scaffold.md or /amil:new.

---

## Overview

This workflow implements a two-pass hybrid approach to module generation with **three human review checkpoints**, an **i18n extraction step**, and a **validation + auto-fix step**:

1. **Pass 1 (Jinja2):** `amil-utils render-module` runs the Jinja2 template engine to produce all structural files, including `# TODO: implement` method stubs for computed fields, onchange handlers, and constraint methods.

2. **Checkpoint 1:** Human reviews generated models, security, and structural files.

3. **Wave 1 (sequential after Pass 1):** The `amil-model-gen` agent rewrites each model file with complete, OCA-compliant method bodies, replacing all `# TODO: implement` stubs. Wave 1 must complete entirely before Wave 2 begins, because Wave 2 agents read the completed model files.

4. **Checkpoint 2:** Human reviews business logic (computed fields, onchange handlers, constraints).

5. **Wave 2 (parallel after Wave 1):** Two agents run in parallel:
   - `amil-view-gen` enriches view files with action buttons for workflow state transitions
   - `amil-test-gen` adds computed field tests, constraint tests, and onchange tests to the Jinja2-generated test stubs

6. **Checkpoint 3:** Human reviews views and tests.

7. **i18n Extraction:** Extract translatable strings into a `.pot` file.

8. **Validation + Auto-Fix:** Run pylint-odoo with auto-fix, optionally Docker validation.

9. **Commit:** All generated files are committed to git in a single atomic commit.

10. **Report:** A generation summary is displayed to the user.

This workflow does NOT generate kanban views (deferred to Phase 7 per Decision F).
This workflow does NOT generate CRUD overrides (deferred to Phase 7 per Decision A).

> **Note on skippable checkpoints (REVW-05):** Checkpoints are always present in this workflow. If the user's Amil config has `workflow.auto_advance = true`, checkpoints auto-approve without pausing. No skip logic is needed in this workflow -- the skip behavior is Amil's existing mechanism.

---

## Inputs

- `$MODULE_NAME` -- module technical name (from spec.json `module_name` field)
- `$SPEC_PATH` -- absolute path to approved spec.json (e.g., `./$MODULE_NAME/spec.json`)
- `$OUTPUT_DIR` -- output directory (default: current working directory)
- `$RETRY_COUNT` -- regeneration attempt counter, initialized to 0 per checkpoint, max 3

---

## Step 1: Render Structural Files

Run the render-module CLI to produce the complete OCA module structure:

```bash
amil-utils render-module \
  --spec-file "$SPEC_PATH" \
  --output-dir "$OUTPUT_DIR"
```

This produces:
- `$MODULE_NAME/__manifest__.py` -- with correct load order (sequences first, wizard views last)
- `$MODULE_NAME/__init__.py` -- imports models/ and wizards/ (if any)
- `$MODULE_NAME/models/__init__.py` and `models/*.py` -- with `# TODO: implement` method stubs for computed/onchange/constrains
- `$MODULE_NAME/views/*_views.xml` -- form (with `<header>` if state field) + tree + search
- `$MODULE_NAME/views/*_action.xml` and `views/menu.xml`
- `$MODULE_NAME/data/sequences.xml` (if sequence fields detected) and `data/data.xml`
- `$MODULE_NAME/wizards/__init__.py` and `wizards/*.py` (if wizards in spec)
- `$MODULE_NAME/views/*_wizard_form.xml` (if wizards in spec)
- `$MODULE_NAME/security/security.xml` and `security/ir.model.access.csv`
- `$MODULE_NAME/tests/__init__.py` and `tests/test_*.py`
- `$MODULE_NAME/README.rst`

Verify the CLI exits with code 0 before continuing. If it fails, report the error and stop.

---

## Checkpoint 1: Review Generated Models and Security

After Step 1 completes, pause for human review of the structural files.

Initialize `$RETRY_COUNT` to 0 for this checkpoint.

### First Pass: Structured Summary

Present the following structured summary to the user:

**Generated Files:**
- Models: list each file in `models/` with the Odoo model name (e.g., `models/sale_order.py` -- `sale.order`)
- Security: `security/security.xml`, `security/ir.model.access.csv`, `security/record_rules.xml` (if present)
- Tests: list each file in `tests/`
- Views: list each file in `views/`
- Data: list files in `data/`
- Other: `__manifest__.py`, `__init__.py`, `README.rst`

**Key Decisions Detected:**
- State fields: list models with state/status Selection fields
- Computed fields: list models with `compute=` fields
- Sequence fields: list models with sequence-type Char fields
- Multi-company: list models with `company_id` Many2one
- Security groups: `{module_name}_user`, `{module_name}_manager`
- ACL summary: User (Read, Write, Create), Manager (Read, Write, Create, Unlink)

Prompt the user:

> Review the generated structural files above. Type **approved** to continue to business logic generation, or describe what needs to change.

### Handling the Response

**If the user types "approved":** Continue to Step 2 (Wave 1 -- Model Method Bodies).

**If the user describes changes:**

1. Increment `$RETRY_COUNT` for CP-1.
2. If `$RETRY_COUNT` > 3: Print the following and continue to Step 2:
   > Maximum regeneration attempts (3) reached for structural files. Proceeding to Step 2. You can manually edit the files or re-run generation.
3. Otherwise: Re-invoke the `amil-scaffold` agent with the original spec + the user's feedback to update `spec.json`. Then re-run Step 1 (`amil-utils render-module`).
4. After re-render, show a unified diff of ONLY the changed files using Python `difflib.unified_diff` (compare old vs new versions). Do NOT show unchanged files.
5. Prompt the user:
   > Here is what changed. Type **approved** to continue, or describe further changes.
6. Loop back to the handling check.

### Regeneration Scope

Rejection at CP-1 triggers a full restart: re-render structural files (Step 1) + re-run Wave 1 (Step 2) + re-run Wave 2 (Step 3). Everything depends on structural files.

---

## Step 2: Wave 1 -- Model Method Bodies

IMPORTANT: Wave 1 must complete fully before Wave 2 begins. `amil-view-gen` reads the
completed model files to add correct action button names.

For each model in `spec.models` that has at least one field with `compute`, `onchange`, or
`constrains` key:

Spawn an `amil-model-gen` Task (one per model file, can run in parallel across models):

**Task prompt for amil-model-gen:**
> Read the file `$OUTPUT_DIR/$MODULE_NAME/models/{model_var}.py` and the spec at `$SPEC_PATH`.
> Model to process: `{model_name}`.
> Rewrite the ENTIRE model file with complete OCA-compliant method bodies replacing all
> `# TODO: implement` stubs. Do NOT change any field declarations. Follow all REQUIRED
> patterns from your system prompt (for rec in self:, ValidationError for constraints, etc.).
> When done, confirm how many TODO stubs were replaced.

Wait for ALL amil-model-gen tasks to complete before proceeding to Checkpoint 2.

If a model has NO computed/onchange/constrains fields: skip it (no agent spawn needed, Jinja2 output is already complete).

---

## Checkpoint 2: Review Business Logic

After Step 2 (Wave 1) completes, pause for human review of the generated business logic.

Initialize `$RETRY_COUNT` to 0 for this checkpoint.

### First Pass: Structured Summary

Present the following to the user:

**Business Logic Added:**

For each model processed by `amil-model-gen`:
- Computed fields: list method names and what they compute (e.g., `_compute_total` -- computes `total` from `price * quantity`)
- Onchange handlers: list method names and trigger fields (e.g., `_onchange_partner_id` -- triggered by `partner_id`)
- Constraint methods: list method names and what they validate (e.g., `_check_positive_quantity` -- ensures `quantity > 0`)
- TODO stubs replaced: count per model

Prompt the user:

> Review the business logic above. Type **approved** to continue to view and test generation, or describe what needs to change.

### Handling the Response

**If the user types "approved":** Continue to Step 3 (Wave 2 -- View Enrichment + Test Generation).

**If the user describes changes:**

1. Increment `$RETRY_COUNT` for CP-2.
2. If `$RETRY_COUNT` > 3: Print the following and continue to Step 3:
   > Maximum regeneration attempts (3) reached for business logic. Proceeding to Step 3. You can manually edit the files or re-run the model-gen agent.
3. Otherwise: Re-invoke `amil-model-gen` for the affected model(s) with: original spec + current model file content + user feedback. The agent rewrites the ENTIRE model file.
4. After rewrite, show a unified diff of the changed model files only using Python `difflib.unified_diff`. Do NOT show unchanged files.
5. Prompt the user:
   > Here is what changed. Type **approved** to continue, or describe further changes.
6. Loop back to the handling check.

### Regeneration Scope

Rejection at CP-2 re-runs Wave 1 (`amil-model-gen`) for the affected models, then proceeds to re-run ALL of Wave 2 (Step 3). View-gen reads completed model files, so views must be regenerated after model changes.

---

## Step 3: Wave 2 -- View Enrichment + Test Generation

Spawn these two agents in parallel using the Task tool:

### Task A: amil-view-gen

**Prompt:**
> Read all view files in `$OUTPUT_DIR/$MODULE_NAME/views/` and the corresponding model files
> in `$OUTPUT_DIR/$MODULE_NAME/models/`. Read spec at `$SPEC_PATH`.
> For each model that has workflow_states in the spec: enrich the form view's `<header>` block
> with action buttons for each state transition (matching action_{state} methods in the model).
> Use `invisible="state != '{current_state}'"` pattern. Do NOT add kanban views.
> Write enriched view files back to the same paths.

### Task B: amil-test-gen

**Prompt:**
> Read all model files in `$OUTPUT_DIR/$MODULE_NAME/models/` and the corresponding test files
> in `$OUTPUT_DIR/$MODULE_NAME/tests/`. Read spec at `$SPEC_PATH`.
> For each model: rewrite the complete test_{model_var}.py file with all Phase 6 test categories:
> (1) Computed field tests (2 per computed field: basic + zero_case)
> (2) Constraint tests (valid + invalid with assertRaises(ValidationError))
> (3) Onchange tests (1 per onchange handler)
> (4) CRUD write test (1 per model: write a field, assert changed)
> (5) CRUD unlink test (1 per model: delete record, assert browse().exists() is False)
> (6) Access rights tests (2 per model: test_user_can_create with module User group via with_user(),
>     test_no_group_cannot_create with base.group_user only, assertRaises(AccessError))
> (7) Workflow transition tests (1 per consecutive state pair when workflow_states in spec has 2+ entries,
>     call action_STATE_KEY(), assert state changed)
> Use TransactionCase. Import AccessError from odoo.exceptions. Do NOT duplicate existing test method names.
> Read the module_name from spec.json to build group refs: MODULE_NAME.group_MODULE_NAME_user

Wait for BOTH tasks to complete.

---

## Checkpoint 3: Review Views and Tests

After Step 3 (Wave 2) completes, pause for human review of the views and tests.

Initialize `$RETRY_COUNT` to 0 for this checkpoint.

### First Pass: Structured Summary

Present the following to the user:

**View Enrichments:**
- Models with workflow buttons added: list model names and button counts (e.g., `sale.order` -- 3 buttons)
- View files modified: list paths (e.g., `views/sale_order_views.xml`)

**Test Coverage:**
- Test files generated/enriched: list paths (e.g., `tests/test_sale_order.py`)
- Test categories present: computed field tests, constraint tests, onchange tests, CRUD tests, access rights tests, workflow transition tests

Prompt the user:

> Review the views and tests above. Type **approved** to continue to i18n extraction and commit, or describe what needs to change.

### Handling the Response

**If the user types "approved":** Continue to Step 3.5 (Extract i18n Strings).

**If the user describes changes:**

1. Increment `$RETRY_COUNT` for CP-3.
2. If `$RETRY_COUNT` > 3: Print the following and continue to Step 3.5:
   > Maximum regeneration attempts (3) reached for views/tests. Proceeding to i18n extraction. You can manually edit the files or re-run the agents.
3. Otherwise: Re-invoke `amil-view-gen` and/or `amil-test-gen` with: original spec + current file content + user feedback. Agents rewrite ENTIRE files.
4. After rewrite, show a unified diff of the changed files only using Python `difflib.unified_diff`. Do NOT show unchanged files.
5. Prompt the user:
   > Here is what changed. Type **approved** to continue, or describe further changes.
6. Loop back to the handling check.

### Regeneration Scope

Rejection at CP-3 re-runs Wave 2 only (`amil-view-gen` and `amil-test-gen`). Wave 1 model files are NOT re-run.

---

## Step 3.5: Extract i18n Strings

Run the i18n extractor to generate the `.pot` file:

```bash
amil-utils extract-i18n "$OUTPUT_DIR/$MODULE_NAME"
```

This scans all Python files for `_()` calls and XML files for `string=` attributes, then writes the POT file to `$MODULE_NAME/i18n/$MODULE_NAME.pot`.

If the command fails, report the error but do NOT block the commit. The `.pot` file is a quality enhancement, not a generation blocker.

Known limitation: field `string=` parameter translations (e.g., `fields.Char(string="My Field")`) are not extracted by static analysis. This is expected for v1.

---

## Step 3.6: Validate and Auto-Fix

Run validation with auto-fix enabled:

```bash
amil-utils validate "$OUTPUT_DIR/$MODULE_NAME" --auto-fix --pylint-only
```

**Pylint auto-fix (QUAL-09):**
The `--auto-fix` flag runs up to 2 fix cycles for these mechanically fixable violations:
- W8113 (redundant `string=`), W8111 (renamed parameter), C8116 (superfluous manifest key),
  W8150 (absolute-to-relative import), C8107 (missing manifest key)

If violations remain after 2 cycles, present the escalation to the user:
```
Auto-fix exhausted. Remaining violations:

[file:line] CODE: message
  -> suggestion
```

Do NOT auto-spawn any agent for remaining violations. The user decides whether to fix manually or run `/amil:validate` again.

**Docker auto-fix (QUAL-10):**
If Docker validation is enabled (not `--pylint-only`), the system attempts to auto-fix these patterns:
- `xml_parse_error`: check for unclosed tags, fix XML syntax
- `missing_acl`: regenerate `ir.model.access.csv` via the `access_csv.j2` template
- `missing_import`: add missing Python import to the relevant model file
- `manifest_load_order`: reorder `data` list in `__manifest__.py`

Max 2 Docker fix cycles (Docker runs take 2-5 min each; more would be too slow).

If issues remain after 2 Docker attempts, present escalation:
```
Docker validation failed after 2 fix attempts. Remaining issues:

INSTALL FAILED:
  [description of failure with file reference]
  -> suggestion

TEST FAILURES:
  [test_name]: FAIL
  [error details]
  -> suggestion

Run /amil:validate for full details.
```

**Important:** Step 3.6 validation is informational -- it does NOT block the commit. The module is committed first (Step 4), then validation results are presented. This ensures the user always has the generated code available.

---

## Step 4: Commit Generated Module

```bash
git add "$OUTPUT_DIR/$MODULE_NAME/"
git commit -m "feat($MODULE_NAME): generate complete Odoo 17.0 module from spec

Generated files: models, views, security, tests, data, wizards (if any), i18n
Spec: $SPEC_PATH
"
```

If git commit fails (not in a repo, no changes staged): report the issue, confirm that
all files were written to disk, and suggest manual commit steps.

---

## Step 5: Summary Report

After commit, display:

```
Generation Complete: $MODULE_NAME

Files generated: {count from render-module output}
Models: {model names}
Views: form + tree + search per model
Wizards: {count or "none"}
Tests: {count of test files}
i18n: {count} translatable strings extracted to i18n/{module_name}.pot

Method stubs filled: {total TODO stubs replaced by amil-model-gen}
View enrichments: {count of buttons added by amil-view-gen}

Checkpoints passed: CP-1 (models/security), CP-2 (business logic), CP-3 (views/tests)
Regeneration cycles: {total retries across all checkpoints, or "none"}

Next steps:
- Validate the module: /amil:validate ./$MODULE_NAME/
- Review generated code: check models/ and views/ for correctness
- If validation fails: /amil:validate will show specific issues to fix
```

---

## Error Handling

- **render-module CLI fails**: Stop generation. Show the error. Fix the spec.json and retry.
- **amil-model-gen returns error for a model**: Log the error, continue with remaining models, report at end.
- **Wave 2 task fails**: Log the error, do not block the commit. Report which enrichment failed.
- **i18n extraction fails**: Log the error, do not block the commit. Report the failure in the summary.
- **git commit fails**: Report error, confirm files exist on disk, provide manual commit command.
