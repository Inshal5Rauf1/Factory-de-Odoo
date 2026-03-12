# Scaffold Workflow

End-to-end workflow for `/amil:new`. Referenced by the `amil-scaffold` agent and the `new` command.

## Overview

This workflow defines the complete scaffold pipeline:

1. **Input Parsing** -- Parse natural language description into a module specification
2. **Spec Confirmation** -- Present inferred spec for user review and approval
3. **Generation** -- Render all templates via `amil-utils render-module`
4. **Post-Generation** -- Summarize output, list files, suggest next steps

---

## Phase 1: Input Parsing

Receive the module description from `$ARGUMENTS` and parse it into a structured module specification.

### Steps

1. **Extract the description** from `$ARGUMENTS`:
   ```
   /amil:new "inventory tracking with stock moves and warehouse locations"
   ```

2. **Infer module technical name** -- Convert the description to `snake_case`:
   - Remove stop words (a, an, the, with, and, for, of, in, to, from)
   - Take the first 2-3 key nouns as the module name
   - Convert to snake_case
   - Examples:
     - "inventory tracking with stock moves" -> `inventory_tracking`
     - "HR leave management system" -> `hr_leave_management`
     - "customer portal for invoices" -> `customer_portal`

3. **Infer module title** -- Human-readable version of the technical name:
   - `inventory_tracking` -> "Inventory Tracking"
   - `hr_leave_management` -> "HR Leave Management"

4. **Identify models** -- Extract potential models from the description:
   - Nouns and noun phrases become model candidates
   - Use Odoo dot-notation: `{module_prefix}.{entity}`
   - Examples:
     - "stock moves" -> `inventory.stock_move`
     - "warehouse locations" -> `inventory.warehouse_location`
     - "leave requests" -> `hr_leave.request`

5. **Infer fields for each model** -- Use context clues to determine field types:
   | Context Clue | Odoo Field Type |
   |--------------|-----------------|
   | "name", "title", "code", "reference" | `Char` |
   | "description", "notes", "body" | `Text` |
   | "price", "cost", "amount", "total" | `Float` |
   | "quantity", "count", "number", "pages", "age" | `Integer` |
   | "date", "deadline", "start", "end" | `Date` |
   | "datetime", "timestamp", "created", "updated" | `Datetime` |
   | "active", "is_*", "has_*", "done" | `Boolean` |
   | "image", "photo", "avatar" | `Binary` |
   | "state", "status", "type" | `Selection` |
   | Entity reference (e.g., "customer", "partner", "user") | `Many2one` |
   | Plural entity reference (e.g., "tags", "categories") | `Many2many` |
   | Implied reverse relation | `One2many` |

   Always include these default fields per model:
   - `name` (Char, required) -- Display name / `_rec_name`
   - `active` (Boolean, default True) -- Archiving support

6. **Determine dependencies** -- Always start with `["base"]`, then add:
   | Description mentions | Add dependency |
   |---------------------|----------------|
   | notifications, messages, chatter, followers | `mail` |
   | inventory, stock, warehouse, picking | `stock` |
   | sales, quotation, sale order | `sale` |
   | purchase, vendor, supplier | `purchase` |
   | accounting, invoice, payment, journal | `account` |
   | website, portal, public | `website` |
   | HR, employee, department | `hr` |
   | project, task, timesheet | `project` |
   | CRM, lead, opportunity, pipeline | `crm` |
   | product, variant, pricelist | `product` |

7. **Read defaults** -- Check `~/.claude/amil/defaults.json` for:
   - `odoo_version` (default: "17.0")
   - `license` (default: "LGPL-3")
   - `author` (default: "")
   - `website` (default: "")

---

## Phase 2: Spec Confirmation

Present the inferred specification to the user for confirmation before generating.

### Presentation Format

```
## Module Specification

**Module:** {module_name}
**Title:** {module_title}
**Summary:** {one-line summary from description}
**Category:** {inferred Odoo category}
**License:** {license from defaults}
**Odoo Version:** {odoo_version from defaults}

### Dependencies

{depends list, e.g., base, mail, stock}

### Models

#### {model_name} ({model_description})

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | Char | Yes | Display name |
| active | Boolean | No | Archiving support (default: True) |
| {field_name} | {field_type} | {Yes/No} | {description} |
| ... | ... | ... | ... |

#### {next_model_name} ...

### Security

- **User group:** Read, Write, Create access
- **Manager group:** Full access (includes Unlink)

### Views (per model)

- Form view with all fields
- Tree view with key columns
- Search view with filters
```

### Confirmation

After presenting the spec, **wait for user confirmation**:

- If user says "yes", "ok", "looks good", "confirm", "approved" -> proceed to Phase 3
- If user requests changes -> update the spec accordingly and re-present
- Common change requests:
  - Add/remove models
  - Add/remove fields
  - Change field types
  - Rename module
  - Add/remove dependencies
  - Change module category

---

## Phase 3: Generation

Generate the complete module using `amil-utils render-module`.

### Step 3.1: Create Spec JSON

Build the module specification JSON matching the `render_module` function input format:

```json
{
  "module_name": "inventory_tracking",
  "module_title": "Inventory Tracking",
  "summary": "Track inventory items with stock moves and warehouse locations",
  "author": "",
  "website": "",
  "license": "LGPL-3",
  "category": "Inventory",
  "odoo_version": "17.0",
  "application": true,
  "depends": ["base", "stock"],
  "models": [
    {
      "name": "inventory.item",
      "description": "Inventory Item",
      "fields": [
        {
          "name": "name",
          "type": "Char",
          "string": "Name",
          "required": true,
          "help": "Item display name"
        },
        {
          "name": "active",
          "type": "Boolean",
          "string": "Active",
          "required": false,
          "default": "True",
          "help": "Archiving support"
        },
        {
          "name": "code",
          "type": "Char",
          "string": "Reference Code",
          "required": false,
          "help": "Internal reference code"
        },
        {
          "name": "warehouse_id",
          "type": "Many2one",
          "string": "Warehouse",
          "comodel_name": "stock.warehouse",
          "required": false,
          "help": "Warehouse location"
        },
        {
          "name": "quantity",
          "type": "Float",
          "string": "Quantity",
          "required": false,
          "help": "Current stock quantity"
        }
      ]
    }
  ]
}
```

Write the spec to a temporary file:

```bash
cat > /tmp/odoo_gen_spec.json << 'EOF'
{spec JSON here}
EOF
```

### Step 3.2: Render Module

Call the render-module command:

```bash
$HOME/.claude/amil/bin/amil-utils render-module \
  --spec-file /tmp/odoo_gen_spec.json \
  --output-dir ./<module_name>/
```

**Note:** The `render-module` command creates the module directory inside `--output-dir` using the `module_name` from the spec. So pass `./` as the output-dir to create `./module_name/module_name/` -- or pass `.` and let the tool handle it. Check the actual output path.

Announce each generation step to the user:

```
Generating module structure...
  - __manifest__.py
  - __init__.py
Generating models...
  - models/__init__.py
  - models/{model_var}.py (per model)
Generating views...
  - views/{model_var}_views.xml (form + tree + search per model)
  - views/{model_var}_action.xml (per model)
  - views/menu.xml
Generating security...
  - security/security.xml (groups)
  - security/ir.model.access.csv (ACLs)
Generating tests...
  - tests/__init__.py
  - tests/test_{model_var}.py (per model)
Generating demo data...
  - demo/demo_data.xml
Generating documentation...
  - README.rst
  - static/description/index.html

Done!
```

### Step 3.3: List Created Files

After generation, list all created files:

```bash
find ./<module_name>/ -type f | sort
```

### Odoo 17.0 Specifics

These rules are enforced by the templates, but verify them in the output:

- **Version format:** `17.0.1.0.0` (5-part)
- **List views:** Use `<tree>` tag, NOT `<list>` (Odoo 18+ only)
- **Inline modifiers:** `invisible="expression"`, NOT `attrs=`
- **License key:** Required in `__manifest__.py`
- **XML root:** `<odoo>`, NOT `<openerp>`
- **Imports:** `from odoo import ...`, NOT `from openerp`
- **No deprecated decorators:** No `@api.one`, `@api.multi`, `@api.returns`
- **One file per model** in `models/`
- **OCA directory structure** is mandatory

---

## Phase 4: Post-Generation

Summarize the output and provide next steps.

### Summary Output

```
Module '{module_title}' scaffolded at ./{module_name}/

Created files:
  {list of all files}

Directory structure:
  {module_name}/
    __init__.py
    __manifest__.py
    README.rst
    models/
      __init__.py
      {model files}
    views/
      {view files}
      menu.xml
    security/
      security.xml
      ir.model.access.csv
    tests/
      __init__.py
      {test files}
    demo/
      demo_data.xml
    static/
      description/
        index.html
```

### Next Steps

Print the following guidance:

```
Next steps:
  1. Review the generated files and customize as needed
  2. Copy to your Odoo addons directory:
     cp -r ./{module_name} /path/to/odoo/addons/
  3. Update the Odoo modules list:
     Settings -> Apps -> Update Apps List
  4. Install the module:
     Apps -> search for "{module_title}" -> Install

For validation (available in Phase 3):
  /amil:validate ./{module_name}/
```

### Cleanup

Remove the temporary spec file:

```bash
rm -f /tmp/odoo_gen_spec.json
```

---

## Error Handling

- If `amil-utils` is not available (package not installed), fall back to generating files directly using the Write tool, following the same template patterns and OCA conventions.
- If a template rendering fails, report the error clearly and continue with remaining templates.
- If the output directory already exists, warn the user and ask before overwriting.

## References

- Agent: `agents/amil-scaffold.md`
- Command: `commands/new.md`
- Python CLI: `python/src/amil_utils/cli.py`
- Templates: `python/src/amil_utils/templates/*.j2`
- Defaults: `defaults.json`
