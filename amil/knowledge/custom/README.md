# Custom Knowledge Base Rules

This directory extends the shipped Odoo 17.0 knowledge base with your team-specific rules and conventions.

## Purpose

Custom rules let you enforce project-specific patterns that go beyond the standard Odoo and OCA conventions. For example:

- Company naming conventions for modules and models
- Required fields on every model (e.g., `company_id` for multi-company)
- Preferred field types or widget assignments
- Project-specific security group structures

## How It Works

1. Agents load the shipped knowledge base in this order:
   - `MASTER.md` (global Odoo 17.0 conventions)
   - Category file (e.g., `models.md`, `views.md`)
   - **Matching custom file** (e.g., `custom/models.md`, `custom/views.md`)

2. Custom rules **extend** the defaults. They never override shipped rules.

3. If no matching custom file exists, agents use only the shipped rules.

## File Naming

Name your custom files to match the shipped category files:

| Custom File           | Extends           | Applies To              |
|-----------------------|-------------------|-------------------------|
| `custom/models.md`    | `models.md`       | Model generation        |
| `custom/views.md`     | `views.md`        | View generation         |
| `custom/security.md`  | `security.md`     | Security generation     |
| `custom/testing.md`   | `testing.md`      | Test generation         |
| `custom/manifest.md`  | `manifest.md`     | Manifest generation     |
| `custom/actions.md`   | `actions.md`      | Action/menu generation  |
| `custom/data.md`      | `data.md`         | Data file generation    |
| `custom/i18n.md`      | `i18n.md`         | Translation handling    |
| `custom/controllers.md` | `controllers.md` | Controller generation |
| `custom/wizards.md`   | `wizards.md`      | Wizard generation       |
| `custom/inheritance.md` | `inheritance.md` | Inheritance patterns   |

You can also create files that do not match a shipped category. These are loaded only if an agent explicitly references them.

## Format Requirements

Every custom rule file must follow the **Rule + WRONG + CORRECT + Why** format:

```markdown
# Custom Model Rules

### Rule: Always include company_id on business models

WRONG:
```python
class ProjectTask(models.Model):
    _name = 'project.task'
    name = fields.Char(required=True)
```

CORRECT:
```python
class ProjectTask(models.Model):
    _name = 'project.task'
    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
```

**Why:** Multi-company environments require company_id for record rule isolation.
```

### Structural requirements

- File must start with a `#` heading
- At least one rule section (heading starting with `### `)
- At least one code block (triple backticks)
- Maximum 500 lines per file
- All code blocks must be properly closed

## Validation

Validate your custom rule files before use:

```bash
# Validate custom/ directory (default)
amil-utils validate-kb

# Validate only custom/ directory (explicit)
amil-utils validate-kb --custom

# Validate all knowledge base files (shipped + custom)
amil-utils validate-kb --all
```

The validator checks **format only** (headings, code blocks, line count). It does not validate the semantic correctness of your rules.

## Example

Create `custom/models.md` with your team's conventions:

```markdown
# Custom Model Conventions

### Rule: Use tracking=True on all status fields

WRONG:
```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('done', 'Done'),
], default='draft')
```

CORRECT:
```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('done', 'Done'),
], default='draft', tracking=True)
```

**Why:** Status changes must appear in the chatter for audit trail compliance.

### Rule: Always set _order on models with a date field

WRONG:
```python
class SaleReport(models.Model):
    _name = 'sale.report'
    date = fields.Date()
```

CORRECT:
```python
class SaleReport(models.Model):
    _name = 'sale.report'
    _order = 'date desc, id desc'
    date = fields.Date()
```

**Why:** Without explicit ordering, records appear in ID order which is rarely useful for date-based models.
```

## Tips

- Keep custom files focused and concise (under 500 lines)
- Use the same `### Rule:` prefix for consistency with shipped rules
- Test your rules by running `amil-utils validate-kb --custom` after editing
- Custom rules are version-controlled with your project -- commit them alongside your code
