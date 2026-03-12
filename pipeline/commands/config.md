---
name: amil:config
description: View or edit Odoo-specific configuration (odoo_version, edition, output_dir)
argument-hint: "[key] [value]"
---
<objective>
View or edit Odoo-specific configuration values.

Manages two layers of configuration:
1. **Global defaults:** `~/.claude/amil/defaults.json` (applies to all projects)
2. **Project overrides:** `.planning/config.json` `odoo` section (applies to current project)

Project overrides take precedence over global defaults.
</objective>

<process>
1. Parse $ARGUMENTS for optional key and value
2. Read global defaults from `~/.claude/amil/defaults.json`
3. Read project overrides from `.planning/config.json` (look for `odoo` section)
4. Merge configuration (project overrides win)

**If no arguments:** Show all Odoo configuration values with their source (global/project).

**Available configuration keys:**
- `odoo_version` -- Target Odoo version (default: "17.0")
- `edition` -- Odoo edition: "community" or "enterprise" (default: "community")
- `output_dir` -- Where to create scaffolded modules (default: "./")
- `python_version` -- Python version for generated code (default: "3.12")

**If key only:** Show current value and source for that key.

**If key and value:** Update the value in the project config (`.planning/config.json` `odoo` section). Create the `odoo` section if it does not exist.

5. Display the result with clear indication of what changed (if anything)
</process>
