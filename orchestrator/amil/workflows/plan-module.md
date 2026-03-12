# Workflow: plan-module

Run the 10-step spec generation pipeline to produce an approved spec.json for a specific Odoo module.

**Rules:** CJS tooling, zero npm deps, atomic writes via `odoo-gsd-tools.cjs`.

---

## Prerequisites

The module argument `{MODULE}` is provided by the user when invoking `/odoo-gsd:plan-module {module_name}`.

---

## Step 1: Validate Module Status

Check that the module exists in module_status.json and is at an appropriate status.

```bash
MODULE_STATUS=$(node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" module-status get "${MODULE}" --raw --cwd "$(pwd)" 2>&1)
```

- If command fails or returns empty: show error "Module '${MODULE}' not found in module_status.json. Run /odoo-gsd:new-erp first." and STOP.
- Parse the JSON result.
- If `.status` is "planned": proceed normally.
- If `.status` is "spec_approved": use AskUserQuestion: "Module '${MODULE}' already has an approved spec. Overwrite and re-run pipeline? (yes / abort)". If "abort": STOP.
- If `.status` is any other value: show error "Module '${MODULE}' is at status '${status}', expected 'planned' or 'spec_approved'." and STOP.

## Step 2: Check Existing Spec

Check if `.planning/modules/${MODULE}/spec.json` already exists.

```bash
ls ".planning/modules/${MODULE}/spec.json" 2>/dev/null
```

- If file exists: use AskUserQuestion: "spec.json already exists for ${MODULE}. Options: overwrite (re-generate), skip (keep existing and jump to coherence check at Step 8), abort"
  - If "overwrite": continue from Step 3
  - If "skip": jump to Step 8 (coherence check)
  - If "abort": STOP workflow

## Step 3: Load Module Context

Read the module's CONTEXT.md:

```
Read .planning/modules/${MODULE}/CONTEXT.md
```

- If missing or empty: show error "CONTEXT.md not found for ${MODULE}. Run /odoo-gsd:discuss-module ${MODULE} first." and STOP.
- Store the full content for passing to agents.

## Step 4: Load Decomposition Entry

Read the project decomposition and extract this module's entry:

```
Read .planning/decomposition.json
```

- Find the entry matching this module name in the decomposition array.
- Extract: module name, description, depends list, tier.
- If module not found in decomposition: show error "Module '${MODULE}' not found in decomposition.json." and STOP.

## Step 5: Spawn Researcher Agent

Spawn the researcher agent to produce RESEARCH.md with Odoo-specific technical research:

```bash
mkdir -p ".planning/modules/${MODULE}/"
```

```
Task(
  prompt="Research module ${MODULE} for spec generation.

MODULE CONTEXT:
---
${CONTEXT_MD_CONTENT}
---

DECOMPOSITION ENTRY:
---
Name: ${MODULE_NAME}
Description: ${DESCRIPTION}
Dependencies: ${DEPENDS_LIST}
Tier: ${TIER}
---

Follow your agent instructions to research this module and write RESEARCH.md to:
.planning/modules/${MODULE}/RESEARCH.md",
  subagent_type="odoo-gsd-module-researcher",
  description="Module research: ${MODULE}"
)
```

After agent completes, read the produced RESEARCH.md:

```
Read .planning/modules/${MODULE}/RESEARCH.md
```

- If missing: show error "Researcher agent did not produce RESEARCH.md." and STOP.

## Step 6: Build Tiered Registry

Build the tiered registry injection for _available_models context:

```bash
# Check if registry exists and has content
REGISTRY_EXISTS=$(node -e "
  const fs = require('fs');
  const p = require('path').join(process.cwd(), '.planning', 'model_registry.json');
  try {
    const d = JSON.parse(fs.readFileSync(p, 'utf-8'));
    console.log(Object.keys(d.models || d).length > 0 ? 'yes' : 'no');
  } catch { console.log('no'); }
")
```

- If registry exists and is non-empty:
  ```bash
  TIERED_REGISTRY=$(node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" registry tiered-injection "${MODULE}" --raw --cwd "$(pwd)")
  ```
- If registry is empty or missing (first module in project): use empty tiered result:
  ```json
  {"direct": {}, "transitive": {}, "rest": []}
  ```

## Step 7: Spawn Spec Generator Agent

Spawn the spec generator agent to produce spec.json:

```bash
# Read config odoo block
ODOO_CONFIG=$(node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-get odoo --raw --cwd "$(pwd)" 2>/dev/null || echo '{}')
```

```
Task(
  prompt="Generate spec.json for module ${MODULE}.

MODULE NAME: ${MODULE}

CONTEXT.MD:
---
${CONTEXT_MD_CONTENT}
---

RESEARCH.MD:
---
${RESEARCH_MD_CONTENT}
---

DECOMPOSITION ENTRY:
---
Name: ${MODULE_NAME}
Description: ${DESCRIPTION}
Dependencies: ${DEPENDS_LIST}
Tier: ${TIER}
---

ODOO CONFIG:
---
${ODOO_CONFIG_JSON}
---

TIERED REGISTRY (for _available_models):
---
${TIERED_REGISTRY_JSON}
---

Follow your agent instructions to generate a complete spec.json conforming to odoo-gen's
ModuleSpec schema. Include all metadata fields (module_name, module_title, odoo_version, version,
summary, author, website, license, category, application, depends) and all 11 content sections
(models, business_rules, computation_chains, workflow, view_hints, reports, notifications,
cron_jobs, security, portal, controllers). Do NOT include _available_models. Write to:
.planning/modules/${MODULE}/spec.json",
  subagent_type="odoo-gsd-spec-generator",
  description="Spec generation: ${MODULE}"
)
```

After agent completes, validate the produced spec.json:

```bash
# Validate spec.json is valid JSON with required top-level keys
node -e "
  const fs = require('fs');
  const spec = JSON.parse(fs.readFileSync('.planning/modules/${MODULE}/spec.json', 'utf-8'));
  const required = ['module_name','module_title','odoo_version','depends','models','business_rules','computation_chains','workflow','view_hints','reports','notifications','cron_jobs','security','portal','controllers'];
  const missing = required.filter(k => !(k in spec));
  if (missing.length > 0) { console.error('Missing keys:', missing.join(', ')); process.exit(1); }
  console.log('Valid spec.json with', Object.keys(spec).length, 'top-level keys');
"
```

- If validation fails: show error with details and STOP.

## Step 8: Run Coherence Check

Run the coherence checker against the produced spec.json:

```bash
COHERENCE_REPORT=$(node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" coherence check --spec ".planning/modules/${MODULE}/spec.json" --registry ".planning/model_registry.json" --raw --cwd "$(pwd)")
```

- Parse the JSON coherence report.
- Save the report to `.planning/modules/${MODULE}/coherence-report.json`:

```bash
echo "${COHERENCE_REPORT}" > ".planning/modules/${MODULE}/coherence-report.json"
```

- Extract the overall status ("pass" or "fail") from the report.

## Step 9: Spawn Reviewer Agent (Presentation)

Spawn the spec reviewer agent to present a human-readable summary:

```
Task(
  prompt="Review the spec for module ${MODULE}.

COHERENCE REPORT:
---
${COHERENCE_REPORT_JSON}
---

SPEC PATH: .planning/modules/${MODULE}/spec.json
MODULE NAME: ${MODULE}

Follow your agent instructions to present a human-readable review of the spec
and coherence results.",
  subagent_type="odoo-gsd-spec-reviewer",
  description="Spec review: ${MODULE}"
)
```

The reviewer agent will present a formatted summary of the spec and any coherence violations.

## Step 10: Human Approval

Based on the coherence check status, present approval options:

- **If coherence status is "fail":**
  Use AskUserQuestion: "Coherence check found violations (see reviewer summary above). Options:
  - **approve_anyway**: Accept spec despite violations
  - **revise**: Re-run pipeline from Step 5 (researcher)
  - **abort**: Stop workflow, no status change"

- **If coherence status is "pass":**
  Use AskUserQuestion: "Spec looks good -- all coherence checks passed. Options:
  - **approve**: Accept spec and transition to spec_approved
  - **revise**: Re-run pipeline from Step 5 (researcher)
  - **abort**: Stop workflow, no status change"

**On "approve" or "approve_anyway":**
```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" module-status transition "${MODULE}" spec_approved --raw --cwd "$(pwd)"
```
Report: "Module '${MODULE}' spec approved. Status transitioned to spec_approved."
Report: "Next step: /odoo-gsd:generate-module ${MODULE}"

**On "revise":**
Go back to Step 5 (researcher) and re-run the pipeline.

**On "abort":**
Report: "Pipeline aborted. No status change for ${MODULE}."
STOP workflow.

## Completion

Report to user:
- "Spec generation complete for ${MODULE}."
- "Output: .planning/modules/${MODULE}/spec.json"
- "Coherence report: .planning/modules/${MODULE}/coherence-report.json"
- "Module status: spec_approved"
- "Next step: /odoo-gsd:generate-module ${MODULE}"
