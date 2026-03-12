---
name: amil:resume
description: Resume an interrupted Odoo module generation session
---
<objective>
Resume an interrupted Odoo module generation session from where it stopped.

Uses Amil's session continuity mechanism to detect the last checkpoint and continue the generation workflow.
</objective>

<process>
1. Read `.planning/STATE.md` for session continuity information:
   - Last session timestamp
   - Stopped at (which task/checkpoint)
   - Resume file path

2. If no session to resume:
   - Inform the user that no interrupted session was found
   - Suggest running `/amil:new` to start a new module generation

3. If a session exists:
   - Show what was in progress when the session was interrupted
   - Show completed tasks and remaining tasks
   - Ask user to confirm resumption

4. On confirmation:
   - Load the resume file referenced in STATE.md
   - Continue execution from the last checkpoint
   - Follow the same generation workflow as `/amil:new`

5. Report progress as generation continues
</process>
