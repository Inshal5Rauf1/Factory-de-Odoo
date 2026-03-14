# Odoo 17.0/18.0/19.0 Manifest Rules

> Loaded alongside MASTER.md. Covers `__manifest__.py` required keys, version format,
> license, forbidden keys, data/demo lists, dependencies, and application flag.

## Required Keys

Every `__manifest__.py` MUST include these keys:

```python
{
    "name": "Library Management",
    "version": "17.0.1.0.0",
    "category": "Services",
    "summary": "Manage library books, members, and borrowing",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/library_book_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
}
```

### Missing `name` or `summary`

**WRONG:**
```python
{
    "version": "17.0.1.0.0",
    "depends": ["base"],
}
```

**CORRECT:**
```python
{
    "name": "Library Management",
    "summary": "Manage library books and borrowing operations",
    "version": "17.0.1.0.0",
    "depends": ["base"],
    "license": "LGPL-3",
    "installable": True,
}
```

**Why:** `name` is the display name in Apps. `summary` is the one-line description shown below it. Without them, the module is invisible or confusing in the Apps list.

## Version Format

**Pattern:** `17.0.X.Y.Z` (5-part)

| Part | Meaning | Range |
|------|---------|-------|
| `17.0` | Odoo version | Fixed for Odoo 17 |
| `X` | Major module version | 1+ |
| `Y` | Minor (new features) | 0+ |
| `Z` | Patch (bugfixes) | 0+ |

### Use 5-part version, not 3-part

**WRONG:**
```python
"version": "1.0.0",
```

**CORRECT:**
```python
"version": "17.0.1.0.0",
```

**Why:** pylint-odoo C8108 flags invalid version format. The Odoo version prefix (`17.0.`) is required so OCA tools can identify which Odoo version the module targets. Without it, the module cannot be published to the OCA repository.

## License

### `license` is REQUIRED (pylint-odoo E8501)

**WRONG:**
```python
{
    "name": "My Module",
    "version": "17.0.1.0.0",
    # No license key
}
```

**CORRECT:**
```python
{
    "name": "My Module",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
}
```

**Why:** pylint-odoo E8501 (error-level) flags missing license. Odoo requires it for module identification. OCA modules use `"LGPL-3"`.

### Valid license values

| License | When to Use |
|---------|-------------|
| `"LGPL-3"` | OCA community modules (default) |
| `"GPL-3"` | Strong copyleft required |
| `"AGPL-3"` | Network copyleft (SaaS protection) |
| `"OEEL-1"` | Odoo Enterprise proprietary |
| `"Other proprietary"` | Custom proprietary modules |

## Forbidden/Deprecated Keys

### Do NOT use `description` key

**WRONG:**
```python
{
    "name": "My Module",
    "description": """
    This module does X, Y, and Z.
    It provides features for...
    """,
}
```

**CORRECT:**
```python
{
    "name": "My Module",
    "summary": "Short one-line description",
    # Long description goes in README.rst, NOT in manifest
}
```

**Why:** pylint-odoo C8101 flags `description` key in manifest. OCA standard requires long descriptions in `README.rst` (or `README.md`), not in the manifest. The manifest `summary` provides the one-liner.

### Avoid `auto_install` unless truly needed

**WRONG:**
```python
{
    "name": "My Module",
    "auto_install": True,  # Auto-installs when dependencies are met
}
```

**CORRECT:**
```python
{
    "name": "My Module",
    "auto_install": False,  # Or simply omit -- False is default
}
```

**Why:** `auto_install: True` causes the module to install automatically whenever ALL its dependencies are present. This is only appropriate for glue modules (e.g., `sale_stock` that bridges `sale` and `stock`). For standalone modules, it causes unexpected installs.

## Data and Demo Lists

### Correct file paths and load order

```python
"data": [
    # 1. Security (groups first, then ACLs)
    "security/security.xml",
    "security/ir.model.access.csv",
    # 2. Data files (sequences, defaults)
    "data/ir_sequence_data.xml",
    # 3. Views and actions
    "views/library_book_views.xml",
    "views/library_member_views.xml",
    "views/menu.xml",
],
"demo": [
    "demo/demo_data.xml",
],
```

### Load order matters

**WRONG:**
```python
"data": [
    "views/library_book_views.xml",    # Views reference groups
    "security/ir.model.access.csv",    # ACLs reference groups
    "security/security.xml",           # Groups defined last -- too late
]
```

**CORRECT:**
```python
"data": [
    "security/security.xml",           # 1. Groups defined first
    "security/ir.model.access.csv",    # 2. ACLs reference groups
    "views/library_book_views.xml",    # 3. Views reference groups
]
```

**Why:** Odoo loads data files in order. If views or ACLs reference security groups that haven't been loaded yet, installation fails with "External ID not found".

### Demo data is separate from data

- `data`: Loaded on every install (production + development)
- `demo`: Loaded only when "Load demo data" is enabled (development only)
- Never put demo records in `data` -- they cannot be removed from production

## Dependencies

### Explicit is better than implicit

**WRONG:**
```python
"depends": ["sale"],
# Uses res.partner fields but doesn't declare 'base' or 'contacts'
```

**CORRECT:**
```python
"depends": ["sale", "contacts"],
# Explicitly depends on everything it uses
```

**Why:** While `base` is always implicitly available, other transitive dependencies are not guaranteed. If your module uses `res.partner` fields added by `contacts`, declare it. Explicit dependencies prevent breakage when the dependency chain changes.

### `base` is always implicit

You do NOT need to list `base` in `depends` -- it is always installed. However, listing it explicitly is harmless and makes dependencies clearer.

### Only list direct dependencies

**WRONG:**
```python
"depends": ["sale", "account", "base", "mail", "product"],
# account and product are already dependencies of sale
```

**CORRECT:**
```python
"depends": ["sale", "mail"],
# sale already pulls in account and product
```

**Why:** Listing transitive dependencies clutters the manifest and creates unnecessary coupling. Only list modules your code directly imports from or references.

## Application Flag

### When to set `application: True`

```python
"application": True,  # Only for top-level application modules
```

Set `application: True` when:
- The module is a standalone application (not a plugin/extension)
- It should appear in the main Apps list
- It creates a top-level menu entry

**Do NOT set** for:
- Modules that extend existing apps
- Library/utility modules
- Glue modules that bridge two apps

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| License enforcement | Warning | Error in pylint-odoo | E8501 is error-level |
| `description` key | Discouraged | Flagged by C8101 | Use README.rst |
| Version prefix | `16.0.X.Y.Z` | `17.0.X.Y.Z` | Update on migration |

## pylint-odoo Rules

| Rule | Level | Trigger | Fix |
|------|-------|---------|-----|
| **E8501** | Error | Missing `license` in manifest | Add `"license": "LGPL-3"` |
| **C8101** | Convention | `description` key in manifest | Remove; use README.rst |
| **C8104** | Convention | Empty `depends` list | Add at least `["base"]` |
| **C8108** | Convention | Invalid version format | Use `17.0.X.Y.Z` (5-part) |

## Changed in 18.0

| What Changed | Before (17.0) | Now (18.0) | Impact |
|-------------|---------------|------------|--------|
| Version prefix | `17.0.X.Y.Z` | `18.0.X.Y.Z` | Update on migration |
| Structural format | No changes | Same manifest structure | No breaking changes |

### Version prefix is `18.0.X.Y.Z`

**WRONG (18.0 module with 17.0 prefix):**
```python
"version": "17.0.1.0.0",
```

**CORRECT (18.0):**
```python
"version": "18.0.1.0.0",
```

**Why:** The Odoo version prefix must match the target Odoo version. OCA tools use the prefix to identify which Odoo version the module targets. Mismatched prefixes prevent publishing and may cause compatibility warnings.

### No structural manifest changes in 18.0

The `__manifest__.py` format is identical between 17.0 and 18.0. All required keys (`name`, `version`, `license`, `depends`, `data`, `installable`) remain the same. The only change is the version prefix number.

## Changed in 19.0

| What Changed | Before (18.0) | Now (19.0) | Impact |
|-------------|---------------|------------|--------|
| Version prefix | `18.0.X.Y.Z` | `19.0.X.Y.Z` | Update on migration |
| Structural format | No changes | Same manifest structure | No breaking changes |

### Version prefix is `19.0.X.Y.Z`

**WRONG (19.0 module with 18.0 prefix):**
```python
"version": "18.0.1.0.0",
```

**CORRECT (19.0):**
```python
"version": "19.0.1.0.0",
```

**Why:** The Odoo version prefix must match the target Odoo version. OCA tools use the prefix to identify which Odoo version the module targets. Mismatched prefixes prevent publishing and may cause compatibility warnings.

### No structural manifest changes in 19.0

The `__manifest__.py` format is identical between 18.0 and 19.0. All required keys (`name`, `version`, `license`, `depends`, `data`, `installable`) remain the same. The only change is the version prefix number.

---
*Odoo 17.0/18.0/19.0 Manifest -- loaded by scaffold and generation agents*
