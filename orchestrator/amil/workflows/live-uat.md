# Live UAT Flow — Interactive Module Verification

## Overview

After modules are installed in the persistent Docker instance, guide the
user through interactive verification. The user accesses the running Odoo
ERP via browser and tests real functionality.

This replaces the code-based conversational UAT for "checked" verification.
The conversational UAT remains for quick spec validation, but live UAT is
required for the final "checked → shipped" transition at scale.

## Prerequisites

- Persistent Docker instance running (`factory-docker --action status`)
- Module(s) installed in the instance
- User has browser access to http://localhost:8069

## UAT Checkpoint Triggers

Live UAT checkpoints are triggered:
1. After every **10 modules** are installed (wave checkpoint)
2. After a **critical dependency chain** completes (chain checkpoint)
3. After **all modules** are installed (final checkpoint)
4. On **user request** (ad-hoc checkpoint)

## Wave Checkpoint Flow

### Step 1: Present Checkpoint Summary

```
=== LIVE UAT CHECKPOINT: Wave 3 ===

Modules installed since last checkpoint:
  1. uni_exam_scheduling (exam creation, scheduling, room assignment)
  2. uni_exam_grading (grade entry, GPA computation, transcripts)
  ... (up to 10)

Odoo instance: http://localhost:8069
Credentials: admin / admin

Please test the following flows and report results:
```

### Step 2: Generate Verification Checklist

For each module in the checkpoint, generate 2-3 key flows to test.
Also generate cross-module flows for modules that share references.

### Step 3: Collect Feedback

Present options per module:
- **PASS** — Module works as expected
- **MINOR** — Works but has cosmetic/UX issues (logged, not re-generated)
- **FAIL** — Critical functionality broken (triggers re-generation)
- **SKIP** — Can't test right now (stays at "checked")

For FAIL results, capture:
- What was attempted
- What happened vs what was expected
- Error messages (if any)

### Step 4: Route Failures

For each FAIL result:
1. Transition module back to `spec_approved` (allows re-generation)
2. Create `.planning/modules/{name}/uat-feedback.md` with failure details
3. Append to cycle log as a coherence event
4. The run-prd loop will pick it up and re-generate with the feedback

For MINOR results:
1. Create `.planning/modules/{name}/uat-minor-issues.md`
2. Transition to `shipped` (issues logged for future improvement)

### Step 5: Cross-Module Integration Test

After collecting per-module feedback, run automated cross-module tests:

```bash
odoo-gen-utils factory-docker --cross-test mod1 mod2 mod3 ... mod10
```

Report results to user. If integration tests fail, identify which
module pair is causing the issue.

## Final Checkpoint (All Modules)

After all 90+ modules are installed and per-wave UAT is complete:

1. Present full ERP summary
2. Full cross-module integration test
3. Present the complete ERP for final sign-off
4. On final approval: transition all remaining `checked` → `shipped`

## Step 8: Live UAT Option (for persistent Docker)

If the persistent Docker instance is running and the module is installed:

1. Ask user: "Would you like to do live UAT in the browser? The module is
   installed at http://localhost:8069"

2. If yes: switch to live UAT flow
   - Present verification checklist for this specific module
   - Collect pass/minor/fail feedback
   - Route failures back to generation

3. If no: continue with conversational UAT (existing flow)

For the `--wave` flag (batch verification):
- Present all modules in the wave together
- Include cross-module flows
- Collect feedback per module
