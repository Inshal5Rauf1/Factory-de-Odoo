---
name: amil:phases
description: Show generation phases and overall ERP project progress
allowed-tools:
  - Read
  - Bash
  - Glob
---
<context>
Displays ERP project generation phases with per-phase completion percentages. Reads from ROADMAP.md and module_status.json to calculate progress across the module generation waves.

**Requires:** Initialized ERP project with ROADMAP.md
**Produces:** Formatted phase progress display to stdout
</context>

<objective>
Show generation phases and overall ERP project progress with phase-by-phase completion percentages.

**After this command:** Use `/amil:progress` for detailed context, or `/amil:run-prd` to advance the next cycle.
</objective>

<process>
1. Read ROADMAP.md and `module_status.json` from `.planning/`
2. Map modules to generation waves (Foundation, Department, Cross-functional, Integration, Analytics, Polish)
3. Calculate per-wave completion by module status distribution
4. Display formatted progress:
   ```
   ## ERP Generation Phases

   | Wave | Name | Modules | Shipped | Progress |
   |------|------|---------|---------|----------|
   | 1 | Foundation | {n} | {n} | {pct}% |

   **Overall:** {shipped}/{total} modules shipped ({pct}%)
   ```
</process>
