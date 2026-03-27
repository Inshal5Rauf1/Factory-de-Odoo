# Odoo 17.0/18.0/19.0 Data Files Rules

> Category: Data | Target: Odoo 17.0/18.0/19.0 | Load with: MASTER.md + data.md

## Data Files (`data/`)

### Define sequences with `ir.sequence`

**WRONG:**
```xml
<record id="seq_library_book" model="ir.sequence">
    <field name="name">Library Book</field>
    <!-- Missing code, prefix, and padding -->
</record>
```

**CORRECT:**
```xml
<record id="seq_library_book" model="ir.sequence">
    <field name="name">Library Book</field>
    <field name="code">library.book</field>
    <field name="prefix">LIB/%(year)s/</field>
    <field name="padding">5</field>
    <field name="number_next">1</field>
    <field name="number_increment">1</field>
</record>
```

**Why:** `code` links the sequence to the model (used in `self.env["ir.sequence"].next_by_code("library.book")`). `prefix` with `%(year)s` generates year-based references like `LIB/2024/00001`. `padding` controls zero-fill width.

### Define scheduled actions with `ir.cron`

**WRONG:**
```xml
<record id="cron_cleanup" model="ir.cron">
    <field name="name">Cleanup</field>
    <field name="model_id" ref="model_library_book"/>
    <!-- Missing interval, method, and active -->
</record>
```

**CORRECT:**
```xml
<record id="cron_library_overdue_check" model="ir.cron">
    <field name="name">Library: Check Overdue Books</field>
    <field name="model_id" ref="model_library_book"/>
    <field name="state">code</field>
    <field name="code">model._cron_check_overdue()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="numbercall">-1</field>
    <field name="active">True</field>
</record>
```

**Why:** `interval_number` + `interval_type` set the schedule. `numbercall=-1` means run indefinitely. `state="code"` with `code` calls a model method. Prefix the cron name with module name for clarity.

### Define email templates with `mail.template`

**CORRECT:**
```xml
<record id="email_template_book_borrowed" model="mail.template">
    <field name="name">Library: Book Borrowed Notification</field>
    <field name="model_id" ref="model_library_book"/>
    <field name="subject">Book Borrowed: {{ object.name }}</field>
    <field name="email_from">{{ (object.company_id.email or user.email) }}</field>
    <field name="email_to">{{ object.borrower_id.email }}</field>
    <field name="body_html" type="html">
        <p>Dear {{ object.borrower_id.name }},</p>
        <p>You have borrowed <strong>{{ object.name }}</strong>.</p>
        <p>Please return it by {{ object.return_date }}.</p>
    </field>
</record>
```

**Why:** Email templates use Jinja2-style expressions (`{{ object.field }}`). `object` refers to the record. Always set `model_id` so the template knows which model's fields are available.

---

## Demo Data (`demo/`)

### Use `noupdate="1"` on demo data records

**WRONG:**
```xml
<odoo>
    <!-- Missing noupdate -- records will be overwritten on module update -->
    <record id="demo_book_1" model="library.book">
        <field name="name">Demo Book</field>
    </record>
</odoo>
```

**CORRECT:**
```xml
<odoo noupdate="1">
    <record id="demo_book_1" model="library.book">
        <field name="name">The Great Library</field>
        <field name="isbn">9780123456789</field>
        <field name="state">available</field>
        <field name="publisher_id" ref="base.res_partner_1"/>
    </record>

    <record id="demo_book_2" model="library.book">
        <field name="name">Advanced Cataloging</field>
        <field name="isbn">9780987654321</field>
        <field name="state">draft</field>
    </record>
</odoo>
```

**Why:** `noupdate="1"` prevents demo records from being overwritten when the module is updated. Users may modify demo records; overwriting them would lose changes. Reference existing demo records (like `base.res_partner_1`) instead of creating unnecessary partners.

### Place demo data files in `demo/` directory and list in manifest `demo` key

**WRONG:**
```python
# __manifest__.py
{
    "data": [
        "demo/demo_data.xml",  # Demo data in 'data' key
    ],
}
```

**CORRECT:**
```python
# __manifest__.py
{
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/library_book_views.xml",
        "data/sequence.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
```

**Why:** The `demo` key is separate from `data`. Demo files are only loaded when "Load demo data" is checked during database creation. Putting demo data in `data` loads it in production databases.

---

## XML Data Format

### Use `<record>` tag with `<field>` elements

**WRONG:**
```xml
<library.book id="demo_book">
    <name>Test</name>
</library.book>
```

**CORRECT:**
```xml
<record id="demo_book_1" model="library.book">
    <field name="name">Test Book</field>
    <field name="active" eval="True"/>
    <field name="page_count" eval="350"/>
</record>
```

**Why:** The `<record>` tag is the standard way to define data records. Use `name` attribute on `<field>` for the field name. Use `eval` for non-string values (booleans, integers, expressions).

### Use `ref` for Many2one references and `eval` for Many2many

**WRONG:**
```xml
<field name="publisher_id">1</field>
<field name="author_ids">[1, 2, 3]</field>
```

**CORRECT:**
```xml
<!-- Many2one: use ref attribute -->
<field name="publisher_id" ref="base.res_partner_1"/>

<!-- Many2many: use eval with command tuples -->
<field name="author_ids" eval="[
    (4, ref('base.res_partner_1')),
    (4, ref('base.res_partner_2')),
]"/>
```

**Why:** `ref="xml_id"` resolves the external ID to a database ID for Many2one fields. For Many2many, use `eval` with command tuples: `(4, id)` adds a link, `(6, 0, [ids])` replaces all links.

### Many2many command reference

| Command | Meaning |
|---------|---------|
| `(4, id)` | Add link to existing record |
| `(3, id)` | Remove link (does not delete record) |
| `(6, 0, [ids])` | Replace all links with given list |
| `(5, 0, 0)` | Remove all links |

---

## CSV Data Format

### Use CSV for `ir.model.access` (ACLs)

**CORRECT:**
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_library_book_user,library.book.user,model_library_book,library.group_library_user,1,1,1,0
access_library_book_manager,library.book.manager,model_library_book,library.group_library_manager,1,1,1,1
```

**Why:** ACLs are traditionally defined in CSV because the tabular format maps naturally to the permission matrix. The CSV must be named `ir.model.access.csv` and placed in the `security/` directory.

### When to use CSV vs XML

| Format | Use For | Why |
|--------|---------|-----|
| CSV | ACLs (`ir.model.access`) | Tabular data, one row per rule |
| XML | Everything else (sequences, cron, views, groups) | Structured data with nested elements |

---

## Load Order in Manifest

### Order `data` list: security groups -> ACLs -> data files -> views

**WRONG:**
```python
"data": [
    "views/library_book_views.xml",
    "security/ir.model.access.csv",  # ACLs AFTER views -- groups not yet defined
    "security/security.xml",         # Groups AFTER ACLs -- order broken
]
```

**CORRECT:**
```python
"data": [
    "security/security.xml",          # 1. Groups and categories FIRST
    "security/ir.model.access.csv",   # 2. ACLs reference groups
    "data/sequence.xml",              # 3. Data records
    "views/library_book_views.xml",   # 4. Views reference models and data
    "views/library_book_menus.xml",   # 5. Menus reference actions
]
```

**Why:** Odoo loads data files in the order listed in `data`. Groups must exist before ACLs reference them. ACLs must exist before views try to check permissions. Wrong order causes `ValueError: External ID not found` during installation.

---

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| Email template syntax | `${object.name}` (Mako) | `{{ object.name }}` (Jinja2) | Jinja2 is default in 17.0 |
| `noupdate` attribute | Same | Same, unchanged | Always use for demo/config data |
| Data file loading | Same `data` key | Same, unchanged | Load order matters |

---

## Common Mistakes

### Referencing records from uninstalled modules

Using `ref("sale.product_category_1")` when your module does not depend on `sale` causes an error during installation. Always ensure the referenced module is in your `depends` list.

### Forgetting `noupdate` on configuration data

Configuration records (system parameters, default settings) should use `noupdate="1"` so that user customizations survive module updates.

### Wrong `eval` syntax

Using `eval="True"` (capital T, Python boolean) is correct. Using `eval="true"` (lowercase) evaluates to a variable name and raises `NameError`. For integers, `eval="42"` is correct; `<field>42</field>` would be a string `"42"`.

## Changed in 19.0

No breaking changes to data file format in 19.0. Sequences (`ir.sequence`), email templates (`mail.template`), cron jobs (`ir.cron`), and demo data patterns remain the same as in 18.0. Note that `ir.cron` `numbercall` was already removed in 18.0 -- this remains absent in 19.0.

---
*Odoo 17.0/18.0/19.0 Data Files -- loaded by data generation agents*
