---
name: amil:module-history
description: Show generation history — timeline of modules with status and coherence results
allowed-tools:
  - Read
  - Bash
  - Glob
---
<context>
Displays the generation history timeline showing all modules with their current status, file counts, generation dates, and coherence check results.

**Requires:** Initialized ERP project with module_status.json
**Produces:** Formatted history display to stdout
</context>

<objective>
Show generation history — timeline of modules with status, file counts, and coherence results.

**After this command:** Use `/amil:progress` for overall status, or `/amil:coherence-report` for detailed analysis.
</objective>

<process>
1. Read `module_status.json` from `.planning/`
2. For each module, gather: status, file count, generation timestamp, last coherence score
3. Sort by generation date (most recent first)
4. Display formatted timeline:
   ```
   ## Module Generation History

   | # | Module | Status | Files | Generated | Coherence |
   |---|--------|--------|-------|-----------|-----------|
   | 1 | {name} | shipped | {count} | {date} | {score}% |
   ```
5. Show summary statistics (total modules, counts by status, avg coherence)
</process>
