---
name: amil:batch-discuss
description: Auto-detect underspecified modules and discuss in batches
allowed-tools:
  - Read
  - Write
  - Bash
  - Agent
  - AskUserQuestion
---
<context>
Scans module_status.json for modules at "planned" status with missing or incomplete CONTEXT.md. Groups them into batches of 5 and runs the module questioner agent for each, producing structured CONTEXT.md files with discussion scores.

**Requires:** Initialized ERP project with modules at "planned" status
**Produces:** `.planning/modules/{module}/CONTEXT.md` for each discussed module, updated discussion scores
</context>

<objective>
Auto-detect underspecified modules (discussion score < 70 or missing CONTEXT.md) and run interactive Q&A sessions in batches of 5. Update CONTEXT.md and discussion scores for each module.

**After this command:** Review generated CONTEXT.md files, then run `/amil:plan-module {module}` for modules with score >= 70.
</objective>

<process>

## Step 1: Scan for underspecified modules

Read `module_status.json` and identify modules where:
- Status is "planned" AND
- CONTEXT.md is missing OR discussion_score < 70

Sort by dependency order (foundation modules first).

## Step 2: Show batch summary

```
## Batch Discussion Queue

**Modules needing discussion:** {count}
**Batch size:** 5

| # | Module | Status | Score | Reason |
|---|--------|--------|-------|--------|
| 1 | {name} | planned | {score} | {missing context / low score} |
```

Ask user to confirm or adjust the batch.

## Step 3: Process each batch

For each batch of up to 5 modules:
1. Spawn the `amil-module-questioner` agent for the module
2. Conduct type-aware Q&A session (detect module type from name, load question template)
3. Generate structured CONTEXT.md
4. Calculate discussion score based on answer completeness
5. Update module_status.json with new discussion_score

## Step 4: Report results

```
## Batch Discussion Complete

| # | Module | Score Before | Score After | Status |
|---|--------|-------------|-------------|--------|
| 1 | {name} | {before} | {after} | Ready for spec / Needs more |
```

</process>
