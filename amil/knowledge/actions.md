# Odoo 17.0/18.0/19.0 Actions & Menus Rules

> Category: Actions | Target: Odoo 17.0/18.0/19.0 | Load with: MASTER.md + actions.md

## Window Actions

### Define `ir.actions.act_window` with required fields

**WRONG:**
```xml
<record id="action_library_book" model="ir.actions.act_window">
    <field name="name">Books</field>
    <!-- Missing res_model and view_mode -->
</record>
```

**CORRECT:**
```xml
<record id="library_book_action" model="ir.actions.act_window">
    <field name="name">Books</field>
    <field name="res_model">library.book</field>
    <field name="view_mode">tree,form</field>
</record>
```

**Why:** `name`, `res_model`, and `view_mode` are the minimum required fields. Without `res_model`, the action has no model to operate on. Without `view_mode`, Odoo cannot render the views.

### Use `tree,form` (not `list,form`) in view_mode for Odoo 17.0

**WRONG:**
```xml
<field name="view_mode">list,form</field>
```

**CORRECT:**
```xml
<field name="view_mode">tree,form</field>
```

**Why:** In Odoo 17.0, `view_mode` uses `tree` for list views. The `list` keyword is only valid in Odoo 18+. Using `list` in 17.0 causes a view resolution error.

### Add domain and context for filtered/contextualized actions

**CORRECT:**
```xml
<record id="library_book_action_available" model="ir.actions.act_window">
    <field name="name">Available Books</field>
    <field name="res_model">library.book</field>
    <field name="view_mode">tree,form</field>
    <field name="domain">[('state', '=', 'available')]</field>
    <field name="context">{'default_state': 'available'}</field>
</record>
```

**Why:** `domain` filters the list view. `context` sets default values when creating new records from this action. Use `default_` prefix in context for default field values.

### Use `search_view_id` to bind a specific search view

**CORRECT:**
```xml
<record id="library_book_action" model="ir.actions.act_window">
    <field name="name">Books</field>
    <field name="res_model">library.book</field>
    <field name="view_mode">tree,form</field>
    <field name="search_view_id" ref="library_book_view_search"/>
</record>
```

---

## Server Actions

### Define `ir.actions.server` for code execution

**WRONG:**
```xml
<record id="action_mark_borrowed" model="ir.actions.server">
    <field name="name">Mark as Borrowed</field>
    <!-- Missing model_id, state, and code -->
</record>
```

**CORRECT:**
```xml
<record id="library_book_action_mark_borrowed" model="ir.actions.server">
    <field name="name">Mark as Borrowed</field>
    <field name="model_id" ref="model_library_book"/>
    <field name="state">code</field>
    <field name="code">
for record in records:
    record.action_borrow()
    </field>
    <field name="binding_model_id" ref="model_library_book"/>
    <field name="binding_view_types">list,form</field>
</record>
```

**Why:** Server actions require `model_id`, `state` (usually `"code"`), and `code`. Use `binding_model_id` to make the action appear in the model's "Action" dropdown menu.

### Use `records` variable (not `object`) in server action code

**WRONG:**
```xml
<field name="code">
object.write({'state': 'done'})
</field>
```

**CORRECT:**
```xml
<field name="code">
for record in records:
    record.write({'state': 'done'})
</field>
```

**Why:** In Odoo 17.0, server action code receives `records` (a recordset) as the variable. The old `object` variable is deprecated. Always iterate over `records`.

---

## Menu Hierarchy

### Define root menu, category menu, and action menu

**WRONG:**
```xml
<!-- Orphan menu with no parent and no action -->
<menuitem id="menu_books" name="Books"/>
```

**CORRECT:**
```xml
<!-- 1. Root menu (app-level, no parent, no action) -->
<menuitem id="menu_library_root"
          name="Library"
          sequence="100"/>

<!-- 2. Category menu (groups related items) -->
<menuitem id="menu_library_catalog"
          name="Catalog"
          parent="menu_library_root"
          sequence="10"/>

<!-- 3. Action menu (opens a view) -->
<menuitem id="menu_library_book"
          name="Books"
          parent="menu_library_catalog"
          action="library_book_action"
          sequence="10"/>
```

**Why:** Odoo menus are hierarchical: root menu (appears in top bar) -> category menu (appears in sidebar) -> action menu (opens a view). Every leaf menu must have an `action` reference. Orphan menus (no parent, no action) cause navigation errors.

### Use `sequence` to control menu ordering

**WRONG:**
```xml
<menuitem id="menu_authors" name="Authors" parent="menu_library_catalog"/>
<menuitem id="menu_books" name="Books" parent="menu_library_catalog"/>
<!-- Order depends on XML ID alphabetical, unreliable -->
```

**CORRECT:**
```xml
<menuitem id="menu_library_book"
          name="Books"
          parent="menu_library_catalog"
          sequence="10"/>
<menuitem id="menu_library_author"
          name="Authors"
          parent="menu_library_catalog"
          sequence="20"/>
```

**Why:** Without `sequence`, menu order depends on load order which is fragile. Explicit `sequence` values ensure consistent ordering. Use increments of 10 to allow insertions.

---

## Action-Model Binding

### Bind an action to a model for the "Action" dropdown

**CORRECT:**
```xml
<record id="library_book_action_archive" model="ir.actions.server">
    <field name="name">Archive Selected</field>
    <field name="model_id" ref="model_library_book"/>
    <field name="binding_model_id" ref="model_library_book"/>
    <field name="binding_view_types">list</field>
    <field name="state">code</field>
    <field name="code">
for record in records:
    record.toggle_active()
    </field>
</record>
```

**Why:** `binding_model_id` makes the action appear in the "Action" dropdown. `binding_view_types` controls where it appears (`list`, `form`, or `list,form`).

---

## URL Actions

### Define `ir.actions.act_url` for external links

**CORRECT:**
```xml
<record id="library_book_action_website" model="ir.actions.act_url">
    <field name="name">Visit Publisher Website</field>
    <field name="url">https://example.com</field>
    <field name="target">new</field>
</record>
```

**Why:** URL actions open external URLs. `target="new"` opens in a new tab. `target="self"` replaces the current page (use cautiously).

---

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| `view_mode` values | `tree` and `list` both work | `tree` is canonical, `list` works but `tree` preferred | Use `tree` consistently |
| Server action variable | `object` (single record) | `records` (recordset) | Iterate with `for record in records:` |
| Binding view types | `binding_view_types` available | Same, unchanged | Use `list,form` or just `list` |
| `<menuitem>` tag | Shorthand available | Same, still valid | Shorthand preferred over `<record>` for menus |

---

## Common Mistakes

### Orphan menus (no action on leaf menu)

Every leaf-level menu item (the deepest in the hierarchy) must reference an action. A menu with no action and no children is an orphan -- clicking it does nothing and confuses users.

### Wrong view_mode value

Using `list` instead of `tree` in Odoo 17.0 `view_mode` causes a view not found error. Always use `tree,form` for the standard list+detail pattern.

### Missing menu sequence

Omitting `sequence` on menus causes unpredictable ordering that changes across module updates. Always specify `sequence` explicitly.

### Action external ID naming

Follow the convention: `{model_underscore}_action` for the primary action. For secondary actions: `{model_underscore}_action_{qualifier}` (e.g., `library_book_action_available`).

## Changed in 19.0

No additional action or menu changes in 19.0 beyond those introduced in 18.0. The `view_mode` values, server action variables, binding types, and menu patterns remain the same as in 18.0 (`list,form` for actions, `records` variable for server actions).

---
*Odoo 17.0/18.0/19.0 Actions & Menus -- loaded by action generation agents*
