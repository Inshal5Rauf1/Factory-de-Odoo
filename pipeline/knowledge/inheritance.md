# Odoo 17.0/18.0/19.0 Inheritance Rules

> Category: Inheritance | Target: Odoo 17.0/18.0/19.0 | Load with: MASTER.md + inheritance.md

## Model Extension (`_inherit`)

### Extend an existing model by setting only `_inherit`

**WRONG:**
```python
class ResPartner(models.Model):
    _name = "res.partner"  # DO NOT redefine _name when extending
    _inherit = "res.partner"

    is_author = fields.Boolean(string="Is Author")
```

**CORRECT:**
```python
class ResPartner(models.Model):
    _inherit = "res.partner"

    is_author = fields.Boolean(string="Is Author")
    biography = fields.Text(string="Biography")
```

**Why:** When extending an existing model, set ONLY `_inherit`. Do NOT set `_name` -- the model already has a name. Setting `_name` equal to `_inherit` is redundant and can cause confusion. Omitting `_name` tells Odoo to add fields/methods to the existing model.

### Always call `super()` when overriding methods

**WRONG:**
```python
class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        if "is_author" in vals:
            # Custom logic
            pass
        # Missing super() -- breaks other modules' overrides
        return True
```

**CORRECT:**
```python
class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        if "is_author" in vals:
            # Custom logic before write
            self._update_author_status(vals)
        result = super().write(vals)
        return result
```

**Why:** Odoo uses cooperative inheritance. Every override MUST call `super()` so that other modules' overrides in the MRO chain are executed. Skipping `super()` silently breaks other modules.

### Use `super()` without arguments in Odoo 17.0

**WRONG:**
```python
def create(self, vals_list):
    result = super(ResPartner, self).create(vals_list)
    return result
```

**CORRECT:**
```python
def create(self, vals_list):
    result = super().create(vals_list)
    return result
```

**Why:** Python 3 supports argumentless `super()`. The explicit `super(ClassName, self)` form is verbose and error-prone (wrong class name causes bugs). Odoo 17 runs on Python 3.10+, so always use the clean form.

### Extend `_inherit` with a list for multiple mixins

**CORRECT:**
```python
class LibraryBook(models.Model):
    _name = "library.book"
    _description = "Library Book"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Title", required=True, tracking=True)
```

**Why:** When creating a NEW model that inherits behavior from mixins, set both `_name` and `_inherit` (as a list). This gives the new model the fields and methods from all listed mixins.

---

## Model Delegation (`_inherits`)

### Use `_inherits` for composition (has-a relationship)

**WRONG:**
```python
class LibraryMember(models.Model):
    _name = "library.member"
    _inherit = "res.partner"  # This EXTENDS res.partner, not creates a new model
```

**CORRECT:**
```python
class LibraryMember(models.Model):
    _name = "library.member"
    _description = "Library Member"
    _inherits = {"res.partner": "partner_id"}

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Related Partner",
        required=True,
        ondelete="cascade",
    )
    member_since = fields.Date(string="Member Since")
    membership_type = fields.Selection(
        selection=[("basic", "Basic"), ("premium", "Premium")],
        string="Membership Type",
        default="basic",
    )
```

**Why:** `_inherits` creates a new model that delegates to a parent model. Each `library.member` record has an associated `res.partner` record. You can read partner fields directly on the member (`member.name` reads from `partner_id.name`). This is composition, not inheritance.

### The delegation field must be declared explicitly

**WRONG:**
```python
class LibraryMember(models.Model):
    _name = "library.member"
    _inherits = {"res.partner": "partner_id"}
    # Missing partner_id field declaration
```

**CORRECT:**
```python
class LibraryMember(models.Model):
    _name = "library.member"
    _inherits = {"res.partner": "partner_id"}

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        ondelete="cascade",
    )
```

**Why:** The delegation field referenced in `_inherits` must be explicitly declared as a `Many2one` field. It should be `required=True` and typically `ondelete="cascade"`.

---

## New Model from Existing (`_name` + `_inherit`)

### Create a distinct model that copies structure from an existing one

**CORRECT:**
```python
class LibraryBookArchive(models.Model):
    _name = "library.book.archive"
    _description = "Library Book Archive"
    _inherit = "library.book"

    archive_date = fields.Date(string="Archive Date")
    archive_reason = fields.Text(string="Reason for Archiving")
```

**Why:** Setting both `_name` (different from the inherited model) and `_inherit` creates a completely new model with its own database table, copying all fields and methods from the inherited model. Use this sparingly -- it duplicates the entire model structure.

---

## View Inheritance

### Inherit a view using `inherit_id` and xpath

**WRONG:**
```xml
<!-- Overwriting the entire parent view -->
<record id="res_partner_view_form" model="ir.ui.view">
    <field name="name">res.partner.form</field>
    <field name="model">res.partner</field>
    <field name="arch" type="xml">
        <form>
            <!-- Complete form rewritten -->
        </form>
    </field>
</record>
```

**CORRECT:**
```xml
<record id="res_partner_view_form_inherit_library" model="ir.ui.view">
    <field name="name">res.partner.form.inherit.library</field>
    <field name="model">res.partner</field>
    <field name="inherit_id" ref="base.view_partner_form"/>
    <field name="arch" type="xml">
        <xpath expr="//group[@name='misc']" position="inside">
            <field name="is_author"/>
            <field name="biography"/>
        </xpath>
    </field>
</record>
```

**Why:** Never overwrite a parent view. Use `inherit_id` to reference the parent and `xpath` to modify specific parts. This preserves all other modules' modifications to the same view.

### Use unique external IDs for inherited views

**WRONG:**
```xml
<record id="view_partner_form" model="ir.ui.view">
    <!-- Same ID as base view -- will overwrite it -->
```

**CORRECT:**
```xml
<record id="res_partner_view_form_inherit_library" model="ir.ui.view">
    <!-- Unique ID: {model}_{view_type}_inherit_{module} -->
```

**Why:** Inherited view IDs must be unique. Convention: `{model_underscore}_view_{type}_inherit_{your_module}`. Using the parent's external ID overwrites the parent view entirely.

---

## xpath Patterns

### Target a field by name

**CORRECT:**
```xml
<xpath expr="//field[@name='email']" position="after">
    <field name="is_author"/>
</xpath>
```

### Target a group by name attribute

**CORRECT:**
```xml
<xpath expr="//group[@name='misc']" position="inside">
    <field name="biography"/>
</xpath>
```

### Target a notebook page by string

**CORRECT:**
```xml
<xpath expr="//page[@string='Internal Notes']" position="after">
    <page string="Library">
        <group>
            <field name="is_author"/>
        </group>
    </page>
</xpath>
```

### Target the header for adding buttons

**CORRECT:**
```xml
<xpath expr="//header" position="inside">
    <button name="action_verify_author"
            string="Verify Author"
            type="object"
            class="btn-primary"
            invisible="not is_author"/>
</xpath>
```

### Target the sheet for adding sections

**CORRECT:**
```xml
<xpath expr="//sheet" position="inside">
    <group string="Library Info">
        <field name="is_author"/>
        <field name="biography" invisible="not is_author"/>
    </group>
</xpath>
```

### Use `position` attribute correctly

| Position | Effect |
|----------|--------|
| `inside` | Add as last child of the matched element |
| `after` | Add as next sibling after the matched element |
| `before` | Add as previous sibling before the matched element |
| `replace` | Replace the matched element entirely |
| `attributes` | Modify attributes of the matched element |

### Modify attributes of an existing element

**WRONG:**
```xml
<xpath expr="//field[@name='name']" position="replace">
    <field name="name" required="1"/>
</xpath>
```

**CORRECT:**
```xml
<xpath expr="//field[@name='name']" position="attributes">
    <attribute name="required">1</attribute>
</xpath>
```

**Why:** `position="replace"` removes the element and adds a new one, losing any other modules' modifications. `position="attributes"` only changes the specified attributes, preserving everything else.

---

## Priority and Sequence

### Use `priority` to control view inheritance order

**CORRECT:**
```xml
<record id="res_partner_view_form_inherit_library" model="ir.ui.view">
    <field name="name">res.partner.form.inherit.library</field>
    <field name="model">res.partner</field>
    <field name="inherit_id" ref="base.view_partner_form"/>
    <field name="priority">20</field>
    <field name="arch" type="xml">
        <xpath expr="//group[@name='misc']" position="inside">
            <field name="is_author"/>
        </xpath>
    </field>
</record>
```

**Why:** Lower `priority` values are applied first. Default is 16. Set a higher priority (e.g., 20-99) if your modifications depend on another module's modifications being applied first.

---

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| View modifiers in inherited views | `attrs="{'invisible': [...]}"` | `invisible="expression"` | Use inline Python expressions |
| `states` attribute | `states="draft"` on buttons | `invisible="state != 'draft'"` | `states` attribute removed |
| `super()` style | `super(ClassName, self)` common | `super()` preferred | Python 3 style, cleaner |
| `column_invisible` | `attrs="{'column_invisible': ...}"` | `column_invisible="expression"` | Dedicated attribute in tree views |

---

## Common Mistakes

### Forgetting `super()` in method override

The most critical inheritance mistake. Every method override MUST call `super()`. Without it, the entire MRO chain breaks and other modules' overrides are silently skipped. This causes subtle, hard-to-debug failures.

### Wrong xpath expression

If your xpath does not match any element, Odoo raises an error during module installation. Test xpath expressions against the actual parent view XML. Common errors:
- Typo in field name: `@name='emial'` instead of `@name='email'`
- Wrong element type: `//field` when the element is a `//button`
- Missing `@name` qualifier: `//group` matches the FIRST group, which may not be the intended one

### Using `replace` when `attributes` or `inside` suffices

`position="replace"` removes the original element. If another module also modifies that element, the replacement breaks their xpath. Prefer `inside`, `after`, `before`, or `attributes` whenever possible.

### Confusing `_inherit` and `_inherits`

| Pattern | `_inherit` (no `_name`) | `_inherit` (with new `_name`) | `_inherits` |
|---------|------------------------|-------------------------------|-------------|
| Purpose | Extend existing model | New model copying structure | Delegation/composition |
| Database | Same table | New table | New table + FK to parent |
| Fields | Added to existing model | Copied to new model | Delegated reads from parent |
| Use case | Adding fields to `res.partner` | Creating `library.book.archive` from `library.book` | `library.member` has-a `res.partner` |

### Setting `_name` when extending (without intent to create new model)

If you set `_name = "res.partner"` alongside `_inherit = "res.partner"`, it is technically redundant. While it works, it can cause confusion. When extending, set ONLY `_inherit`.

## Changed in 19.0

No breaking changes to inheritance mechanisms in 19.0. Model extension (`_inherit`), delegation (`_inherits`), view inheritance (`inherit_id` + xpath), and priority all work the same as in 18.0. Note that overriding `name_get()` on inherited models will fail in 19.0 -- use `_compute_display_name()` instead (see models.md "Changed in 19.0").

---
*Odoo 17.0/18.0/19.0 Inheritance -- loaded by inheritance agents*
