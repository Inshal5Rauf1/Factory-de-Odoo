# Odoo 17.0/18.0/19.0 View Rules

> Loaded alongside MASTER.md. Covers form, tree, search views, modifiers,
> actions, menus, external IDs, statusbar, and Odoo 17 view changes.

## Form Views

### Standard form structure

```xml
<odoo>
    <record id="library_book_view_form" model="ir.ui.view">
        <field name="name">library.book.form</field>
        <field name="model">library.book</field>
        <field name="arch" type="xml">
            <form string="Library Book">
                <header>
                    <button name="action_confirm" string="Confirm"
                            type="object" class="btn-primary"
                            invisible="state != 'draft'"/>
                    <field name="state" widget="statusbar"
                           statusbar_visible="draft,confirmed,done"/>
                </header>
                <sheet>
                    <group>
                        <group>
                            <field name="name"/>
                            <field name="partner_id"/>
                        </group>
                        <group>
                            <field name="date_published"/>
                            <field name="state"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Details">
                            <field name="description"/>
                        </page>
                        <page string="Lines">
                            <field name="line_ids"/>
                        </page>
                    </notebook>
                </sheet>
                <chatter/>
            </form>
        </field>
    </record>
</odoo>
```

### Always use `<header>` for buttons and statusbar

**WRONG:**
```xml
<form>
    <button name="action_confirm" string="Confirm" type="object"/>
    <sheet>
        <field name="name"/>
    </sheet>
</form>
```

**CORRECT:**
```xml
<form>
    <header>
        <button name="action_confirm" string="Confirm"
                type="object" class="btn-primary"/>
    </header>
    <sheet>
        <field name="name"/>
    </sheet>
</form>
```

**Why:** Buttons outside `<header>` render incorrectly. The `<header>` section provides the standard button bar above the form sheet.

### Always use `<sheet>` inside `<form>`

**WRONG:**
```xml
<form>
    <group>
        <field name="name"/>
    </group>
</form>
```

**CORRECT:**
```xml
<form>
    <sheet>
        <group>
            <field name="name"/>
        </group>
    </sheet>
</form>
```

**Why:** `<sheet>` provides the standard card-style layout. Without it, the form renders as a flat page without proper padding and structure.

### Use `<chatter/>` shorthand (Odoo 17)

**WRONG:**
```xml
<div class="oe_chatter">
    <field name="message_follower_ids" widget="mail_followers"/>
    <field name="activity_ids" widget="mail_activity"/>
    <field name="message_ids" widget="mail_thread"/>
</div>
```

**CORRECT:**
```xml
<chatter/>
```

**Why:** Odoo 17 supports the `<chatter/>` shorthand that renders all mail components. Only use this if the model inherits `mail.thread`.

## List/Tree Views

### Use `<tree>` tag in Odoo 17.0

**WRONG (Odoo 18+ only):**
```xml
<list>
    <field name="name"/>
    <field name="state"/>
</list>
```

**CORRECT (Odoo 17.0):**
```xml
<tree>
    <field name="name"/>
    <field name="state"/>
</tree>
```

**Why:** Odoo 17.0 uses `<tree>` for list views. The `<list>` tag is only valid starting in Odoo 18.0. Using `<list>` in 17.0 produces an error.

### Standard tree view record

```xml
<record id="library_book_view_tree" model="ir.ui.view">
    <field name="name">library.book.tree</field>
    <field name="model">library.book</field>
    <field name="arch" type="xml">
        <tree>
            <field name="name"/>
            <field name="partner_id"/>
            <field name="date_published"/>
            <field name="state" decoration-info="state == 'draft'"
                   decoration-success="state == 'done'"/>
        </tree>
    </field>
</record>
```

### Use `column_invisible` for tree column visibility

**WRONG:**
```xml
<tree>
    <field name="internal_code"
           attrs="{'column_invisible': [('parent.show_code', '=', False)]}"/>
</tree>
```

**CORRECT:**
```xml
<tree>
    <field name="internal_code"
           column_invisible="not parent.show_code"/>
</tree>
```

**Why:** `column_invisible` is a new dedicated attribute in Odoo 17.0 that takes an inline Python expression. The old `attrs` dict syntax is removed.

### Editable tree views

```xml
<tree editable="bottom">
    <field name="product_id"/>
    <field name="quantity"/>
    <field name="price_unit"/>
</tree>
```

Options: `editable="bottom"` (new rows at bottom) or `editable="top"` (new rows at top).

## Search Views

### Standard search view

```xml
<record id="library_book_view_search" model="ir.ui.view">
    <field name="name">library.book.search</field>
    <field name="model">library.book</field>
    <field name="arch" type="xml">
        <search>
            <field name="name" string="Title"/>
            <field name="partner_id"/>
            <separator/>
            <filter name="filter_draft" string="Draft"
                    domain="[('state', '=', 'draft')]"/>
            <filter name="filter_active" string="Active"
                    domain="[('active', '=', True)]"/>
            <separator/>
            <group expand="0" string="Group By">
                <filter name="group_state" string="Status"
                        context="{'group_by': 'state'}"/>
                <filter name="group_partner" string="Partner"
                        context="{'group_by': 'partner_id'}"/>
            </group>
        </search>
    </field>
</record>
```

### Always give filters a `name` attribute

**WRONG:**
```xml
<filter string="Draft" domain="[('state', '=', 'draft')]"/>
```

**CORRECT:**
```xml
<filter name="filter_draft" string="Draft"
        domain="[('state', '=', 'draft')]"/>
```

**Why:** Filters without `name` cannot be referenced in action `context` for default activation, and cannot be targeted by inheritance for extension.

## View Modifiers (CRITICAL -- Changed in 17.0)

### Use inline expressions, NOT `attrs` dict

**WRONG (Odoo 16 and earlier -- REMOVED in 17.0):**
```xml
<field name="partner_id"
       attrs="{'invisible': [('state', '!=', 'draft')],
               'readonly': [('state', '=', 'done')],
               'required': [('type', '=', 'sale')]}"/>
```

**CORRECT (Odoo 17.0):**
```xml
<field name="partner_id"
       invisible="state != 'draft'"
       readonly="state == 'done'"
       required="type == 'sale'"/>
```

**Why:** The `attrs` attribute is completely removed in Odoo 17.0. Modifiers use inline Python expressions directly on the element. This is not optional -- `attrs` will cause a hard error.

### Do NOT use `states` attribute on buttons

**WRONG:**
```xml
<button name="action_confirm" string="Confirm"
        type="object" states="draft"/>
```

**CORRECT:**
```xml
<button name="action_confirm" string="Confirm"
        type="object" invisible="state != 'draft'"/>
```

**Why:** The `states` attribute is removed in Odoo 17.0. Use `invisible` with an inline expression instead.

### Modifier expressions are Python, not domains

**WRONG (domain-style in inline):**
```xml
<field name="partner_id"
       invisible="[('state', '!=', 'draft')]"/>
```

**CORRECT (Python expression):**
```xml
<field name="partner_id"
       invisible="state != 'draft'"/>
```

**Why:** Inline modifiers use Python expressions evaluated in the browser, not server-side domain tuples. Domain syntax in inline modifiers causes a JavaScript error.

## Actions and Menus

### Action definition

```xml
<record id="library_book_action" model="ir.actions.act_window">
    <field name="name">Library Books</field>
    <field name="res_model">library.book</field>
    <field name="view_mode">tree,form</field>
    <field name="search_view_id" ref="library_book_view_search"/>
    <field name="context">{'search_default_filter_active': 1}</field>
    <field name="help" type="html">
        <p class="o_view_nocontent_smiling_face">
            Create your first book
        </p>
    </field>
</record>
```

### Menu hierarchy

```xml
<menuitem id="menu_library_root" name="Library" sequence="100"/>
<menuitem id="menu_library_catalog" name="Catalog"
          parent="menu_library_root" sequence="10"/>
<menuitem id="menu_library_book" name="Books"
          parent="menu_library_catalog"
          action="library_book_action" sequence="10"/>
```

## External ID Naming Conventions

| Element | Pattern | Example |
|---------|---------|---------|
| Form view | `{model_underscore}_view_form` | `library_book_view_form` |
| Tree view | `{model_underscore}_view_tree` | `library_book_view_tree` |
| Search view | `{model_underscore}_view_search` | `library_book_view_search` |
| Action | `{model_underscore}_action` | `library_book_action` |
| Root menu | `menu_{module}_root` | `menu_library_root` |
| Sub menu | `menu_{model_underscore}` | `menu_library_book` |

## Statusbar Pattern

### Complete statusbar with conditional buttons

```xml
<header>
    <button name="action_confirm" string="Confirm"
            type="object" class="btn-primary"
            invisible="state != 'draft'"/>
    <button name="action_done" string="Done"
            type="object" class="btn-primary"
            invisible="state != 'confirmed'"/>
    <button name="action_cancel" string="Cancel"
            type="object"
            invisible="state in ('done', 'cancelled')"/>
    <field name="state" widget="statusbar"
           statusbar_visible="draft,confirmed,done"/>
</header>
```

- `statusbar_visible` lists the states shown as steps (hides others like "cancelled")
- Button visibility uses inline `invisible` expressions, not the removed `states` attribute

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Impact |
|-------------|---------------|------------|--------|
| View modifiers | `attrs="{'invisible': [('state','=','draft')]}"` | `invisible="state == 'draft'"` | **Breaking** -- attrs dict removed |
| Column hiding | `attrs="{'column_invisible': ...}"` | `column_invisible="expression"` | New dedicated attribute |
| States attribute | `states="draft"` on buttons | `invisible="state != 'draft'"` | **Breaking** -- states removed |
| Modifier syntax | Domain tuples `[('field','op','val')]` | Python expressions `field == val` | Expressions, not domains |
| Chatter | Explicit message/activity fields | `<chatter/>` shorthand | Simpler XML |
| List tag | `<tree>` | `<tree>` (still valid in 17, `<list>` in 18+) | Use `<tree>` for 17.0 |

## pylint-odoo Rules

| Rule | Trigger | Fix |
|------|---------|-----|
| **W8140** | Deprecated `attrs` attribute in XML view | Replace with inline `invisible`/`readonly`/`required` expressions |

## Common View Mistakes

1. **Using `<list>` instead of `<tree>`** -- `<list>` is Odoo 18+ only
2. **Using `attrs` dict for modifiers** -- Completely removed in 17.0
3. **Using `states` on buttons** -- Removed; use `invisible`
4. **Domain syntax in inline modifiers** -- Use Python expressions, not `[('field','op','val')]`
5. **Missing `name` on filters** -- Cannot be referenced or inherited
6. **Chatter outside `<sheet>`** -- `<chatter/>` goes after `</sheet>`, inside `<form>`
7. **Missing `<header>` for statusbar** -- Statusbar must be inside `<header>`

## Changed in 18.0

| What Changed | Before (17.0) | Now (18.0) | Impact |
|-------------|---------------|------------|--------|
| `<tree>` tag | Valid for list views | **REMOVED** -- use `<list>` exclusively | **Breaking** -- `ValueError: Wrong value for ir.ui.view.type: 'tree'` |
| `view_mode="tree,form"` | Correct for actions | Use `view_mode="list,form"` | **Breaking** -- action windows show no list view |
| `<chatter/>` shorthand | Works (verbose form also works) | **Preferred** (verbose form still works) | **Style** -- verbose form is unnecessary |
| `ir.ui.view` type `tree` | Valid view type | **REMOVED** from the registry | **Breaking** -- cannot create views with type `tree` |

### `<tree>` tag REMOVED -- use `<list>`

**WRONG (causes hard error in 18.0):**
```xml
<record id="my_model_view_tree" model="ir.ui.view">
    <field name="name">my.model.tree</field>
    <field name="model">my.model</field>
    <field name="arch" type="xml">
        <tree>
            <field name="name"/>
            <field name="state"/>
        </tree>
    </field>
</record>
```

**CORRECT (18.0):**
```xml
<record id="my_model_view_list" model="ir.ui.view">
    <field name="name">my.model.list</field>
    <field name="model">my.model</field>
    <field name="arch" type="xml">
        <list>
            <field name="name"/>
            <field name="state"/>
        </list>
    </field>
</record>
```

**Why:** Odoo 18 completely removed the `tree` view type from the registry. Using `<tree>` causes `ValueError: Wrong value for ir.ui.view.type: 'tree'`. This is a hard error, not a warning.

### `view_mode` in actions must also change

**WRONG (18.0):**
```xml
<field name="view_mode">tree,form</field>
```

**CORRECT (18.0):**
```xml
<field name="view_mode">list,form</field>
```

**Why:** The `tree` value in `view_mode` is no longer recognized. Actions will not display a list view if `tree` is used.

### `<chatter/>` shorthand preferred

**17.0 verbose form (still works in 18.0 but unnecessary):**
```xml
<div class="oe_chatter">
    <field name="message_follower_ids"/>
    <field name="activity_ids"/>
    <field name="message_ids"/>
</div>
```

**18.0 preferred form:**
```xml
<chatter/>
```

**Why:** The `<chatter/>` shorthand renders all mail components automatically. In 18.0, the verbose form is unnecessary and adds XML noise.

## Changed in 19.0

| What Changed | Before (18.0) | Now (19.0) | Impact |
|-------------|---------------|------------|--------|
| Kanban card template | `t-name="kanban-box"` | `t-name="card"` | **Breaking** -- kanban views using old template name fail to render |
| QWeb `t-esc` | Available | **Deprecated** -- use `t-out` | **Deprecation warning** -- `t-esc` still works but triggers warnings |
| `<list>` tag | Valid (introduced in 18.0) | Same, unchanged | No change from 18.0 |
| `<chatter/>` shorthand | Preferred | Same, unchanged | No change from 18.0 |

### Kanban card template: `kanban-box` replaced by `card`

**WRONG (fails in 19.0):**
```xml
<kanban>
    <templates>
        <t t-name="kanban-box">
            <div class="oe_kanban_card">
                <field name="name"/>
            </div>
        </t>
    </templates>
</kanban>
```

**CORRECT (19.0):**
```xml
<kanban>
    <templates>
        <t t-name="card">
            <field name="name"/>
        </t>
    </templates>
</kanban>
```

**Why:** Odoo 19 renamed the kanban card template from `kanban-box` to `card` and simplified the card structure. The wrapping `<div class="oe_kanban_card">` is no longer needed -- the card container is provided automatically.

### QWeb: `t-esc` deprecated -- use `t-out`

**WRONG (triggers deprecation in 19.0):**
```xml
<span t-esc="record.name.value"/>
```

**CORRECT (19.0):**
```xml
<span t-out="record.name.value"/>
```

**Why:** `t-out` is the modern replacement for both `t-esc` (escaped output) and `t-raw` (raw HTML output). In 19.0, `t-esc` triggers deprecation warnings. `t-out` escapes by default and supports `t-out` with `Markup()` for safe HTML.

---
*Odoo 17.0/18.0/19.0 Views -- loaded by view generation agents*
