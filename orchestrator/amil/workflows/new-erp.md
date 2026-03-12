# Workflow: new-erp

Initialize an Odoo ERP project by collecting configuration and analyzing a PRD with parallel research agents.

**Rules:** CJS tooling, zero npm deps, atomic writes via `odoo-gsd-tools.cjs`.

---

## Stage A: Odoo Config Collection

Collect 7 sequential configuration questions. Each answer is written to `config.json` immediately after the user responds.

### Step A.1: Ensure config exists

```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config ensure-section odoo --cwd "$(pwd)"
```

### Step A.2: Ask 7 config questions

Ask each question sequentially using `AskUserQuestion`. After each answer, write to config immediately.

**Q1: Odoo Version**
- Prompt: "Which Odoo version will this project target?"
- Options: `17.0`, `18.0`
- Default: `17.0`
- On answer:
```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-set odoo.version "${ANSWER}" --cwd "$(pwd)"
```

**Q2: Multi-Company Setup**
- Prompt: "Will this be a multi-company setup (separate company per campus)?"
- Options: `yes`, `no`
- Default: `no`
- On answer (convert to boolean):
```bash
# yes -> true, no -> false
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-set odoo.multi_company ${BOOL_VALUE} --cwd "$(pwd)"
```

**Q3: Localization**
- Prompt: "Which localization package should be used?"
- Options: `pk`, `sa`, `ae`, `none`
- Default: `pk`
- On answer:
```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-set odoo.localization "${ANSWER}" --cwd "$(pwd)"
```

**Q4: Existing Modules**
- Prompt: "Are there existing Odoo modules being extended? (comma-separated list, or 'none')"
- Input: Free text
- Default: `none`
- On answer:
```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-set odoo.existing_modules "${ANSWER}" --cwd "$(pwd)"
```
- **Important:** Store this answer in a variable `EXISTING_MODULES` for passing to research agents in Stage B.

**Q5: LMS Integration**
- Prompt: "Which LMS integration is needed?"
- Options: `canvas`, `moodle`, `none`
- Default: `canvas`
- On answer:
```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-set odoo.canvas_integration "${ANSWER}" --cwd "$(pwd)"
```

**Q6: Notification Channels**
- Prompt: "Which notification channels should be supported? (select all that apply)"
- Options: `email`, `whatsapp`, `sms`
- Multi-select (user picks one or more)
- On answer (write as JSON array):
```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-set odoo.notification_channels '["email","whatsapp"]' --cwd "$(pwd)"
```

**Q7: Deployment Target**
- Prompt: "What is the deployment target?"
- Options: `single`, `multi`
- Default: `single`
- On answer:
```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-set odoo.deployment_target "${ANSWER}" --cwd "$(pwd)"
```

---

## Stage B: PRD Analysis

Analyze the PRD document with 4 parallel research agents.

### Step B.1: Check for PRD

Check if `.planning/PRD.md` exists. If it does not exist:
1. Ask the user: "No PRD found at `.planning/PRD.md`. Please provide your PRD content or a file path to read from."
2. If user provides content directly, write it to `.planning/PRD.md`.
3. If user provides a file path, read that file and write contents to `.planning/PRD.md`.

### Step B.2: Read PRD and config

```bash
PRD_TEXT=$(cat .planning/PRD.md)
EXISTING_MODULES=$(node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" config-get odoo.existing_modules --cwd "$(pwd)")
```

### Step B.3: Create research directory

```bash
mkdir -p .planning/research
```

### Step B.4: Spawn 4 parallel research agents

Launch all 4 agents in parallel using `Task()`. Each receives the full PRD text and existing_modules as context.

**Agent 1: Module Boundary Analyzer (dedicated agent)**
```
Task(
  prompt="Analyze the following PRD and identify Odoo module boundaries.

PRD:
---
${PRD_TEXT}
---

Existing modules: ${EXISTING_MODULES}

Write your output to .planning/research/module-boundaries.json following the schema in your agent instructions.",
  subagent_type="odoo-gsd-erp-decomposer",
  description="Module boundary analysis"
)
```

**Agent 2: OCA Registry Checker (dedicated agent)**
```
Task(
  prompt="Check OCA and standard Odoo registries for existing modules covering domains in this PRD.

PRD:
---
${PRD_TEXT}
---

Existing modules: ${EXISTING_MODULES}

Write your output to .planning/research/oca-analysis.json following the schema in your agent instructions.",
  subagent_type="odoo-gsd-module-researcher",
  description="OCA registry check"
)
```

**Agent 3: Dependency Mapper (inline)**
```
Task(
  prompt="Map dependencies between Odoo modules identified in this PRD. For each custom module (uni_* prefix), identify which other custom modules it depends on and why.

PRD:
---
${PRD_TEXT}
---

Existing modules: ${EXISTING_MODULES}

Write your output as JSON to .planning/research/dependency-map.json with this EXACT schema:
{
  \"dependencies\": [
    {
      \"module\": \"uni_student\",
      \"depends_on\": [\"uni_core\"],
      \"reason\": \"Student model references institution and program from uni_core\"
    }
  ]
}

Schema details:
- module (string): The custom module name
- depends_on (string[]): List of other custom modules this depends on
- reason (string): Why this dependency exists

Write ONLY valid JSON. No markdown, no comments.",
  description="Dependency mapping"
)
```

**Agent 4: Computation Chain Identifier (inline)**
```
Task(
  prompt="Identify computation chains in this PRD -- sequences where data flows across models via computed fields, triggers, or workflows.

PRD:
---
${PRD_TEXT}
---

Existing modules: ${EXISTING_MODULES}

Write your output as JSON to .planning/research/computation-chains.json with this EXACT schema:
{
  \"chains\": [
    {
      \"name\": \"fee_calculation_chain\",
      \"description\": \"Fee structure flows from program to student enrollment to invoice\",
      \"steps\": [\"uni.program.fee_structure_id\", \"uni.enrollment.compute_fees\", \"account.move.create_invoice\"],
      \"cross_module\": true
    }
  ]
}

Schema details:
- name (string): Short identifier for the chain
- description (string): What this chain does
- steps (string[]): Ordered list of model.field or model.method references in the chain
- cross_module (boolean): true if chain spans multiple custom modules

Write ONLY valid JSON. No markdown, no comments.",
  description="Computation chain identification"
)
```

Wait for all 4 agents to complete.

### Step B.5: Validate agent outputs

Check that all 4 JSON output files exist:

```bash
MISSING=""
[ ! -f .planning/research/module-boundaries.json ] && MISSING="$MISSING module-boundaries.json"
[ ! -f .planning/research/oca-analysis.json ] && MISSING="$MISSING oca-analysis.json"
[ ! -f .planning/research/dependency-map.json ] && MISSING="$MISSING dependency-map.json"
[ ! -f .planning/research/computation-chains.json ] && MISSING="$MISSING computation-chains.json"

if [ -n "$MISSING" ]; then
  echo "WARNING: Missing agent outputs:$MISSING"
  echo "Consider retrying failed agents."
else
  echo "All 4 research outputs generated successfully."
fi
```

Validate each file contains valid JSON:

```bash
for f in module-boundaries.json oca-analysis.json dependency-map.json computation-chains.json; do
  node -e "JSON.parse(require('fs').readFileSync('.planning/research/$f','utf8')); console.log('VALID: $f')" 2>/dev/null || echo "INVALID JSON: $f"
done
```

If any file is missing or contains invalid JSON, report which agent failed and offer to retry that specific agent.

---

## Stage C: Merge, Human Approval, and ROADMAP Generation

Merge the 4 agent outputs into a unified decomposition, present it for human approval, initialize modules, and generate ROADMAP.md.

**Library:** `$HOME/.claude/odoo-gsd/bin/lib/decomposition.cjs` provides `mergeDecomposition`, `formatDecompositionTable`, `generateRoadmapMarkdown`.

### Step C.1: Merge agent outputs

Run the 5-step merge to combine all 4 agent JSON files into `decomposition.json`:

```bash
node -e "
  const { mergeDecomposition } = require('$HOME/.claude/odoo-gsd/bin/lib/decomposition.cjs');
  const path = require('path');
  const researchDir = path.join(process.cwd(), '.planning/research');
  const result = mergeDecomposition(researchDir, process.cwd());
  console.log('Merged ' + result.modules.length + ' modules into decomposition.json');
"
```

The 5-step merge process:
1. Read `module-boundaries.json` as base module list
2. Cross-reference with `oca-analysis.json` (annotate build_new/extend/skip)
3. Extract custom depends from `dependency-map.json`, run topoSort + computeTiers for tier assignment
4. Attach computation chains from `computation-chains.json` by step prefix matching
5. Generate warnings (circular risks, same-tier high-dependency, unknown complexity)

Result is written to `.planning/research/decomposition.json`.

### Step C.2: Present decomposition to human

Format the decomposition using the locked structured text format:

```bash
node -e "
  const { formatDecompositionTable } = require('$HOME/.claude/odoo-gsd/bin/lib/decomposition.cjs');
  const decomp = JSON.parse(require('fs').readFileSync('.planning/research/decomposition.json', 'utf8'));
  console.log(formatDecompositionTable(decomp));
"
```

This produces:
```
ERP MODULE DECOMPOSITION -- {N} modules across {M} tiers

TIER 1: Foundation (generate first)
  | Module      | Models   | Build     | Depends             |
  ...

COMPUTATION CHAINS (cross-module):
  1. chain_name: step1 -> step2 -> step3

WARNINGS:
  - circular risks, ordering issues

Approve this decomposition? (yes / modify / regenerate)
```

### Step C.3: Handle human response

Present the formatted table to the human and ask for approval.

- **"yes" / "approve"**: Proceed to Step C.4
- **"modify"**: Ask what to change, apply changes to `.planning/research/decomposition.json`, re-run Step C.2 to re-present
- **"regenerate"**: Go back to Stage B (re-run all 4 agents)

Loop on "modify" until the human approves or chooses to regenerate.

### Step C.4: Initialize modules (on approval)

For each module in the approved decomposition (in `generation_order`):

```bash
node -e "
  const decomp = JSON.parse(require('fs').readFileSync('.planning/research/decomposition.json', 'utf8'));
  const modules = decomp.modules;
  const order = decomp.generation_order;
  const moduleMap = new Map(modules.map(m => [m.name, m]));
  for (const name of order) {
    const mod = moduleMap.get(name);
    if (!mod) continue;
    const allDeps = [...mod.base_depends, ...mod.custom_depends];
    console.log('INIT: ' + name + ' tier=' + mod.tier + ' depends=' + JSON.stringify(allDeps));
  }
"
```

Then for each module:

```bash
node "$HOME/.claude/odoo-gsd/bin/odoo-gsd-tools.cjs" module-status init {module_name} {tier} '{depends_json}' --cwd "$(pwd)"
```

This creates `module_status.json` entries and artifact directories in the TARGET project.

### Step C.5: Generate ROADMAP.md

Generate the flat ROADMAP.md in the TARGET project's `.planning/` directory:

```bash
node -e "
  const { generateRoadmapMarkdown } = require('$HOME/.claude/odoo-gsd/bin/lib/decomposition.cjs');
  const fs = require('fs');
  const decomp = JSON.parse(fs.readFileSync('.planning/research/decomposition.json', 'utf8'));
  const md = generateRoadmapMarkdown(decomp);
  const header = '# ERP Module Roadmap\n\nGenerated: ' + new Date().toISOString().split('T')[0] + '\n\n';
  fs.writeFileSync('.planning/ROADMAP.md', header + md);
  console.log('ROADMAP.md written to .planning/ROADMAP.md');
"
```

**IMPORTANT:** This writes to the TARGET project's `.planning/ROADMAP.md`, NOT the odoo-gsd tool repo.

The ROADMAP.md uses the flat format:
```markdown
### Phase 1: uni_core
- Tier: 1 (Foundation)
- Models: uni.institution, uni.campus, uni.department, uni.program
- Depends: base, mail
- Build: NEW
- Status: not_started
```

### Step C.6: Summary

Print completion summary:

```
ERP project initialized with {N} modules across {M} tiers.
Next: Run `/odoo-gsd:discuss-module {first_module}` to start module design.
```

Where `{first_module}` is `generation_order[0]` from the decomposition.
