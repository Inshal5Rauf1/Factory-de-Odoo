# Workflow: generate-module

Run the 10-step module generation pipeline to produce a complete Odoo module from an approved spec.json using the odoo-gen belt.

**Rules:** CJS tooling, zero npm deps, atomic writes via `odoo-gsd-tools.cjs`.

---

## Prerequisites

The module argument `{MODULE}` is provided by the user when invoking `/odoo-gsd:generate-module {module_name}`.

---

## Step 1: Validate Module Status

Check that the module is at `spec_approved` status.

```bash
MODULE_STATUS=$(node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" module-status get "${MODULE}" --raw --cwd "$(pwd)" 2>&1)
```

- If command fails or returns empty: show error "Module '${MODULE}' not found. Run /odoo-gsd:plan-module first." and STOP.
- Parse the JSON result.
- If `.status` is "spec_approved": proceed normally.
- If `.status` is "generated": use AskUserQuestion: "Module '${MODULE}' is already generated. Re-generate? (yes / abort)". If "abort": STOP. If "yes": transition back first:
  ```bash
  node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" module-status transition "${MODULE}" spec_approved --raw --cwd "$(pwd)"
  ```
- If `.status` is any other value: show error "Module '${MODULE}' is at status '${status}', expected 'spec_approved'. Run /odoo-gsd:plan-module first." and STOP.

## Step 2: Load Spec

Read the module's spec.json:

```
Read .planning/modules/${MODULE}/spec.json
```

- If missing: show error "spec.json not found for ${MODULE}. Run /odoo-gsd:plan-module ${MODULE} first." and STOP.
- Validate it's valid JSON with `module_name` key:
  ```bash
  node -e "
    const fs = require('fs');
    const spec = JSON.parse(fs.readFileSync('.planning/modules/${MODULE}/spec.json', 'utf-8'));
    if (!spec.module_name) { console.error('Missing module_name'); process.exit(1); }
    console.log('Valid spec for:', spec.module_name, '—', (spec.models || []).length, 'models');
  "
  ```

## Step 3: Read Odoo Gen Config

Determine the odoo-gen project path and output directory:

```bash
# Read gen_path from config
GEN_PATH=$(node -e "
  const fs = require('fs');
  const p = require('path').join(process.cwd(), '.planning', 'config.json');
  try {
    const c = JSON.parse(fs.readFileSync(p, 'utf-8'));
    console.log((c.odoo && c.odoo.gen_path) || '');
  } catch { console.log(''); }
")

# Fallback to environment variable
if [ -z "$GEN_PATH" ]; then
  GEN_PATH="${ODOO_GEN_PATH:-}"
fi

# Final check
if [ -z "$GEN_PATH" ] || [ ! -d "$GEN_PATH" ]; then
  echo "ERROR: odoo-gen path not configured."
  echo "Set odoo.gen_path in .planning/config.json or ODOO_GEN_PATH env var."
  echo "Expected: path to odoo-gen Python project (e.g., /path/to/Odoo_module_automation/python)"
  # STOP
fi
```

```bash
# Read addons_path from config (defaults to ./addons)
ADDONS_PATH=$(node -e "
  const fs = require('fs');
  const path = require('path');
  const p = path.join(process.cwd(), '.planning', 'config.json');
  try {
    const c = JSON.parse(fs.readFileSync(p, 'utf-8'));
    const ap = (c.odoo && c.odoo.addons_path) || './addons';
    console.log(path.resolve(process.cwd(), ap));
  } catch { console.log(path.resolve(process.cwd(), './addons')); }
")

mkdir -p "$ADDONS_PATH"
```

## Step 4: Build Output Path

```bash
SPEC_PATH="$(pwd)/.planning/modules/${MODULE}/spec.json"
OUTPUT_DIR="${ADDONS_PATH}"
MODULE_DIR="${ADDONS_PATH}/${MODULE}"
```

Check if module output already exists:

```bash
if [ -d "$MODULE_DIR" ]; then
  echo "Module directory already exists: $MODULE_DIR"
fi
```

- If exists: use AskUserQuestion: "Generated module already exists at ${MODULE_DIR}. Options: overwrite (delete and re-generate), abort"
  - If "overwrite": `rm -rf "$MODULE_DIR"`
  - If "abort": STOP

## Step 5: Spawn Belt Executor Agent

Spawn the belt executor to run odoo-gen:

```
Task(
  prompt="Generate Odoo module ${MODULE} using odoo-gen.

SPEC_PATH: ${SPEC_PATH}
OUTPUT_DIR: ${OUTPUT_DIR}
GEN_PATH: ${GEN_PATH}
MODULE_NAME: ${MODULE}

Follow your agent instructions to:
1. Run the odoo-gen render-module CLI
2. Collect results
3. Write generation report to:
   .planning/modules/${MODULE}/generation-report.json",
  subagent_type="odoo-gsd-belt-executor",
  description="Belt execution: ${MODULE}"
)
```

After agent completes, read the generation report:

```
Read .planning/modules/${MODULE}/generation-report.json
```

- If missing: show error "Belt executor did not produce generation-report.json." and STOP.
- If status is "failure":
  Use AskUserQuestion: "Belt execution failed. Error: ${ERROR_DETAIL}. Options:
  - **retry**: Re-run belt executor
  - **revise**: Go back to /odoo-gsd:plan-module ${MODULE} to fix spec
  - **abort**: Stop generation"
  - If "retry": go back to Step 5
  - If "revise" or "abort": STOP

## Step 6: Validate Generation Output

Verify the generated module exists and has required files:

```bash
[ -f "${MODULE_DIR}/__manifest__.py" ] && echo "MANIFEST: OK" || echo "MANIFEST: MISSING"
[ -f "${MODULE_DIR}/__init__.py" ] && echo "INIT: OK" || echo "INIT: MISSING"
[ -d "${MODULE_DIR}/models" ] && echo "MODELS: OK" || echo "MODELS: MISSING"
[ -d "${MODULE_DIR}/views" ] && echo "VIEWS: OK" || echo "VIEWS: MISSING"
[ -d "${MODULE_DIR}/security" ] && echo "SECURITY: OK" || echo "SECURITY: MISSING"
```

If any critical file/directory is missing, show error and STOP.

## Step 7: Update Model Registry

Convert spec models to registry format and merge into model_registry.json:

```bash
node -e "
  const path = require('path');
  const { updateFromSpec } = require(path.join(process.env.HOME, '.claude/odoo-gsd/bin/lib/registry.cjs'));
  const fs = require('fs');
  const spec = JSON.parse(fs.readFileSync('.planning/modules/${MODULE}/spec.json', 'utf-8'));
  const result = updateFromSpec(process.cwd(), spec);
  console.log('Registry updated: v' + result._meta.version + ', ' + Object.keys(result.models).length + ' models total');
"
```

## Step 8: Run Coherence Check (Post-Generation)

Run coherence checker to verify the newly registered models don't break existing cross-references:

```bash
COHERENCE_POST=$(node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" coherence check --spec ".planning/modules/${MODULE}/spec.json" --registry ".planning/model_registry.json" --raw --cwd "$(pwd)")
```

- If status is "fail": show warnings but do NOT stop — coherence violations at this stage are informational (they indicate cross-module work needed in future modules).

## Step 9: Spawn Belt Verifier Agent

Spawn the verifier to validate the generated module structure:

```
Task(
  prompt="Verify generated module ${MODULE}.

MODULE_PATH: ${MODULE_DIR}
SPEC_PATH: .planning/modules/${MODULE}/spec.json
MODULE_NAME: ${MODULE}

Follow your agent instructions to verify the generated module and write:
.planning/modules/${MODULE}/verification-report.json",
  subagent_type="odoo-gsd-belt-verifier",
  description="Belt verification: ${MODULE}"
)
```

After agent completes, read the verification report:

```
Read .planning/modules/${MODULE}/verification-report.json
```

Present the verification results to the user.

## Step 10: Status Transition + Git Commit

Based on verification results, present options:

- **If verification status is "pass" or "warnings":**
  Use AskUserQuestion: "Module ${MODULE} generated and verified. Options:
  - **approve**: Accept and transition to 'generated' status
  - **revise**: Go back to /odoo-gsd:plan-module ${MODULE} to fix spec
  - **abort**: Stop, no status change"

- **If verification status is "fail":**
  Use AskUserQuestion: "Module ${MODULE} generated but verification found issues. Options:
  - **approve_anyway**: Accept despite issues
  - **retry**: Re-run generation
  - **revise**: Go back to /odoo-gsd:plan-module ${MODULE}
  - **abort**: Stop, no status change"

**On "approve" or "approve_anyway":**

```bash
# Transition module status
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" module-status transition "${MODULE}" generated --raw --cwd "$(pwd)"

# Git commit the generated module + registry + reports
git add "${MODULE_DIR}" ".planning/model_registry.json" ".planning/modules/${MODULE}/generation-report.json" ".planning/modules/${MODULE}/verification-report.json" ".planning/module_status.json"
git commit -m "feat(${MODULE}): generate module from spec via odoo-gen belt"
```

Report:
- "Module '${MODULE}' generated. Status transitioned to 'generated'."
- "Output: ${MODULE_DIR}"
- "Registry: updated to v${VERSION}"
- "Next step: validate with Docker, or proceed to next module."

## Step 10.5: Persistent Docker Install (if running)

If the factory Docker instance is running (check via `factory-docker --action status`):
1. Install the generated module: `factory-docker --install ${MODULE_DIR}`
2. If install fails, log to cycle log but don't block status transition
3. If install succeeds, log success with installed module count
4. After every 10th module install: run cross-module tests on last 10 modules

## Completion

Report to user:
- "Generation complete for ${MODULE}."
- "Output: ${MODULE_DIR}"
- "Generation report: .planning/modules/${MODULE}/generation-report.json"
- "Verification report: .planning/modules/${MODULE}/verification-report.json"
- "Module status: generated"
