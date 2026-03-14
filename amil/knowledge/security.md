# Odoo 17.0/18.0/19.0 Security Rules

> Loaded alongside MASTER.md. Covers module categories, security groups,
> access control lists, record rules, and data load order.

## Module Category

Every module that defines security groups should first define a module category:

```xml
<!-- security/security.xml -->
<odoo>
    <record id="module_category_library" model="ir.module.category">
        <field name="name">Library</field>
        <field name="sequence">100</field>
    </record>
</odoo>
```

**Why:** Categories group security groups in Settings > Users. Without a category, groups appear under "Other" -- confusing for administrators.

## Security Groups

### Standard two-group hierarchy: User and Manager

```xml
<record id="group_library_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_library"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
</record>

<record id="group_library_manager" model="res.groups">
    <field name="name">Manager</field>
    <field name="category_id" ref="module_category_library"/>
    <field name="implied_ids" eval="[(4, ref('group_library_user'))]"/>
</record>
```

### Always chain groups with `implied_ids`

**WRONG -- flat hierarchy:**
```xml
<record id="group_library_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_library"/>
</record>

<record id="group_library_manager" model="res.groups">
    <field name="name">Manager</field>
    <field name="category_id" ref="module_category_library"/>
</record>
```

**CORRECT -- chained hierarchy:**
```xml
<record id="group_library_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_library"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
</record>

<record id="group_library_manager" model="res.groups">
    <field name="name">Manager</field>
    <field name="category_id" ref="module_category_library"/>
    <field name="implied_ids" eval="[(4, ref('group_library_user'))]"/>
</record>
```

**Why:** Without `implied_ids`, Managers do NOT automatically inherit User permissions. An admin must manually assign both groups to each Manager user. The chain ensures Manager includes all User rights.

### User group inherits from `base.group_user`

**WRONG:**
```xml
<record id="group_library_user" model="res.groups">
    <field name="name">User</field>
</record>
```

**CORRECT:**
```xml
<record id="group_library_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_library"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
</record>
```

**Why:** Inheriting from `base.group_user` ensures your module's User group is automatically assigned to all internal users. Without it, no one has access by default.

## Access Control Lists (ACLs)

### CSV format: `ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_library_book_user,library.book.user,model_library_book,group_library_user,1,1,1,0
access_library_book_manager,library.book.manager,model_library_book,group_library_manager,1,1,1,1
```

### Column reference

| Column | Description | Example |
|--------|-------------|---------|
| `id` | External ID for the ACL record | `access_library_book_user` |
| `name` | Human-readable name | `library.book.user` |
| `model_id:id` | Model external ID | `model_library_book` |
| `group_id:id` | Group external ID | `group_library_user` |
| `perm_read` | Read permission (0/1) | `1` |
| `perm_write` | Write permission (0/1) | `1` |
| `perm_create` | Create permission (0/1) | `1` |
| `perm_unlink` | Delete permission (0/1) | `0` (user) / `1` (manager) |

### Model reference format: dots become underscores

**WRONG:**
```csv
access_library_book_user,library.book.user,model_library.book,group_library_user,1,1,1,0
```

**CORRECT:**
```csv
access_library_book_user,library.book.user,model_library_book,group_library_user,1,1,1,0
```

**Why:** The model external ID replaces dots with underscores and adds the `model_` prefix. `library.book` becomes `model_library_book`. Using dots causes "External ID not found" error.

### Standard permission patterns

| Group | Read | Write | Create | Unlink |
|-------|------|-------|--------|--------|
| User | 1 | 1 | 1 | 0 |
| Manager | 1 | 1 | 1 | 1 |

User can read, write, and create. Only Manager can delete. This is the standard OCA pattern.

### Every model MUST have an ACL entry

**WRONG:** Model exists but no ACL defined for it.

**CORRECT:** Every model declared in `models/` has at least one row in `ir.model.access.csv`.

**Why:** pylint-odoo W8180 flags missing access rights. Without ACLs, only the admin user can see the model's records. All other users get "Access Denied".

## Record Rules

### Multi-company record rule

```xml
<record id="library_book_company_rule" model="ir.rule">
    <field name="name">Library Book: Multi-Company</field>
    <field name="model_id" ref="model_library_book"/>
    <field name="domain_force">[
        '|',
        ('company_id', '=', False),
        ('company_id', 'in', company_ids),
    ]</field>
    <field name="global" eval="True"/>
</record>
```

### User-specific record rule

```xml
<record id="library_book_user_rule" model="ir.rule">
    <field name="name">Library Book: Own Records Only</field>
    <field name="model_id" ref="model_library_book"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('group_library_user'))]"/>
</record>
```

- `global="True"`: applies to ALL users (even admin)
- No `global` + `groups` specified: applies only to users in those groups
- Manager group typically gets no restrictive record rule (inherits full access)

### Record rule domain uses `user` and `company_ids`

**WRONG:**
```xml
<field name="domain_force">[('company_id', '=', user.company_id)]</field>
```

**CORRECT:**
```xml
<field name="domain_force">[
    '|',
    ('company_id', '=', False),
    ('company_id', 'in', company_ids),
]</field>
```

**Why:** Users can belong to multiple companies. Use `company_ids` (list) not `user.company_id` (single). Include `('company_id', '=', False)` for records without a company.

## Common Mistakes

1. **Missing ACL for a model** -- Every model needs at least one `ir.model.access.csv` entry (W8180)
2. **Wrong model reference in CSV** -- Use `model_library_book` not `model_library.book`
3. **Flat group hierarchy** -- Manager must inherit from User via `implied_ids`
4. **Groups defined AFTER ACLs in manifest** -- Load security XML before CSV (see Data Load Order)
5. **Missing `category_id` on groups** -- Groups without category appear under "Other" in Settings
6. **No `base.group_user` implied** -- User group must inherit from internal user group
7. **ACL without group** -- An ACL row with empty `group_id:id` grants access to ALL users including portal

## Data Load Order

In `__manifest__.py`, security files must be loaded in the correct order:

**WRONG:**
```python
"data": [
    "security/ir.model.access.csv",  # ACLs loaded before groups exist
    "security/security.xml",
    "views/library_book_views.xml",
]
```

**CORRECT:**
```python
"data": [
    "security/security.xml",         # Groups defined first
    "security/ir.model.access.csv",  # ACLs reference groups
    "views/library_book_views.xml",  # Views reference groups for visibility
]
```

**Why:** ACLs reference group external IDs. If the CSV is loaded before the XML that defines groups, Odoo throws "External ID not found" for the group references.

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| Record rule context | `user.company_id` | `company_ids` available | Multi-company improved |
| Group visibility | Basic category | Same pattern | No breaking changes |

## pylint-odoo Rules

| Rule | Trigger | Fix |
|------|---------|-----|
| **W8180** | Missing access rights for a model | Add ACL rows in `ir.model.access.csv` for every model |

## Changed in 19.0

| What Changed | Before (18.0) | Now (19.0) | Impact |
|-------------|---------------|------------|--------|
| Security groups `category_id` | Used to associate groups with module categories | **Replaced** by `privilege_id` | **Breaking** -- group XML using `category_id` must use `privilege_id` instead |
| ACLs and record rules | Same format | Same, unchanged | No breaking changes |

### Security groups: `category_id` replaced by `privilege_id`

**WRONG (19.0):**
```xml
<record id="group_library_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_library"/>
</record>
```

**CORRECT (19.0):**
```xml
<record id="group_library_user" model="res.groups">
    <field name="name">User</field>
    <field name="privilege_id" ref="module_category_library"/>
</record>
```

**Why:** Odoo 19 replaced `category_id` with `privilege_id` on `res.groups` for a clearer privilege-based security model. Existing group definitions using `category_id` must be updated.

---
*Odoo 17.0/18.0/19.0 Security -- loaded by security generation agents*
