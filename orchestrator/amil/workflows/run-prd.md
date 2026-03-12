# run-prd — Full PRD-to-ERP Cycle

## Overview

Single command that drives the entire ERP generation pipeline from
a PRD document to shipped modules. Designed to work with Ralph Loop
for autonomous iteration. Handles 90+ modules with wave-based generation,
coherence tracking, and automatic context recovery.

## Init

Read current state:
- `.planning/module_status.json` (if exists)
- `.planning/ERP_CYCLE_LOG.md` — read ONLY the compact summary header
- `.planning/research/decomposition.json` (if exists)
- `.planning/model_registry.json` (if exists — check size)
- `.planning/provisional_registry.json` (if exists — see Gap 5)

Determine current iteration number from cycle log compact summary (0 if new).

## Priority-Based Action Selection

Each iteration selects ONE action based on this priority table:

| Priority | Condition | Action |
|----------|-----------|--------|
| 0 | No modules exist | `/odoo-gsd:new-erp` with PRD |
| 0.5 | Modules exist but no provisional registry | Build provisional registry from decomposition |
| 1 | Any module at `generated` | `/odoo-gsd:verify-work` (unblock belt) |
| 2 | Any module at `checked` | Transition to `shipped`, install to Docker |
| 3 | Belt is free AND any `spec_approved` with deps met | `/odoo-gsd:generate-module` (dep order) |
| 3.5 | Belt free AND spec_approved but deps NOT met | Log blocked, skip to next ready module |
| 4 | Any `planned` with score < 70 | `/odoo-gsd:batch-discuss` (wave of 5) |
| 4b | Any `planned` with score >= 70 | `/odoo-gsd:plan-module` |
| 5 | ALL modules `shipped` or `blocked` | Finalize cycle log, output completion |
| 5.5 | Blocked modules remain with retries available | Retry blocked (max 2 retries each) |

## Step-by-Step

### Step 1: Read State

```bash
node odoo-gsd-tools.cjs module-status read --raw
# Read ONLY the compact summary (first 15 lines) for context efficiency
head -15 .planning/ERP_CYCLE_LOG.md
```

Parse module statuses into counts:
- planned_count, spec_approved_count, generated_count
- checked_count, shipped_count, blocked_count, total

### Step 2: Select Action (Priority Table)

Apply priority table top-to-bottom. First match wins.

### Step 3: Execute Action

Run the selected slash command. Log result to cycle log:
```bash
node odoo-gsd-tools.cjs cycle-log append '{
  "iteration": N,
  "module": "uni_fee",
  "action": "generate-module",
  "result": "success",
  "wave": 3,
  "stats": {"shipped": 25, "total": 92, "in_progress": 3, "remaining": 64},
  "next_action": "verify-work for uni_fee"
}'
```

### Step 4: Coherence Check (after generation)

After every module generation, run coherence validation:
```bash
node odoo-gsd-tools.cjs coherence check --registry .planning/model_registry.json
```

If coherence warnings found:
1. Log warning to cycle log via `cycle-log coherence`
2. If CRITICAL (duplicate model name, circular dep): BLOCK module
3. If WARNING (unresolved Many2one): check provisional registry — may resolve when target builds

### Step 5: Error Handling

On failure:
1. Log error to cycle log
2. If first failure for this module: retry once
3. If second failure: mark as BLOCKED in cycle log, skip
4. If 3+ modules blocked in a row: pause and ask human for guidance
5. Continue to next module

```bash
node odoo-gsd-tools.cjs cycle-log blocked "uni_fee" "Docker install failed: missing depends"
```

### Step 6: Completion Check

If all modules are `shipped` or `blocked`:
1. Finalize cycle log with summary
2. Print completion report including coherence stats
3. If blocked modules exist: report them with reasons
4. Notify user to check Docker instance at http://localhost:8069
5. If using Ralph Loop: output `<promise>ERP COMPLETE</promise>`

## Wave Strategy (90+ modules)

The dependency graph + tier system already handles ordering:
- `dep-graph order` returns topological sort
- `dep-graph can-generate {name}` checks readiness
- `module-status tiers` groups by tier

For 90+ modules, generation follows a 6-wave strategy:

| Wave | Tier | Module Count | Description |
|------|------|-------------|-------------|
| 1 | Foundation | 5-8 | Base modules: core, contacts, settings |
| 2 | Domain Core | 10-15 | Primary domains: HR, Finance, Academic, Inventory |
| 3 | Domain Extensions | 15-20 | Extensions: Payroll, Budgeting, Grading, Warehouse |
| 4 | Operations | 15-20 | Cross-domain: Scheduling, Reporting, Communication |
| 5 | Support | 12-15 | Support: Helpdesk, Document Mgmt, Quality Control |
| 6 | Integration | 10-15 | Glue: Dashboards, Portals, Workflows, Admin |

Discussion batching follows the same wave order.
Generation is strictly sequential (one at a time through belt).
Verification and shipping happen between generations to keep belt unblocked.

## Human Interaction Points

The workflow STOPS and waits for human input at:
1. PRD decomposition approval (after `new-erp`)
2. Module discussion questions (during `batch-discuss`)
3. Spec approval (during `plan-module`)
4. Generation approval (during `generate-module` step 10)
5. UAT verification (during `verify-work`)
6. **Live UAT checkpoints** — after every 10 modules shipped (see Gap 6)
7. **Blocked module triage** — after 3+ consecutive blocks

Ralph Loop handles this naturally — when Claude asks a question,
the loop pauses until the human responds.

## Docker Integration

Before starting the generation loop:
```bash
odoo-gen-utils factory-docker --action start
```

After each module ships:
```bash
odoo-gen-utils factory-docker --install /path/to/module
```

After every 10 modules shipped — cross-module integration test:
```bash
odoo-gen-utils factory-docker --cross-test mod1 mod2 mod3 ... mod10
```

Docker stays alive until human runs:
```bash
odoo-gen-utils factory-docker --action stop
```
