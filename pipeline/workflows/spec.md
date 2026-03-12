# Specification Workflow

End-to-end workflow for `/amil:plan`. Referenced by the `amil-scaffold` agent and the `plan` command.

## Overview

This workflow defines the complete specification pipeline:

1. **Parse Natural Language Description** -- Parse module description into a draft specification
2. **Tiered Follow-Up Questions** -- Ask targeted Odoo-specific questions to refine the spec
3. **Generate Structured Specification** -- Build the complete spec.json from answers
4. **Present Specification for Approval** -- Render as markdown, wait for user approval

Unlike the scaffold workflow (`scaffold.md`) which goes from description to code directly, this workflow produces a reviewed, committed specification as the generation contract.

---

## Phase 1: Parse Natural Language Description

Receive the module description from `$ARGUMENTS` and parse it into a draft specification.

### Steps

1. **Extract the description** from `$ARGUMENTS`:
   ```
   /amil:plan "equipment maintenance tracking with work orders and technician assignments"
   ```

2. **Infer module technical name** -- Convert the description to `snake_case`:
   - Remove stop words (a, an, the, with, and, for, of, in, to, from)
   - Take the first 2-3 key nouns as the module name
   - Convert to snake_case
   - Examples:
     - "equipment maintenance tracking" -> `equipment_maintenance`
     - "HR leave management system" -> `hr_leave_management`
     - "customer portal for invoices" -> `customer_portal`

3. **Infer module title** -- Human-readable version of the technical name:
   - `equipment_maintenance` -> "Equipment Maintenance"
   - `hr_leave_management` -> "HR Leave Management"

4. **Infer summary** -- One-line description from the user's input, trimmed and cleaned.

5. **Infer category** -- Map the description to an Odoo module category:
   | Description Domain | Odoo Category |
   |--------------------|---------------|
   | inventory, stock, warehouse | Inventory |
   | sales, quotation, deal | Sales |
   | purchase, procurement, vendor | Purchases |
   | accounting, invoice, payment, journal | Accounting |
   | HR, employee, leave, attendance, payroll | Human Resources |
   | project, task, timesheet | Project |
   | CRM, lead, opportunity, pipeline | Sales/CRM |
   | website, portal, e-commerce | Website |
   | manufacturing, production, BOM | Manufacturing |
   | maintenance, repair, equipment | Maintenance |
   | fleet, vehicle | Fleet |
   | Default (no clear match) | Uncategorized |

6. **Extract draft models** -- Identify models from nouns and noun phrases in the description:
   - Use Odoo dot-notation: `{module_prefix}.{entity}`
   - Singular form for model names (e.g., "work orders" -> `module.work_order`)
   - Examples:
     - "equipment" -> `maintenance.equipment`
     - "work orders" -> `maintenance.work_order`
     - "technician assignments" -> `maintenance.assignment`

7. **Infer draft fields for each model** -- Use the keyword-to-type mapping table to assign field types:

   | Keyword Pattern | Odoo Field Type | Default Config |
   |----------------|-----------------|----------------|
   | name, title | Char | required=True |
   | description, notes, comment, body | Text | |
   | email | Char | widget="email" |
   | phone | Char | widget="phone" |
   | url, website, link | Char | widget="url" |
   | amount, price, cost, total | Float | digits=(16,2); use Monetary if currency field present |
   | quantity, count, number, pages, age | Integer | |
   | percentage, rate, ratio | Float | digits=(5,2) |
   | date, deadline, start_date, end_date | Date | |
   | datetime, timestamp, created, updated | Datetime | |
   | active, is_*, has_* | Boolean | default=True for active |
   | image, photo, avatar | Binary | |
   | state, status | Selection | default="draft" |
   | type, kind | Selection | |
   | color | Integer | (Odoo color widget index) |
   | priority | Selection | [("0","Normal"),("1","Urgent")] (standard mail.thread default; customize as needed for domain-specific priorities) |
   | sequence | Integer | default=10 |
   | partner, customer, vendor, supplier | Many2one("res.partner") | |
   | user, responsible, assigned, salesperson | Many2one("res.users") | |
   | company | Many2one("res.company") | index=True |
   | currency | Many2one("res.currency") | |
   | tag, category (plural context) | Many2many | |
   | line, detail, item (plural context) | One2many | |

   **Always include per model:**
   - `name` (Char, required=True) -- Display name / `_rec_name`
   - `active` (Boolean, default=True) -- Archiving support

8. **Determine dependencies** -- Always start with `["base"]`, then add:
   | Description Mentions | Add Dependency |
   |---------------------|----------------|
   | notifications, messages, chatter, followers, tracking | `mail` |
   | inventory, stock, warehouse, picking | `stock` |
   | sales, quotation, sale order | `sale` |
   | purchase, vendor, supplier, procurement | `purchase` |
   | accounting, invoice, payment, journal | `account` |
   | website, portal, public | `website` |
   | HR, employee, department, leave | `hr` |
   | project, task, timesheet | `project` |
   | CRM, lead, opportunity, pipeline | `crm` |
   | product, variant, pricelist | `product` |
   | maintenance, equipment | `maintenance` |
   | fleet, vehicle | `fleet` |

   If any model will use chatter (messages, activity tracking), add `mail` to depends.

9. **Read defaults** -- Check `~/.claude/amil/defaults.json` for:
   - `odoo_version` (default: "17.0")
   - `license` (default: "LGPL-3")
   - `author` (default: "")
   - `website` (default: "")

   If `defaults.json` cannot be read, use hardcoded defaults: `17.0`, `LGPL-3`, empty author and website.

---

## Phase 2: Tiered Follow-Up Questions

Ask targeted, Odoo-specific follow-up questions to refine the draft specification. Questions are informed by the knowledge base (`@~/.claude/amil/knowledge/`) and reference real Odoo concepts.

### Tier 1 (Always Asked -- 3-5 Questions)

Present these as a numbered list and **wait for user answers** before proceeding:

1. **Models & Entities**: "Based on your description, I identified these data entities: [list inferred models with brief descriptions]. Are these the right models? Should any be added, removed, or renamed?"

2. **User Groups**: "Who will use this module? The typical Odoo pattern is a **User** group (read/write/create access) and a **Manager** group (full access including delete). Do you need different roles or additional access levels?"

3. **Module Integration**: "Should this module extend or integrate with existing Odoo apps? I inferred these dependencies: [list inferred depends]. Do you need integration with any others? Common choices:
   - `stock` (inventory/warehouse)
   - `sale` (sales orders)
   - `purchase` (purchase orders)
   - `hr` (employees/departments)
   - `account` (accounting/invoicing)
   - `website` (portal/public access)"

4. **Workflow/Status**: "Should records have a workflow? Odoo supports state-based workflows with button transitions and group-based approval. For example: **Draft -> Confirmed -> In Progress -> Done**. Describe your workflow if needed, or say 'no workflow' for simple data entry."

5. **(Conditional -- only if description mentions customer/portal/website/public)** **Portal Access**: "Should external users (customers or vendors) see this data through the Odoo portal? If so, what data should be visible and should they be able to edit it?"

### Complexity Detection

After receiving Tier 1 answers, scan the answers for complexity triggers:

| Trigger Keywords | Complexity Signal | Tier 2 Question |
|-----------------|-------------------|-----------------|
| approval, validate, confirm, sign-off | Workflow Complexity | "What are the specific states and transitions? Who can approve at each step? Should approval be restricted to managers?" |
| multi-company, branch, subsidiary, company-specific | Multi-company | "Should records be company-specific (isolated per company) or shared across companies? Odoo supports `company_id` fields with record rules for multi-company isolation." |
| extend, inherit, add field to, modify existing, customize | Inheritance | "Which specific existing Odoo models should be extended? What fields or views should be added to them? Odoo supports three inheritance patterns: classical (_inherit), prototype (_inherits), and delegation." |
| portal, website, public, customer access, vendor access | Portal Access | "What data should portal users see? Read-only or editable? Which specific fields should be visible? Should they be able to create new records?" |
| report, dashboard, KPI, analytics, statistics, chart | Reporting | "What metrics or KPIs matter most? What dimensions should data be grouped by (e.g., date, user, status)? Do you need pivot tables, charts, or both?" |
| import, export, sync, API, external, integration | External Integration | "What external systems need data exchange? What format (CSV, XML, REST API)? Inbound, outbound, or bidirectional?" |
| schedule, cron, automated, recurring, automatic, periodic | Automation | "What should happen automatically? At what frequency? What triggers the action? Odoo supports scheduled actions (ir.cron) and automated actions (base.automation)." |

### Tier 2 (Conditional -- 0-3 Questions)

Only ask Tier 2 questions for detected complexity signals. **Maximum 3 additional questions.** If no complexity is detected, skip Tier 2 entirely and proceed to Phase 3.

When selecting which Tier 2 questions to ask (if more than 3 are triggered), prioritize:
1. Workflow (affects model structure and views most)
2. Inheritance (affects model definitions fundamentally)
3. Multi-company / Portal / Reporting / Integration / Automation (by relevance to description)

### Question Guidelines

- Questions MUST be **Odoo-specific**, not generic. Reference Odoo concepts (workflow states, record rules, ir.cron, mail.thread, etc.).
- Use the knowledge base to inform questions. For example, if the user mentions "approval", reference the workflow state pattern from `knowledge/models.md`.
- **Total maximum: 8 questions** (5 Tier 1 + 3 Tier 2). Avoid interrogation fatigue.
- If user gives brief/unclear answers, **infer reasonable defaults** and show them for confirmation rather than asking more questions.

After all answers are collected, proceed to Phase 3.

---

## Phase 3: Generate Structured Specification

Build the complete `spec.json` from the parsed description (Phase 1) and user answers (Phase 2). The JSON schema **extends** the `render-module` input format and is fully backward-compatible.

### Specification JSON Schema

```json
{
  "module_name": "snake_case_name",
  "module_title": "Human Readable Name",
  "summary": "One-line module description",
  "author": "from defaults.json",
  "website": "from defaults.json",
  "license": "from defaults.json (default LGPL-3)",
  "category": "Inferred Odoo category",
  "odoo_version": "from defaults.json (default 17.0)",
  "application": true,
  "depends": ["base", "...inferred and confirmed..."],
  "models": [
    {
      "name": "module.entity",
      "description": "Human description",
      "_inherit": null,
      "inherit_mixins": [],
      "fields": [
        {
          "name": "field_name",
          "type": "FieldType",
          "string": "Label",
          "required": false,
          "default": null,
          "help": "Help text",
          "comodel_name": null,
          "inverse_name": null,
          "selection": null,
          "compute": null,
          "widget": null,
          "tracking": false,
          "copy": true,
          "index": false,
          "groups": null
        }
      ],
      "workflow_states": [],
      "sql_constraints": []
    }
  ],
  "views": [
    {
      "model": "module.entity",
      "types": ["form", "tree", "search"],
      "custom_fields_in_tree": [],
      "custom_search_filters": []
    }
  ],
  "security_groups": [
    {
      "name": "group_module_user",
      "label": "User",
      "permissions": {"read": true, "write": true, "create": true, "unlink": false}
    },
    {
      "name": "group_module_manager",
      "label": "Manager",
      "implied_ids": ["group_module_user"],
      "permissions": {"read": true, "write": true, "create": true, "unlink": true}
    }
  ],
  "menu_structure": {
    "root_menu": "Module Title",
    "sub_menus": ["Entity One", "Entity Two"]
  },
  "demo_data_hints": ["3 sample records per model"]
}
```

### Spec Generation Rules

1. **Backward compatibility**: All new fields beyond the Phase 1 `render-module` format are **OPTIONAL** with `null` or empty defaults. An old-format spec passed to `render-module` will still work.

2. **Workflow states**: If the user described a workflow, populate `workflow_states` array with objects containing `key`, `label`, and `is_default` flag:
   ```json
   "workflow_states": [
     {"key": "draft", "label": "Draft", "is_default": true},
     {"key": "confirmed", "label": "Confirmed", "is_default": false},
     {"key": "done", "label": "Done", "is_default": false}
   ]
   ```
   Also add a `state` Selection field to the model with matching values.

3. **Inheritance**: If the user mentioned extending existing models, set `_inherit` on the model:
   ```json
   {"name": "res.partner", "_inherit": "res.partner", "fields": [...]}
   ```

4. **Chatter/tracking**: If the user wants messages, activity tracking, or chatter:
   - Add `["mail.thread", "mail.activity.mixin"]` to `inherit_mixins`
   - Add `"mail"` to `depends`
   - Set `tracking: true` on `state` and `name` fields

5. **Smart defaults**: Apply the keyword-to-type mapping from Phase 1 automatically:
   - Field named `partner_id` -> set `comodel_name: "res.partner"`
   - Field named `user_id` -> set `comodel_name: "res.users"`
   - Field named `company_id` -> set `comodel_name: "res.company"`, `index: true`
   - Field named `currency_id` -> set `comodel_name: "res.currency"`
   - Field named `state` -> set `tracking: true`, `default: "draft"`, `copy: false`
   - Field named `name` -> set `tracking: true`, `required: true`
   - Field named `active` -> set `default: true`

6. **Views**: Populate `views` array with `form` + `tree` + `search` for each model:
   - `custom_fields_in_tree`: Key fields to show in the tree view (name, state, key relational fields)
   - `custom_search_filters`: Fields to include as search filters (state, key relational fields, dates)

7. **Security groups**: Default to User/Manager hierarchy:
   - User: read, write, create (no unlink)
   - Manager: full access, `implied_ids` includes user group

8. **Menu structure**: Root menu = module title, sub-menus = one per model (using model description as label).

9. **Demo data hints**: Include `"3 sample records per model"` by default. If workflow states exist, add `"Include one record in each workflow state"`.

10. **Application flag**: Set `application: false` if ALL models use `_inherit` (extension module with no new top-level models). Set `application: true` if any model defines a new `_name`.

11. **Constraints**: If the user mentioned uniqueness or validation rules, add to `sql_constraints`:
    ```json
    "sql_constraints": [
      {"name": "unique_reference", "definition": "UNIQUE(reference)", "message": "Reference must be unique"}
    ]
    ```

### Step 3.5: Edition Compatibility Check

After building the spec, run the enterprise dependency check before presenting for approval:

```bash
amil-utils check-edition {spec_path}
```

If warnings are returned:
1. Display each Enterprise dependency with its Community alternative (if available)
2. Ask user: "Some dependencies are Enterprise-only. Options:
   a) Substitute with OCA alternatives (system will update spec depends list)
   b) Keep as-is (you have Enterprise license)
   c) Remove these dependencies"
3. If user chooses (a), update spec `depends` list replacing EE modules with their OCA alternatives from the check output
4. If user chooses (b) or (c), proceed with current spec

This check is informational -- it never blocks generation. Users with Enterprise licenses can safely keep EE dependencies.

### Validation Checks

Before proceeding to Phase 4, verify the spec:

- `module_name` is present and in `snake_case`
- All model names use dot-notation (`module.entity`)
- All field types are from the known set: `Char`, `Text`, `Integer`, `Float`, `Monetary`, `Boolean`, `Date`, `Datetime`, `Binary`, `Selection`, `Html`, `Many2one`, `One2many`, `Many2many`
- All `Many2one` fields have `comodel_name` set
- All `One2many` fields have `comodel_name` and `inverse_name` set
- All `Selection` fields have `selection` array set (or `compute` for dynamic)
- `depends` includes `"base"` at minimum
- `depends` includes `"mail"` if any model uses `inherit_mixins` with `mail.thread`
- All `sql_constraints` entries have `name`, `definition`, and `message` fields set
- All field names are valid Python identifiers (snake_case, no spaces, no hyphens, no Python reserved keywords)

---

## Phase 4: Present Specification for Approval

Generate the spec.json FIRST (Phase 3 output), then render a markdown summary FROM the JSON. The markdown is a view of the JSON, not an independent document. This prevents spec-markdown desync.

### Step 4.1: Render Markdown Summary

Transform the spec.json into a human-readable markdown summary. The markdown MUST be generated from the JSON fields -- never maintain them independently.

**Markdown Summary Format:**

```markdown
## Module Specification: {module_title}

### Overview
| Property | Value |
|----------|-------|
| Technical Name | `{module_name}` |
| Title | {module_title} |
| Summary | {summary} |
| Category | {category} |
| License | {license} |
| Odoo Version | {odoo_version} |
| Application | {yes/no based on application boolean} |

### Dependencies
{depends list as comma-separated, e.g., `base`, `mail`, `stock`}

### Models

#### {model_description} (`{model_name}`)
{If _inherit is set: "Extends: `{_inherit}`"}
{If inherit_mixins is non-empty: "Mixins: {comma-separated list}"}

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| {name} | {type} | {Yes/No} | {default or -} | {help} |
| ... | ... | ... | ... | ... |

{If sql_constraints are non-empty:}
**SQL Constraints:**
- {sql_constraint.name}: {sql_constraint.message}

{Repeat for each model}

### Relationships
{For each Many2one/One2many/Many2many field across all models:}
- `{model1}` -> `{model2}` via `{field_name}` ({field_type})

### Views
{For each model:}
- **{model_description}**: {view types joined by ", "} (e.g., Form, Tree, Search)

### Security Groups
| Group | Label | Permissions | Inherits From |
|-------|-------|-------------|---------------|
| {group_name} | {label} | {R/W/C/U summary} | {implied_ids or -} |

{If workflow_states exist for any model:}
### Workflow States
{For each model with states:}
**{model_description}:**
{State diagram as text: Draft -> Confirmed -> Done}
{Note which groups can trigger transitions, if specified}

### Menu Structure
- {root_menu}
  - {sub_menu_1}
  - {sub_menu_2}

### Demo Data
{demo_data_hints as bullet list}

### Inferred Defaults (Review These)
The following were inferred from your description and standard Odoo patterns:
{List every default that was inferred, not explicitly stated by user:}
- Field `{name}` on `{model}` inferred as {type} (reason: keyword "{keyword}" pattern)
- Dependency `{dep}` added because description mentions {trigger}
- Security groups set to default User/Manager hierarchy
- {Any other inference: default values, widget choices, tracking settings, etc.}
{This section MUST be present and MUST list all inferences -- nothing is silently assumed}
```

**Rendering Rules:**

1. Iterate `spec.models[]` to build the Models and Relationships sections
2. For Relationships, scan all models' fields for types `Many2one`, `One2many`, `Many2many` and render each as a relationship line
3. For Views, use `spec.views[]` and join the `types` array with ", " (capitalize each: form -> Form)
4. For Security Groups, map `permissions` object to a compact string: R (read), W (write), C (create), U (unlink) -- e.g., "R/W/C" for user, "R/W/C/U" for manager
5. The Inferred Defaults section MUST list every field, dependency, or configuration that was not explicitly requested by the user but was added by the system
6. For Menu Structure, render `spec.menu_structure.root_menu` as the top-level bullet, then each entry in `spec.menu_structure.sub_menus` as an indented sub-bullet with sequence and action reference

### Step 4.2: Present for User Review

After rendering the markdown summary, present it to the user followed by the review options:

```
---

**Please review the specification above.**

Options:
1. **Approve** - Proceed with this specification (spec.json will be committed to git)
2. **Request Changes** - Tell me what to modify (I'll ask targeted follow-up questions)
3. **Edit Directly** - Describe your edits in plain text (I'll update the spec accordingly)
```

**Wait for user response before proceeding.** Do not auto-approve. Do not continue to code generation.

### Step 4.3: Handle User Response

**If user approves** (says "approve", "yes", "looks good", "1", "proceed", "confirm", "approved"):

1. Write spec.json to `./{module_name}/spec.json` (create the directory if it does not exist)
2. Commit to git:
   ```bash
   mkdir -p ./{module_name}
   # Write spec.json to ./{module_name}/spec.json
   git add ./{module_name}/spec.json
   git commit -m "spec({module_name}): approved module specification

   Module: {module_title}
   Models: {model1}, {model2}, ...
   "
   ```
3. **Trigger code generation** — Execute the generate.md workflow:
   - Set `$MODULE_NAME` = `{module_name}` (from spec)
   - Set `$SPEC_PATH` = `./{module_name}/spec.json`
   - Set `$OUTPUT_DIR` = current working directory
   - Follow all steps in `@workflows/generate.md` to completion

   This is the automated generation pipeline. The spec commit (step 2 above) is the
   contract; generate.md reads that contract and produces the module code.

4. Report the result:
   ```
   Specification approved and committed.

   Spec file: ./{module_name}/spec.json
   Commit: {git_hash}

   Next steps:
   - To re-run generation: /amil:plan {module_name}
   - To validate the generated module: /amil:validate ./{module_name}/
   - To modify the spec: edit ./{module_name}/spec.json and re-run
   ```

**If user requests changes** (says "changes", "modify", "2", "request changes", or describes what to change):

1. Parse which parts of the spec the user wants changed
2. Ask 1-3 TARGETED follow-up questions about only the changed sections:
   - If models change: "You want to [add/remove/rename] [model]. What fields should [model] have?"
   - If fields change: "For [model].[field], should it be [type]? Required? Any default value?"
   - If workflow changes: "What states should [model] have? What triggers each transition?"
   - If dependencies change: "Adding [dep] dependency. This gives access to [what]. Is that what you need?"
   - If security changes: "Should [group] have [permission] access? What about [other group]?"
   - If views change: "Which fields should appear in the [tree/form/search] view for [model]?"
3. Update the spec.json based on user's answers
4. Re-render the markdown summary from the updated JSON
5. Present for approval again (loop back to Step 4.2)

**If user edits directly** (says "edit", "3", or provides specific edits):

1. Parse the user's edit instructions (natural language)
2. Apply changes directly to the spec.json
3. Re-run validation checks from Phase 3 on the updated spec
4. Re-render the markdown summary showing changes
5. Present for approval again (loop back to Step 4.2)

### Step 4.4: Iteration Limit

Track the number of review-and-revise cycles. After 3 rounds of changes (whether via "Request Changes" or "Edit Directly"), suggest:

```
We've iterated 3 times on this specification. If it still needs significant changes,
consider starting fresh with `/amil:plan` and a more detailed description that
includes the specific requirements up front.

You can still approve the current version, or continue editing if the changes are minor.
```

Continue allowing edits after the suggestion -- this is advisory, not a hard stop.

### Step 4.5: Error Handling

- **spec.json write failure** (permission error, disk full): Report the error clearly. Suggest an alternative path: "Could not write to `./{module_name}/spec.json`. Try creating the directory manually: `mkdir -p ./{module_name}`". The spec data is still in memory and can be retried.

- **git commit failure** (not a repo, git not installed, staging error): Report the error. Confirm that spec.json was still saved locally: "Git commit failed, but spec.json has been saved to `./{module_name}/spec.json`. You can commit it manually: `git add ./{module_name}/spec.json && git commit -m 'spec: {module_name}'`"

- **Ambiguous user response** (unclear if approving, changing, or editing): Ask for clarification. Default to the "Request Changes" interpretation to avoid premature approval: "I wasn't sure if you want to approve or make changes. Could you clarify? Say **approve** to proceed, or describe what you'd like to change."

### Key Rules

1. **Generate JSON first, markdown from JSON**: Never maintain the spec and summary independently. The JSON is the source of truth; the markdown is a derived view.

2. **Show ALL inferred defaults**: The "Inferred Defaults (Review These)" section MUST list every assumption -- field types inferred from keywords, dependencies added from description patterns, default security groups, default field values, widget choices, tracking settings. Nothing is silently assumed.

3. **Approval blocks generation**: No downstream process (scaffold workflow, code generation, module creation) can use the spec until it is approved and committed. The approval step is a hard gate.

4. **spec.json is the contract**: The markdown summary is for human review only. The JSON file at `./{module_name}/spec.json` is what code generation reads. If there is ever a conflict between what the markdown showed and what the JSON contains, the JSON is authoritative.

5. **Backward compatibility**: The spec.json MUST be loadable by `amil-utils render-module --spec-file`. All fields beyond the Phase 1 render-module format are optional with `null` or empty defaults. An old-format spec will still work.

---

## Error Handling

- **Empty `$ARGUMENTS`**: Prompt the user: "Please describe the module you need. For example: `/amil:plan 'equipment maintenance tracking with work orders and technician assignments'`"

- **Vague description (< 5 words)**: Infer a minimal spec and present it with: "I inferred the following from your brief description. Please confirm or provide more details so I can refine the specification."

- **defaults.json not readable**: Use hardcoded defaults:
  - `odoo_version`: "17.0"
  - `license`: "LGPL-3"
  - `author`: ""
  - `website`: ""

- **Invalid model/field names**: Automatically sanitize -- convert spaces to underscores, remove special characters, ensure dot-notation for models.

- **Conflicting answers**: If user answers contradict the draft spec (e.g., says "no workflow" but earlier mentioned "approval process"), flag the conflict and ask for clarification.

---

## References

- Agent: `agents/amil-scaffold.md`
- Command: `commands/plan.md`
- Existing workflow: `workflows/scaffold.md` (pattern reference for quick mode)
- Knowledge base (loaded by agent for question generation):
  - `@~/.claude/amil/knowledge/MASTER.md` (global conventions)
  - `@~/.claude/amil/knowledge/models.md` (model patterns, field types, inheritance)
  - `@~/.claude/amil/knowledge/views.md` (view types, modifiers, widgets)
  - `@~/.claude/amil/knowledge/security.md` (groups, ACLs, record rules)
  - `@~/.claude/amil/knowledge/manifest.md` (manifest keys, depends)
  - `@~/.claude/amil/knowledge/inheritance.md` (inheritance patterns)
  - `@~/.claude/amil/knowledge/actions.md` (server actions, automated actions)
  - `@~/.claude/amil/knowledge/wizards.md` (transient models, wizard pattern)
  - `@~/.claude/amil/knowledge/data.md` (data files, email templates)
  - `@~/.claude/amil/knowledge/testing.md` (test patterns, TransactionCase)
  - `@~/.claude/amil/knowledge/controllers.md` (HTTP controllers, portal)
  - `@~/.claude/amil/knowledge/i18n.md` (translations, _() function)
- Defaults: `~/.claude/amil/defaults.json`
