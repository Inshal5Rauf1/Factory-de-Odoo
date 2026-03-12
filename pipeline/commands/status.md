---
name: amil:status
description: Show current Odoo module generation status
---
<objective>
Show the current status of Odoo module generation, combining Amil project state with Odoo-specific context.

Provides a unified view of where the user is in the module generation process.
</objective>

<process>
1. Read `.planning/STATE.md` for current phase, plan, and progress
2. Read `.planning/ROADMAP.md` for phase completion overview
3. Read `.planning/config.json` for Odoo-specific settings (if `odoo` section exists)

4. Present a status summary:
   - Current phase name and number
   - Current plan within the phase
   - Overall progress percentage
   - Last activity timestamp
   - Any active blockers or concerns

5. If a module generation is in progress:
   - Show which stage of generation is active (spec, models, views, security, tests)
   - Show any pending checkpoints awaiting user review

6. Show Odoo configuration summary (version, edition, output directory)

7. Suggest next action (e.g., "Run `/amil:new` to scaffold a module" or "Run `/amil:resume` to continue")
</process>
