"""Academic calendar domain preprocessor for Odoo module generation.

Generates ``academic.year``, ``academic.term``, and ``academic.batch`` model
dicts when ``academic_calendar: true`` is present in the spec.  Configurable
via optional ``academic_config`` dict.

Registered at order=27 (after pakistan_hec=25, before constraints=30).

Phase 50 -- DOMN-03.
"""

from __future__ import annotations

from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.utils.copy import deep_copy_model, has_field as _has_field


# -- String constants for constraint check_body --------------------------------

_YEAR_OVERLAP_CHECK_BODY = """\
for rec in self:
    if not rec.date_start or not rec.date_end:
        continue
    if rec.date_start >= rec.date_end:
        raise ValidationError(
            _("Start date must be before end date.")
        )
    domain = [
        ('id', '!=', rec.id),
        ('company_id', '=', rec.company_id.id),
        ('date_start', '<', rec.date_end),
        ('date_end', '>', rec.date_start),
    ]
    if self.search_count(domain):
        raise ValidationError(
            _("Academic year '%s' overlaps with an existing year.") % rec.name
        )"""

_TERM_OVERLAP_CHECK_BODY = """\
for rec in self:
    if not rec.date_start or not rec.date_end:
        continue
    if rec.date_start >= rec.date_end:
        raise ValidationError(
            _("Term start date must be before end date.")
        )
    year = rec.academic_year_id
    if year:
        if rec.date_start < year.date_start or rec.date_end > year.date_end:
            raise ValidationError(
                _("Term '%s' must be within academic year date range (%s to %s).")
                % (rec.name, year.date_start, year.date_end)
            )
    domain = [
        ('id', '!=', rec.id),
        ('academic_year_id', '=', rec.academic_year_id.id),
        ('date_start', '<', rec.date_end),
        ('date_end', '>', rec.date_start),
    ]
    if self.search_count(domain):
        raise ValidationError(
            _("Term '%s' overlaps with another term in the same academic year.")
            % rec.name
        )"""


# -- String constants for action method check_body ----------------------------

_ACTION_CONFIRM_BODY = """\
\"\"\"Confirm academic year and auto-generate terms.\"\"\"
from datetime import timedelta
self.ensure_one()
if self.term_structure == 'custom':
    return
if self.term_ids:
    return  # Terms already exist
total_days = (self.date_end - self.date_start).days
term_count_map = {'semester': 2, 'trimester': 3, 'quarter': 4}
n_terms = term_count_map.get(self.term_structure, 2)
base_days = total_days // n_terms
vals_list = []
current_start = self.date_start
for i in range(n_terms):
    if i == n_terms - 1:
        term_end = self.date_end
    else:
        term_end = current_start + timedelta(days=base_days)
    vals_list.append({
        'name': "%s - Term %d" % (self.name, i + 1),
        'code': "T%d" % (i + 1),
        'academic_year_id': self.id,
        'date_start': current_start,
        'date_end': term_end,
        'sequence': (i + 1) * 10,
        'company_id': self.company_id.id,
    })
    current_start = term_end
self.env['academic.term'].create(vals_list)"""

_ACTION_ACTIVATE_BODY = """\
\"\"\"Activate the academic year and cascade to draft terms.\"\"\"
self.ensure_one()
self.write({'state': 'active'})
# Cascade: activate draft terms
for term in self.term_ids.filtered(lambda t: t.state == 'draft'):
    term.write({'state': 'active'})"""

_ACTION_CLOSE_BODY = """\
\"\"\"Close the academic year and cascade to all terms and batches.\"\"\"
self.ensure_one()
self.write({'state': 'closed'})
# Cascade: close all terms and their batches
for term in self.term_ids:
    if term.state != 'closed':
        term.write({'state': 'closed'})
    for batch in term.batch_ids:
        if batch.state != 'closed':
            batch.write({'state': 'closed'})"""


# -- Builder functions ---------------------------------------------------------


def _build_academic_year_model(
    default_term_structure: str = "semester",
) -> dict[str, Any]:
    """Build a complete model dict for academic.year."""
    return {
        "name": "academic.year",
        "description": "Academic Year",
        "model_order": "date_start desc",
        "fields": [
            {
                "name": "name",
                "type": "Char",
                "string": "Academic Year",
                "required": True,
                "help": "e.g. 2026-2027",
            },
            {
                "name": "code",
                "type": "Char",
                "string": "Code",
                "required": True,
                "help": "e.g. AY2627",
            },
            {
                "name": "date_start",
                "type": "Date",
                "string": "Start Date",
                "required": True,
                "index": True,
            },
            {
                "name": "date_end",
                "type": "Date",
                "string": "End Date",
                "required": True,
            },
            {
                "name": "term_structure",
                "type": "Selection",
                "string": "Term Structure",
                "required": True,
                "default": default_term_structure,
                "selection": [
                    ("semester", "Semester (2 terms)"),
                    ("trimester", "Trimester (3 terms)"),
                    ("quarter", "Quarter (4 terms)"),
                    ("custom", "Custom"),
                ],
            },
            {
                "name": "company_id",
                "type": "Many2one",
                "comodel_name": "res.company",
                "string": "Company",
                "required": True,
                "index": True,
            },
            {
                "name": "term_ids",
                "type": "One2many",
                "comodel_name": "academic.term",
                "inverse_name": "academic_year_id",
                "string": "Terms",
            },
            {
                "name": "term_count",
                "type": "Integer",
                "string": "Term Count",
                "compute": "_compute_term_count",
                "store": True,
                "depends": ["term_ids"],
            },
            {
                "name": "state",
                "type": "Selection",
                "string": "State",
                "default": "draft",
                "tracking": True,
                "selection": [
                    ("draft", "Draft"),
                    ("active", "Active"),
                    ("closed", "Closed"),
                ],
            },
        ],
        "sql_constraints": [
            {
                "name": "academic_year_code_company_unique",
                "definition": "UNIQUE(code, company_id)",
                "message": "Academic year code must be unique per company.",
            },
        ],
        "complex_constraints": [
            {
                "name": "year_dates",
                "fields": ["date_start", "date_end"],
                "type": "ac_year_overlap",
                "check_body": _YEAR_OVERLAP_CHECK_BODY,
            },
            {
                "name": "action_confirm",
                "fields": ["term_structure"],
                "type": "ac_action_confirm",
                "check_body": _ACTION_CONFIRM_BODY,
            },
            {
                "name": "action_activate",
                "fields": ["state"],
                "type": "ac_action_activate",
                "check_body": _ACTION_ACTIVATE_BODY,
            },
            {
                "name": "action_close",
                "fields": ["state"],
                "type": "ac_action_close",
                "check_body": _ACTION_CLOSE_BODY,
            },
        ],
    }


def _build_academic_term_model() -> dict[str, Any]:
    """Build a complete model dict for academic.term."""
    return {
        "name": "academic.term",
        "description": "Academic Term",
        "model_order": "sequence, date_start",
        "fields": [
            {
                "name": "name",
                "type": "Char",
                "string": "Term Name",
                "required": True,
            },
            {
                "name": "code",
                "type": "Char",
                "string": "Code",
                "required": True,
                "help": "e.g. FA26",
            },
            {
                "name": "academic_year_id",
                "type": "Many2one",
                "comodel_name": "academic.year",
                "string": "Academic Year",
                "required": True,
                "ondelete": "cascade",
                "index": True,
            },
            {
                "name": "date_start",
                "type": "Date",
                "string": "Start Date",
                "required": True,
            },
            {
                "name": "date_end",
                "type": "Date",
                "string": "End Date",
                "required": True,
            },
            {
                "name": "sequence",
                "type": "Integer",
                "string": "Sequence",
                "default": 10,
            },
            {
                "name": "batch_ids",
                "type": "One2many",
                "comodel_name": "academic.batch",
                "inverse_name": "term_id",
                "string": "Batches",
            },
            {
                "name": "batch_count",
                "type": "Integer",
                "string": "Batch Count",
                "compute": "_compute_batch_count",
                "store": True,
                "depends": ["batch_ids"],
            },
            {
                "name": "company_id",
                "type": "Many2one",
                "comodel_name": "res.company",
                "string": "Company",
                "related": "academic_year_id.company_id",
                "store": True,
            },
            {
                "name": "state",
                "type": "Selection",
                "string": "State",
                "default": "draft",
                "selection": [
                    ("draft", "Draft"),
                    ("active", "Active"),
                    ("closed", "Closed"),
                ],
            },
        ],
        "complex_constraints": [
            {
                "name": "term_dates",
                "fields": ["date_start", "date_end"],
                "type": "ac_term_overlap",
                "check_body": _TERM_OVERLAP_CHECK_BODY,
            },
        ],
    }


def _build_academic_batch_model(
    capacity_default: int = 50,
) -> dict[str, Any]:
    """Build a complete model dict for academic.batch."""
    return {
        "name": "academic.batch",
        "description": "Academic Batch",
        "model_order": "name",
        "fields": [
            {
                "name": "name",
                "type": "Char",
                "string": "Batch Name",
                "required": True,
                "help": "e.g. BSCS-2026-A",
            },
            {
                "name": "code",
                "type": "Char",
                "string": "Code",
            },
            {
                "name": "term_id",
                "type": "Many2one",
                "comodel_name": "academic.term",
                "string": "Term",
                "required": True,
                "ondelete": "cascade",
                "index": True,
            },
            {
                "name": "program_id",
                "type": "Many2one",
                "comodel_name": "uni.program",
                "string": "Program",
            },
            {
                "name": "capacity",
                "type": "Integer",
                "string": "Capacity",
                "default": capacity_default,
            },
            {
                "name": "enrolled_count",
                "type": "Integer",
                "string": "Enrolled Count",
                "compute": "_compute_enrolled_count",
                "store": True,
                "depends": [],
            },
            {
                "name": "available_seats",
                "type": "Integer",
                "string": "Available Seats",
                "compute": "_compute_available_seats",
                "store": True,
                "depends": ["capacity", "enrolled_count"],
            },
            {
                "name": "section",
                "type": "Char",
                "string": "Section",
            },
            {
                "name": "company_id",
                "type": "Many2one",
                "comodel_name": "res.company",
                "string": "Company",
                "related": "term_id.company_id",
                "store": True,
            },
            {
                "name": "state",
                "type": "Selection",
                "string": "State",
                "default": "draft",
                "selection": [
                    ("draft", "Draft"),
                    ("active", "Active"),
                    ("closed", "Closed"),
                ],
            },
        ],
    }


# -- Semester linkage injection -----------------------------------------------


def _inject_semester_links(model: dict[str, Any]) -> None:
    """Inject academic_year_id and term_id fields on a semester-aware model.

    Mutates model in-place (caller provides a copy).
    """
    if not _has_field(model, "academic_year_id"):
        model["fields"].append({
            "name": "academic_year_id",
            "type": "Many2one",
            "comodel_name": "academic.year",
            "string": "Academic Year",
            "index": True,
        })
    if not _has_field(model, "term_id"):
        model["fields"].append({
            "name": "term_id",
            "type": "Many2one",
            "comodel_name": "academic.term",
            "string": "Term / Semester",
            "index": True,
        })
    if not _has_field(model, "batch_id"):
        model["fields"].append({
            "name": "batch_id",
            "type": "Many2one",
            "comodel_name": "academic.batch",
            "string": "Batch",
        })
    model["semester_aware"] = True


# -- Main preprocessor --------------------------------------------------------


@register_preprocessor(order=27, name="academic_calendar")
def _process_academic_calendar(spec: dict[str, Any]) -> dict[str, Any]:
    """Generate academic calendar models when ``academic_calendar: true``.

    Generates ``academic.year``, ``academic.term``, and optionally
    ``academic.batch`` model dicts and appends them to the spec's
    ``models`` list.  Injects ``mail`` into spec ``depends`` for
    mail.thread mixin support.

    Returns a new spec dict -- never mutates the input.
    """
    if not spec.get("academic_calendar"):
        return spec

    config = spec.get("academic_config", {})
    default_term = config.get("default_term_structure", "semester")
    enable_batch = config.get("enable_batch", True)
    capacity_default = config.get("batch_capacity_default", 50)

    # Deep-copy existing models and inject semester linkage where requested
    new_models = []
    for model in spec.get("models", []):
        if model.get("semester_aware"):
            new_model = deep_copy_model(model)
            _inject_semester_links(new_model)
            new_models.append(new_model)
        else:
            new_models.append(model)

    # Append generated calendar models
    new_models.append(_build_academic_year_model(default_term))
    new_models.append(_build_academic_term_model())
    if enable_batch:
        new_models.append(_build_academic_batch_model(capacity_default))

    new_spec = {**spec, "models": new_models}

    # Academic calendar models auto-inherit mail.thread (renderer default for
    # non-line-item models), so mail dependency is always required.
    depends = list(new_spec.get("depends", []))
    if "mail" not in depends:
        depends.append("mail")
    new_spec["depends"] = depends

    return new_spec
