"""Pakistan/HEC localization preprocessor for Odoo module generation.

Injects Pakistan-specific fields, constraints, and SQL constraints into model
specs when ``localization: "pk"`` is present. Per-model opt-in via ``pk_fields``.

Registered at order=25 (after computation_chains=20, before constraints=30).

Phase 49 -- DOMN-02.
"""

from __future__ import annotations

from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.renderer_utils import _to_python_var
from odoo_gen_utils.utils.copy import deep_copy_model, has_field as _has_field


# -- Valid pk_fields tokens --------------------------------------------------
_VALID_PK_FIELDS = frozenset({
    "cnic", "phone", "gpa", "credit_hours", "hec_registration",
    "ntn", "strn", "degree_level", "recognition_status",
    "pkr_amount", "hec_program_code", "cgpa", "total_credit_hours",
})


# -- String constants for generated constraint method bodies -----------------

_CNIC_CHECK_BODY = """\
import re
for rec in self:
    if not rec.cnic:
        continue
    raw = re.sub(r'[^0-9]', '', rec.cnic)
    if len(raw) != 13:
        raise ValidationError(
            _("CNIC must be exactly 13 digits. Got: %s") % rec.cnic
        )
    # Normalize to XXXXX-XXXXXXX-X canonical form
    rec.cnic = f"{raw[:5]}-{raw[5:12]}-{raw[12]}\""""

_PHONE_CHECK_BODY = """\
import re
for rec in self:
    if not rec.phone_pk:
        continue
    try:
        import phonenumbers
        parsed = phonenumbers.parse(rec.phone_pk, "PK")
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError(
                _("Invalid Pakistani phone number: %s") % rec.phone_pk
            )
        rec.phone_pk = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
    except ImportError:
        # Fallback: regex validation only, no normalization
        mobile_re = r'^(\\+92|0)?3\\d{9}$'
        landline_re = r'^(\\+92|0)?\\d{10,11}$'
        cleaned = re.sub(r'[\\s\\-\\(\\)]', '', rec.phone_pk)
        if not (re.match(mobile_re, cleaned) or re.match(landline_re, cleaned)):
            raise ValidationError(
                _("Invalid Pakistani phone number format: %s") % rec.phone_pk
            )"""

_GPA_CHECK_BODY = """\
for rec in self:
    if rec.gpa < 0.0 or rec.gpa > 4.0:
        raise ValidationError(
            _("GPA must be between 0.00 and 4.00. Got: %s") % rec.gpa
        )"""

_CREDIT_HOURS_CHECK_BODY = """\
for rec in self:
    if rec.credit_hours < 0 or rec.credit_hours > 6:
        raise ValidationError(
            _("Credit hours must be between 0 and 6. Got: %s") % rec.credit_hours
        )"""


# -- HEC Degree Level selection values --------------------------------------

_DEGREE_LEVEL_SELECTION = [
    ("matriculation", "Matriculation"),
    ("intermediate", "Intermediate / HSSC"),
    ("bachelor", "Bachelor (BS/BA/BBA)"),
    ("master", "Master (MS/MA/MBA)"),
    ("mphil", "MPhil"),
    ("phd", "PhD"),
    ("postdoc", "Post-Doctorate"),
]

# -- Recognition Status selection values ------------------------------------

_RECOGNITION_STATUS_SELECTION = [
    ("recognized", "HEC Recognized"),
    ("chartered", "Chartered"),
    ("affiliated", "Affiliated"),
    ("not_recognized", "Not Recognized"),
]


# -- Field injection helpers ------------------------------------------------
# Each helper mutates a model dict **in-place**. The caller provides a copy.




def _has_sql_constraint(model: dict[str, Any], name: str) -> bool:
    """Check if a SQL constraint with the given name exists."""
    return any(c.get("name") == name for c in model.get("sql_constraints", []))


def _model_prefix(model: dict[str, Any]) -> str:
    """Return model variable name prefix for SQL constraint naming."""
    return _to_python_var(model["name"])


def _inject_cnic(model: dict[str, Any]) -> None:
    """Inject CNIC field, SQL unique constraint, and complex_constraint."""
    prefix = _model_prefix(model)

    if not _has_field(model, "cnic"):
        model["fields"].append({
            "name": "cnic",
            "type": "Char",
            "string": "CNIC",
            "size": 15,
            "copy": False,
            "tracking": True,
            "help": "Computerized National Identity Card (XXXXX-XXXXXXX-X)",
        })

    constraint_name = f"{prefix}_cnic_unique"
    sql = model.setdefault("sql_constraints", [])
    if not _has_sql_constraint(model, constraint_name):
        sql.append({
            "name": constraint_name,
            "definition": "UNIQUE(cnic)",
            "message": "CNIC must be unique.",
        })

    cc = model.setdefault("complex_constraints", [])
    cc.append({
        "name": "cnic",
        "fields": ["cnic"],
        "type": "pk_cnic",
        "check_body": _CNIC_CHECK_BODY,
    })


def _inject_phone(model: dict[str, Any]) -> None:
    """Inject phone_pk field and complex_constraint with phonenumbers fallback."""
    if not _has_field(model, "phone_pk"):
        model["fields"].append({
            "name": "phone_pk",
            "type": "Char",
            "string": "Phone (PK)",
            "tracking": True,
        })

    cc = model.setdefault("complex_constraints", [])
    cc.append({
        "name": "phone_pakistan",
        "fields": ["phone_pk"],
        "type": "pk_phone",
        "check_body": _PHONE_CHECK_BODY,
    })


def _inject_ntn(model: dict[str, Any]) -> None:
    """Inject NTN field and SQL unique constraint."""
    prefix = _model_prefix(model)

    if not _has_field(model, "ntn"):
        model["fields"].append({
            "name": "ntn",
            "type": "Char",
            "string": "NTN",
            "size": 9,
            "copy": False,
            "tracking": True,
            "help": "National Tax Number (FBR)",
        })

    constraint_name = f"{prefix}_ntn_unique"
    sql = model.setdefault("sql_constraints", [])
    if not _has_sql_constraint(model, constraint_name):
        sql.append({
            "name": constraint_name,
            "definition": "UNIQUE(ntn)",
            "message": "NTN must be unique.",
        })


def _inject_strn(model: dict[str, Any]) -> None:
    """Inject STRN field and SQL unique constraint."""
    prefix = _model_prefix(model)

    if not _has_field(model, "strn"):
        model["fields"].append({
            "name": "strn",
            "type": "Char",
            "string": "STRN",
            "size": 15,
            "copy": False,
            "tracking": True,
            "help": "Sales Tax Registration Number (FBR)",
        })

    constraint_name = f"{prefix}_strn_unique"
    sql = model.setdefault("sql_constraints", [])
    if not _has_sql_constraint(model, constraint_name):
        sql.append({
            "name": constraint_name,
            "definition": "UNIQUE(strn)",
            "message": "STRN must be unique.",
        })


def _inject_hec_registration(model: dict[str, Any]) -> None:
    """Inject HEC Registration No. field and SQL unique constraint."""
    prefix = _model_prefix(model)

    if not _has_field(model, "hec_registration_no"):
        model["fields"].append({
            "name": "hec_registration_no",
            "type": "Char",
            "string": "HEC Registration No.",
            "copy": False,
            "tracking": True,
        })

    constraint_name = f"{prefix}_hec_reg_unique"
    sql = model.setdefault("sql_constraints", [])
    if not _has_sql_constraint(model, constraint_name):
        sql.append({
            "name": constraint_name,
            "definition": "UNIQUE(hec_registration_no)",
            "message": "HEC Registration Number must be unique.",
        })


def _inject_gpa(model: dict[str, Any]) -> None:
    """Inject GPA Float field and complex_constraint for 0.00-4.00 range."""
    if not _has_field(model, "gpa"):
        model["fields"].append({
            "name": "gpa",
            "type": "Float",
            "string": "GPA",
            "digits": (3, 2),
            "default": 0.0,
        })

    cc = model.setdefault("complex_constraints", [])
    cc.append({
        "name": "gpa",
        "fields": ["gpa"],
        "type": "pk_gpa",
        "check_body": _GPA_CHECK_BODY,
    })


def _inject_credit_hours(model: dict[str, Any]) -> None:
    """Inject credit_hours Integer field and complex_constraint for 0-6 range."""
    if not _has_field(model, "credit_hours"):
        model["fields"].append({
            "name": "credit_hours",
            "type": "Integer",
            "string": "Credit Hours",
            "default": 3,
        })

    cc = model.setdefault("complex_constraints", [])
    cc.append({
        "name": "credit_hours",
        "fields": ["credit_hours"],
        "type": "pk_credit_hours",
        "check_body": _CREDIT_HOURS_CHECK_BODY,
    })


def _inject_degree_level(model: dict[str, Any]) -> None:
    """Inject degree_level Selection field with 7 HEC-standard values."""
    if not _has_field(model, "degree_level"):
        model["fields"].append({
            "name": "degree_level",
            "type": "Selection",
            "string": "Degree Level",
            "selection": list(_DEGREE_LEVEL_SELECTION),
        })


def _inject_recognition_status(model: dict[str, Any]) -> None:
    """Inject recognition_status Selection field with 4 values."""
    if not _has_field(model, "recognition_status"):
        model["fields"].append({
            "name": "recognition_status",
            "type": "Selection",
            "string": "Recognition Status",
            "selection": list(_RECOGNITION_STATUS_SELECTION),
            "default": "recognized",
        })


# -- HEC Program Code selection values ----------------------------------------

_HEC_PROGRAM_CODE_SELECTION = [
    ("bs_cs", "BS Computer Science"),
    ("bs_se", "BS Software Engineering"),
    ("bs_it", "BS Information Technology"),
    ("bs_ee", "BS Electrical Engineering"),
    ("bs_me", "BS Mechanical Engineering"),
    ("bs_ce", "BS Civil Engineering"),
    ("bs_bba", "BBA"),
    ("bs_eco", "BS Economics"),
    ("ms_cs", "MS Computer Science"),
    ("ms_se", "MS Software Engineering"),
    ("ms_ee", "MS Electrical Engineering"),
    ("ms_mba", "MBA"),
    ("phd_cs", "PhD Computer Science"),
    ("phd_ee", "PhD Electrical Engineering"),
    ("other", "Other"),
]


def _inject_pkr_amount(model: dict[str, Any]) -> None:
    """Inject PKR currency amount field with Monetary type."""
    if not _has_field(model, "amount_pkr"):
        model["fields"].append({
            "name": "amount_pkr",
            "type": "Monetary",
            "string": "Amount (PKR)",
            "currency_field": "currency_id",
        })
    if not _has_field(model, "currency_id"):
        model["fields"].append({
            "name": "currency_id",
            "type": "Many2one",
            "comodel_name": "res.currency",
            "string": "Currency",
            "default": "lambda self: self.env.company.currency_id",
        })


def _inject_hec_program_code(model: dict[str, Any]) -> None:
    """Inject HEC program code selection field."""
    if not _has_field(model, "hec_program_code"):
        model["fields"].append({
            "name": "hec_program_code",
            "type": "Selection",
            "string": "HEC Program Code",
            "selection": list(_HEC_PROGRAM_CODE_SELECTION),
            "tracking": True,
        })


def _inject_cgpa(model: dict[str, Any]) -> None:
    """Inject cumulative GPA computed field."""
    if not _has_field(model, "cgpa"):
        model["fields"].append({
            "name": "cgpa",
            "type": "Float",
            "string": "CGPA",
            "digits": (3, 2),
            "compute": "_compute_cgpa",
            "store": True,
            "depends": ["result_line_ids", "result_line_ids.gpa",
                        "result_line_ids.credit_hours"],
            "help": "Cumulative Grade Point Average across all semesters",
        })


def _inject_total_credit_hours(model: dict[str, Any]) -> None:
    """Inject total credit hours computed field."""
    if not _has_field(model, "total_credit_hours"):
        model["fields"].append({
            "name": "total_credit_hours",
            "type": "Integer",
            "string": "Total Credit Hours",
            "compute": "_compute_total_credit_hours",
            "store": True,
            "depends": ["result_line_ids", "result_line_ids.credit_hours"],
        })


# -- Dispatch table ----------------------------------------------------------

_PK_FIELD_INJECTORS: dict[str, Any] = {
    "cnic": _inject_cnic,
    "phone": _inject_phone,
    "ntn": _inject_ntn,
    "strn": _inject_strn,
    "hec_registration": _inject_hec_registration,
    "gpa": _inject_gpa,
    "credit_hours": _inject_credit_hours,
    "degree_level": _inject_degree_level,
    "recognition_status": _inject_recognition_status,
    "pkr_amount": _inject_pkr_amount,
    "hec_program_code": _inject_hec_program_code,
    "cgpa": _inject_cgpa,
    "total_credit_hours": _inject_total_credit_hours,
}


# -- Main preprocessor -------------------------------------------------------


@register_preprocessor(order=25, name="pakistan_hec")
def _process_pakistan_hec(spec: dict[str, Any]) -> dict[str, Any]:
    """Inject Pakistan/HEC localization fields into model specs.

    Triggered by ``localization: "pk"`` at module level.
    Per-model opt-in via ``pk_fields`` list on each model.

    Returns a new spec dict -- never mutates the input.
    """
    if spec.get("localization") != "pk":
        return spec

    # Deep-copy models using canonical utility
    new_models = [deep_copy_model(m) for m in spec.get("models", [])]

    for model in new_models:
        pk_fields = set(model.get("pk_fields", []))
        if not pk_fields:
            continue

        for field_key, injector in _PK_FIELD_INJECTORS.items():
            if field_key in pk_fields:
                injector(model)

    new_spec = {**spec, "models": new_models}

    # Module-level: always inject PKR currency data file path
    extra = list(new_spec.get("extra_data_files", []))
    extra.append("data/pk_currency_data.xml")
    new_spec["extra_data_files"] = extra

    return new_spec
