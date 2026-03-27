"""Helper functions for context_builder: classification, error messages, field analysis.

Extracted from ``context_builder.py`` to keep each module under ~600 lines.
All functions here are pure or near-pure — they depend only on their
arguments, never on module-level mutable state.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword constants
# ---------------------------------------------------------------------------

_RELATIONAL_TYPES = frozenset({"Many2one", "One2many", "Many2many"})
_X2MANY_TYPES = frozenset({"One2many", "Many2many"})
_NUMERIC_TYPES = frozenset({"Float", "Integer", "Monetary"})

# Keyword sets for constraint_type classification
_RANGE_KEYWORDS = frozenset({
    "between", "at least", "at most", "minimum", "maximum",
    "greater than", "less than",
})
_REQUIRED_IF_KEYWORDS = frozenset({
    "required when", "must have if", "required if",
})
_CROSS_FIELD_COMPARATORS = frozenset({
    "after", "before", "greater", "less", ">", "<",
})
_FORMAT_KEYWORDS = frozenset({
    "format", "pattern", "cnic", "email", "phone",
})
_UNIQUE_KEYWORDS = frozenset({
    "unique per", "no duplicate", "unique",
})
_REFERENTIAL_KEYWORDS = frozenset({
    "must exist", "catalog", "reference",
})

# Keyword sets for aggregate computation_hint
_AGGREGATE_KEYWORDS = frozenset({
    "average", "weighted", "min", "max", "mean",
})

# Keywords for side_effects detection
_SIDE_EFFECT_KEYWORDS = frozenset({
    "notification", "email", "create record", "log", "send",
    "create", "notify",
})

# Keywords for preconditions detection
_PRECONDITION_KEYWORDS = frozenset({
    "cannot", "must have", "required", "must be",
})

# Keywords for processing_pattern classification
_CRON_BATCH_KEYWORDS = frozenset({"for each", "per record", "each record"})
_CRON_GENERATE_KEYWORDS = frozenset({"generate", "create", "schedule"})
_CRON_CLEANUP_KEYWORDS = frozenset({"archive", "expire", "older than", "delete", "clean"})
_CRON_AGGREGATE_KEYWORDS = frozenset({"calculate", "summarize", "report", "aggregate"})

# Computation pattern templates keyed by (source, aggregation)
_PATTERN_TEMPLATES: dict[tuple[str, str | None], str] = {
    ("aggregation", "sum"): "sum(record.{rel_field}.mapped('{target_field}'))",
    ("aggregation", "count"): "len(record.{rel_field}.filtered(...))",
    ("aggregation", "min"): "min(record.{rel_field}.mapped('{target_field}'))",
    ("aggregation", "max"): "max(record.{rel_field}.mapped('{target_field}'))",
    ("aggregation", "average"): (
        "sum(record.{rel_field}.mapped('{target_field}'))"
        " / len(record.{rel_field})"
    ),
}


# ---------------------------------------------------------------------------
# Method type classification
# ---------------------------------------------------------------------------


def _classify_method_type(stub: Any) -> str:
    """Classify the method type from the method name pattern.

    Returns one of: compute, constraint, onchange, action, cron, override, other.
    """
    name = stub.method_name
    if name.startswith("_compute_"):
        return "compute"
    if name.startswith("_check_"):
        return "constraint"
    if name.startswith("_onchange_"):
        return "onchange"
    if name.startswith("action_"):
        return "action"
    if name.startswith("_cron_"):
        return "cron"
    if name in ("create", "write"):
        return "override"
    return "other"


# ---------------------------------------------------------------------------
# Computation hint classification
# ---------------------------------------------------------------------------


def _classify_computation_hint(
    stub: Any,
    model_fields: dict[str, dict[str, Any]],
    business_rules: list[str],
) -> str:
    """Classify the computation pattern for a compute method.

    Priority order: cross_model_calc -> sum_related -> count_related ->
    aggregate -> conditional_set -> lookup -> custom.
    """
    depends_args = _parse_depends_args(stub.decorator)
    dot_paths = [d for d in depends_args if "." in d]
    target_types = {
        tf: model_fields.get(tf, {}).get("type", "")
        for tf in stub.target_fields
    }

    # cross_model_calc: 2+ dot-path segments (e.g. "order_id.partner_id.credit")
    for dp in dot_paths:
        if dp.count(".") >= 2:
            return "cross_model_calc"

    # sum_related: dot-path to a field on a x2many, target is numeric
    if dot_paths:
        for dp in dot_paths:
            first_segment = dp.split(".")[0]
            first_field_type = model_fields.get(first_segment, {}).get("type", "")
            if first_field_type in _X2MANY_TYPES:
                if any(t in _NUMERIC_TYPES for t in target_types.values()):
                    return "sum_related"

    # count_related: target is Integer, depends includes a x2many field
    if any(t == "Integer" for t in target_types.values()):
        for dep in depends_args:
            first_segment = dep.split(".")[0]
            dep_type = model_fields.get(first_segment, {}).get("type", "")
            if dep_type in _X2MANY_TYPES:
                return "count_related"

    # aggregate: business rules contain average/weighted/min/max/mean
    rules_lower = " ".join(r.lower() for r in business_rules)
    if any(kw in rules_lower for kw in _AGGREGATE_KEYWORDS):
        return "aggregate"

    # conditional_set: target is Boolean or Selection
    if any(t in ("Boolean", "Selection") for t in target_types.values()):
        return "conditional_set"

    # lookup: single dot-path, target type is non-numeric
    if dot_paths:
        non_numeric_targets = [
            t for t in target_types.values()
            if t and t not in _NUMERIC_TYPES
        ]
        if non_numeric_targets:
            return "lookup"

    return "custom"


def _parse_depends_args(decorator: str) -> list[str]:
    """Parse field names from a ``@api.depends(...)`` decorator string.

    Returns a list of field name strings (may include dot notation).
    """
    if "depends" not in decorator:
        return []
    paren_start = decorator.find("(")
    if paren_start == -1:
        return []
    paren_end = decorator.rfind(")")
    if paren_end == -1:
        paren_end = len(decorator)
    args_str = decorator[paren_start + 1 : paren_end]
    # Extract quoted strings
    return re.findall(r'["\']([^"\']+)["\']', args_str)


# ---------------------------------------------------------------------------
# Constraint type classification
# ---------------------------------------------------------------------------


def _classify_constraint_type(business_rules: list[str]) -> str:
    """Classify the constraint pattern from business rules.

    Priority order: range -> required_if -> cross_field -> format ->
    unique -> referential -> custom.
    """
    rules_lower = " ".join(r.lower() for r in business_rules)

    # range: between, at least, at most, minimum, maximum
    if any(kw in rules_lower for kw in _RANGE_KEYWORDS):
        return "range"

    # required_if: required when, must have if, required if
    if any(kw in rules_lower for kw in _REQUIRED_IF_KEYWORDS):
        return "required_if"

    # cross_field: references two+ field names with comparison words
    if any(kw in rules_lower for kw in _CROSS_FIELD_COMPARATORS):
        return "cross_field"

    # format: format, pattern, CNIC, email, phone
    if any(kw in rules_lower for kw in _FORMAT_KEYWORDS):
        return "format"

    # unique: unique per, no duplicate, unique
    if any(kw in rules_lower for kw in _UNIQUE_KEYWORDS):
        return "unique"

    # referential: must exist, catalog, reference
    if any(kw in rules_lower for kw in _REFERENTIAL_KEYWORDS):
        return "referential"

    return "custom"


# ---------------------------------------------------------------------------
# Target field types
# ---------------------------------------------------------------------------


def _build_target_field_types(
    stub: Any,
    model_fields: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Extract type metadata for each target field.

    For each target field, extracts type, currency_field, store, digits
    from model_fields. Only includes keys that have non-None values.
    """
    result: dict[str, dict[str, Any]] = {}
    for target in stub.target_fields:
        field_meta = model_fields.get(target, {})
        if not field_meta:
            continue
        entry: dict[str, Any] = {}
        for key in ("type", "currency_field", "store", "digits"):
            val = field_meta.get(key)
            if val is not None:
                entry[key] = val
        if entry:
            result[target] = entry
    return result


# ---------------------------------------------------------------------------
# Error message generation
# ---------------------------------------------------------------------------


def _generate_error_messages(
    constraint_type: str,
    business_rules: list[str],
    target_fields: list[str],
    model_fields: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Generate translatable error message templates for constraint methods.

    Uses field ``string`` (label) from model_fields when available,
    falling back to the field name. Each message contains condition,
    message, and translatable=True.
    """
    def _field_label(field_name: str) -> str:
        return model_fields.get(field_name, {}).get("string", field_name)

    messages: list[dict[str, Any]] = []

    if constraint_type == "range" and target_fields:
        label = _field_label(target_fields[0])
        messages.append({
            "condition": f"{target_fields[0]} out of range",
            "message": (
                f"_('%(field_label)s must be between %(min)s and %(max)s."
                f" Got %(value)s.')"
            ),
            "translatable": True,
        })

    elif constraint_type == "required_if" and target_fields:
        label = _field_label(target_fields[0])
        messages.append({
            "condition": f"{target_fields[0]} missing when required",
            "message": (
                "_('%(field_label)s is required when %(condition)s.')"
            ),
            "translatable": True,
        })

    elif constraint_type == "cross_field" and len(target_fields) >= 2:
        label1 = _field_label(target_fields[0])
        label2 = _field_label(target_fields[1])
        messages.append({
            "condition": f"{target_fields[0]} vs {target_fields[1]}",
            "message": (
                "_('%(field1_label)s must be after %(field2_label)s.')"
            ),
            "translatable": True,
        })

    elif constraint_type == "format" and target_fields:
        label = _field_label(target_fields[0])
        messages.append({
            "condition": f"invalid {target_fields[0]} format",
            "message": (
                "_('Invalid %(field_label)s format. Expected %(format)s.')"
            ),
            "translatable": True,
        })

    elif constraint_type == "unique":
        messages.append({
            "condition": "duplicate found",
            "message": (
                "_('%(field_label)s must be unique per %(scope)s.')"
            ),
            "translatable": True,
        })

    else:
        # Generic: use business rule text as message template
        for rule in business_rules:
            if rule and not rule.startswith(("University", "uni.")):
                messages.append({
                    "condition": "validation failed",
                    "message": f"_('{rule}')",
                    "translatable": True,
                })
                break  # One generic message is enough

    # If still no messages but we have business rules, use the first meaningful one
    if not messages and business_rules:
        for rule in business_rules:
            if rule:
                messages.append({
                    "condition": "validation failed",
                    "message": f"_('{rule}')",
                    "translatable": True,
                })
                break

    return tuple(messages)


# ---------------------------------------------------------------------------
# Collect rules helper
# ---------------------------------------------------------------------------


def _collect_all_rules(model: dict[str, Any]) -> list[str]:
    """Collect all rule-like strings from model spec for side_effect/precondition extraction."""
    rules: list[str] = []
    for cc in model.get("complex_constraints", []):
        msg = cc.get("message", "")
        if msg:
            rules.append(msg)
    for rule in model.get("business_rules", []):
        if isinstance(rule, str) and rule:
            rules.append(rule)
        elif isinstance(rule, dict):
            msg = rule.get("message", rule.get("description", ""))
            if msg:
                rules.append(msg)
    return rules


# ---------------------------------------------------------------------------
# Cron pattern classification
# ---------------------------------------------------------------------------


def _classify_cron_pattern(text: str) -> str:
    """Classify cron processing pattern from text keywords.

    Priority: generate_records -> cleanup -> aggregate -> batch_per_record (default).
    """
    if any(kw in text for kw in _CRON_GENERATE_KEYWORDS):
        return "generate_records"
    if any(kw in text for kw in _CRON_CLEANUP_KEYWORDS):
        return "cleanup"
    if any(kw in text for kw in _CRON_AGGREGATE_KEYWORDS):
        return "aggregate"
    if any(kw in text for kw in _CRON_BATCH_KEYWORDS):
        return "batch_per_record"
    return "batch_per_record"


# ---------------------------------------------------------------------------
# Computation pattern builder
# ---------------------------------------------------------------------------


def _build_computation_pattern(
    source: str,
    aggregation: str | None,
    depends_args: list[str],
    model_fields: dict[str, dict[str, Any]],
    target_field_name: str,
) -> str:
    """Build a computation_pattern hint string based on source and aggregation type."""
    # direct_input and computation sources have no specific pattern
    if source in ("direct_input", "computation"):
        return ""

    # lookup: GRADE_MAP.get(record.source_field, 0.0)
    if source == "lookup":
        source_field = depends_args[0] if depends_args else "source_field"
        return f"GRADE_MAP.get(record.{source_field}, 0.0)"

    # aggregation: use templates
    if source == "aggregation":
        if aggregation == "weighted_average":
            return _build_weighted_average_pattern(depends_args, model_fields)

        # For other aggregation types, extract rel_field and target from depends
        dot_paths = [d for d in depends_args if "." in d]
        if dot_paths:
            parts = dot_paths[0].split(".", 1)
            rel_field = parts[0]
            mapped_field = parts[1]
        else:
            rel_field = "related_ids"
            mapped_field = target_field_name

        template = _PATTERN_TEMPLATES.get(("aggregation", aggregation), "")
        if template:
            return template.format(
                rel_field=rel_field, target_field=mapped_field,
            )

    return ""


def _build_weighted_average_pattern(
    depends_args: list[str],
    model_fields: dict[str, dict[str, Any]],
) -> str:
    """Build weighted_average computation_pattern with actual field names.

    Expected depends: ["rel.numerator_field", "rel.denominator_field"]
    Pattern: sum(r.num * r.den for r in record.rel) / sum(r.den for r in record.rel)
    """
    dot_paths = [d for d in depends_args if "." in d]
    if len(dot_paths) < 2:
        return "sum(r.X * r.Y for r in record.related_ids) / sum(r.Y for r in record.related_ids)"

    # First dot-path: numerator (e.g., enrollment_ids.weighted_grade_points)
    num_parts = dot_paths[0].split(".", 1)
    rel_field = num_parts[0]
    num_field = num_parts[1].split(".")[-1]  # last segment

    # Second dot-path: denominator (e.g., enrollment_ids.course_id.credit_hours)
    den_parts = dot_paths[1].split(".", 1)
    den_field = den_parts[1].split(".")[-1]  # last segment

    return (
        f"sum(r.{num_field} * r.{den_field} for r in record.{rel_field})"
        f" / sum(r.{den_field} for r in record.{rel_field})"
    )
