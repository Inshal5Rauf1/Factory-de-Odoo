---
name: amil:phases
description: Show Odoo module generation phases and progress
---
<objective>
Show the 9-phase Odoo module generation roadmap with current progress for each phase.

Provides visibility into the overall build plan and what capabilities are available at each stage.
</objective>

<process>
1. Read `.planning/ROADMAP.md` for the full phase structure and progress table
2. Read `.planning/STATE.md` for the current active phase

3. Present the roadmap as a progress overview:
   - Phase number, name, and description
   - Plan completion count (e.g., "2/4 plans complete")
   - Status (Completed, In Progress, Planned, Not Started)
   - Requirements covered by each phase

4. Highlight the current active phase

5. Show phase dependencies (which phases must complete before others can start)

6. Show overall project progress:
   - Total plans completed across all phases
   - Estimated completion percentage
   - Key milestones reached

7. Suggest next action based on current position
</process>
