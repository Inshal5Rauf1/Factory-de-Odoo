# Odoo 17.0/18.0/19.0 Wizard Rules

> Category: Wizards | Target: Odoo 17.0/18.0/19.0 | Load with: MASTER.md + wizards.md

## Wizard Model

### Use `models.TransientModel` for wizards

**WRONG:**
```python
class BookBorrowWizard(models.Model):  # Regular Model -- records persist forever
    _name = "library.book.borrow.wizard"
```

**CORRECT:**
```python
from odoo import api, fields, models

class BookBorrowWizard(models.TransientModel):
    _name = "library.book.borrow.wizard"
    _description = "Borrow Book Wizard"
```

**Why:** `TransientModel` records are automatically cleaned up by Odoo's garbage collector (default: after 1 hour). Using `models.Model` for wizards creates permanent records that waste database space.

### Always set `_description` on wizard models

**WRONG:**
```python
class BookBorrowWizard(models.TransientModel):
    _name = "library.book.borrow.wizard"
    # Missing _description -- pylint-odoo W8120
```

**CORRECT:**
```python
class BookBorrowWizard(models.TransientModel):
    _name = "library.book.borrow.wizard"
    _description = "Borrow Book Wizard"
```

**Why:** `_description` is required by OCA standards (pylint-odoo W8120). It should be a human-readable description of the wizard's purpose.

---

## Wizard Fields

### Define fields for user input

**CORRECT:**
```python
class BookBorrowWizard(models.TransientModel):
    _name = "library.book.borrow.wizard"
    _description = "Borrow Book Wizard"

    borrower_id = fields.Many2one(
        comodel_name="res.partner",
        string="Borrower",
        required=True,
    )
    return_date = fields.Date(
        string="Return Date",
        required=True,
    )
    notes = fields.Text(string="Notes")
```

### Use `default_get` or `default` for context-based defaults

**WRONG:**
```python
book_id = fields.Many2one("library.book")

def action_confirm(self):
    book = self.env["library.book"].browse(self._context.get("active_id"))
    # Accessing context directly in action -- fragile
```

**CORRECT:**
```python
book_id = fields.Many2one(
    comodel_name="library.book",
    string="Book",
    readonly=True,
)

@api.model
def default_get(self, fields_list):
    defaults = super().default_get(fields_list)
    if self._context.get("active_model") == "library.book":
        defaults["book_id"] = self._context.get("active_id")
    return defaults
```

**Why:** `default_get` receives the active record context and sets field defaults. The `active_id` and `active_model` context keys are set by Odoo when launching a wizard from a record. Storing the active record in a field makes the wizard self-contained.

### Handle multiple active records with `active_ids`

**CORRECT:**
```python
book_ids = fields.Many2many(
    comodel_name="library.book",
    string="Books",
    readonly=True,
)

@api.model
def default_get(self, fields_list):
    defaults = super().default_get(fields_list)
    if self._context.get("active_model") == "library.book":
        defaults["book_ids"] = [(6, 0, self._context.get("active_ids", []))]
    return defaults
```

**Why:** When the wizard is launched from a list view with multiple selected records, `active_ids` contains all selected record IDs. Use a `Many2many` field to store them.

---

## Wizard Action Method

### Return `act_window_close` to close the wizard

**WRONG:**
```python
def action_confirm(self):
    self.book_id.write({"borrower_id": self.borrower_id.id})
    # No return -- wizard stays open
```

**CORRECT:**
```python
def action_confirm(self):
    self.ensure_one()
    self.book_id.write({
        "borrower_id": self.borrower_id.id,
        "state": "borrowed",
    })
    return {"type": "ir.actions.act_window_close"}
```

**Why:** Returning `{"type": "ir.actions.act_window_close"}` closes the wizard dialog. Without a return value, the wizard stays open and the user must manually close it.

### Return an action dict to redirect after wizard completion

**CORRECT:**
```python
def action_confirm(self):
    self.ensure_one()
    self.book_id.write({
        "borrower_id": self.borrower_id.id,
        "state": "borrowed",
    })
    return {
        "type": "ir.actions.act_window",
        "res_model": "library.book",
        "res_id": self.book_id.id,
        "view_mode": "form",
        "target": "current",
    }
```

**Why:** Returning an action dict redirects the user to a specific view after the wizard completes. This is useful for showing the modified record immediately.

### Use `self.ensure_one()` in action methods

**WRONG:**
```python
def action_confirm(self):
    # No ensure_one -- method may silently process only first record
    self.book_id.write({"state": "borrowed"})
```

**CORRECT:**
```python
def action_confirm(self):
    self.ensure_one()
    self.book_id.write({"state": "borrowed"})
    return {"type": "ir.actions.act_window_close"}
```

**Why:** `ensure_one()` raises `ValueError` if the recordset contains zero or multiple records. Wizard action methods should always operate on a single wizard instance.

---

## Wizard View

### Define a form view with `<footer>` for buttons

**WRONG:**
```xml
<record id="library_book_borrow_wizard_view_form" model="ir.ui.view">
    <field name="name">library.book.borrow.wizard.form</field>
    <field name="model">library.book.borrow.wizard</field>
    <field name="arch" type="xml">
        <form>
            <group>
                <field name="borrower_id"/>
                <field name="return_date"/>
            </group>
            <!-- Buttons inside form body -- wrong placement for dialogs -->
            <button name="action_confirm" string="Confirm" type="object"/>
        </form>
    </field>
</record>
```

**CORRECT:**
```xml
<record id="library_book_borrow_wizard_view_form" model="ir.ui.view">
    <field name="name">library.book.borrow.wizard.form</field>
    <field name="model">library.book.borrow.wizard</field>
    <field name="arch" type="xml">
        <form string="Borrow Book">
            <group>
                <field name="book_id"/>
                <field name="borrower_id"/>
                <field name="return_date"/>
                <field name="notes"/>
            </group>
            <footer>
                <button name="action_confirm"
                        string="Confirm"
                        type="object"
                        class="btn-primary"/>
                <button string="Cancel"
                        special="cancel"/>
            </footer>
        </form>
    </field>
</record>
```

**Why:** `<footer>` positions buttons at the bottom of the dialog. `special="cancel"` closes the wizard without calling any method. `class="btn-primary"` highlights the main action button.

---

## Launching Wizards

### Create a window action with `target="new"` for dialog

**WRONG:**
```xml
<record id="action_borrow_wizard" model="ir.actions.act_window">
    <field name="name">Borrow Book</field>
    <field name="res_model">library.book.borrow.wizard</field>
    <field name="view_mode">form</field>
    <!-- Missing target="new" -- opens in full page instead of dialog -->
</record>
```

**CORRECT:**
```xml
<record id="library_book_borrow_wizard_action" model="ir.actions.act_window">
    <field name="name">Borrow Book</field>
    <field name="res_model">library.book.borrow.wizard</field>
    <field name="view_mode">form</field>
    <field name="target">new</field>
    <field name="context">{'default_book_id': active_id}</field>
</record>
```

**Why:** `target="new"` opens the wizard in a modal dialog. Without it, the wizard opens as a full page, which is confusing for a transient operation. Use `context` to pass the active record ID.

### Launch wizard from a button on the parent model's form

**CORRECT:**
```xml
<!-- In the library.book form view -->
<button name="%(library_book_borrow_wizard_action)d"
        string="Borrow"
        type="action"
        class="btn-primary"
        invisible="state != 'available'"/>
```

**Why:** `type="action"` with `name="%(action_xml_id)d"` launches the referenced window action. The `%()d` syntax resolves the XML ID to a database ID. The `active_id` context is automatically set to the current record.

### Launch wizard from server action (for list view multi-select)

**CORRECT:**
```xml
<record id="library_book_action_mass_borrow" model="ir.actions.server">
    <field name="name">Mass Borrow</field>
    <field name="model_id" ref="model_library_book"/>
    <field name="binding_model_id" ref="model_library_book"/>
    <field name="binding_view_types">list</field>
    <field name="state">code</field>
    <field name="code">
action = {
    'type': 'ir.actions.act_window',
    'name': 'Mass Borrow',
    'res_model': 'library.book.borrow.wizard',
    'view_mode': 'form',
    'target': 'new',
    'context': {'active_ids': env.context.get('active_ids', [])},
}
    </field>
</record>
```

**Why:** This creates an entry in the "Action" dropdown on list views. When the user selects multiple records and clicks the action, `active_ids` is passed to the wizard via context.

---

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| `TransientModel` | Same | Same, unchanged | Auto-cleanup still default 1 hour |
| View modifiers | `attrs="{'invisible': ...}"` | `invisible="expression"` | Use inline expressions in wizard views too |
| `special="cancel"` | Available | Same, unchanged | Still the standard way to close wizard |
| Context passing | `active_id`/`active_ids` | Same, unchanged | Standard context keys |

---

## Common Mistakes

### Wizard fields referencing wrong model

If the wizard is for `library.book` records, the `book_id` field must be `Many2one("library.book")`, not `Many2one("library.member")`. Verify the `comodel_name` matches the intended parent model.

### Not passing context when launching wizard

If the wizard expects `active_id` or `active_ids` in context but the launching action does not pass them, `default_get` receives empty context and the wizard has no records to operate on.

### Forgetting `special="cancel"` on the cancel button

Without `special="cancel"`, the cancel button does nothing. It must have `special="cancel"` to close the dialog. Do NOT use `type="object"` with a method that does nothing -- that wastes a server round-trip.

### Using `models.Model` instead of `models.TransientModel`

Wizard data is ephemeral. Using `models.Model` creates permanent records in the database that accumulate indefinitely. Always use `models.TransientModel` for wizards.

### Not using `ensure_one()` in the action method

Without `ensure_one()`, if the wizard somehow has multiple records in the recordset, the action method may produce unexpected results or silently process only the first record.

## Changed in 19.0

No breaking changes to wizards in 19.0. `TransientModel`, `default_get` patterns, `target="new"`, `special="cancel"`, and `ensure_one()` all work the same as in 18.0. Wizard views should adopt 19.0 QWeb changes where applicable (use `t-out` instead of `t-esc`).

---
*Odoo 17.0/18.0/19.0 Wizards -- loaded by wizard generation agents*
