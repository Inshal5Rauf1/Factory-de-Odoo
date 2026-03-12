"""Per-stub context assembly from spec dict and ModelRegistry.

For each detected :class:`StubInfo`, builds a :class:`StubContext` that
contains everything an LLM (or developer) needs to implement the
method: model fields with type info, related model fields from the
registry, aggregated business rules from the spec, and the source of
cross-module data.

This module is a **leaf** -- it imports only from ``stub_detector``
(sibling) and ``registry`` (parent package), never from renderer or
validation modules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pathlib import Path

from odoo_gen_utils.logic_writer.stub_detector import StubInfo, _find_stub_zones
from odoo_gen_utils.registry import ModelEntry, ModelRegistry

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StubContext:
    """Assembled context for a single detected stub."""

    model_fields: dict[str, dict[str, Any]]
    """All fields on the model with type metadata."""

    related_fields: dict[str, dict[str, Any]]
    """Fields on referenced comodels, keyed by comodel name."""

    business_rules: list[str]
    """Flat list of business-rule strings aggregated from the spec."""

    registry_source: str | None
    """``'registry'``, ``'known_models'``, or ``None``."""

    method_type: str = ""
    """Method classification: compute, constraint, onchange, action, cron, override, other."""

    computation_hint: str = ""
    """Computation pattern hint for compute methods: sum_related, count_related, etc."""

    constraint_type: str = ""
    """Constraint pattern type for constraint methods: range, required_if, etc."""

    target_field_types: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Type metadata for each target field (type, currency_field, store, digits)."""

    error_messages: tuple[dict[str, Any], ...] = ()
    """Translatable error message templates for constraint methods."""

    stub_zone: dict[str, Any] | None = None
    """Marker-delimited zone dict for override method stubs."""

    exclusion_zones: tuple[dict[str, Any], ...] = ()
    """Template-generated code zones that must not be modified."""

    action_context: dict[str, Any] | None = None
    """Full state machine context for action_* methods."""

    cron_context: dict[str, Any] | None = None
    """Domain hint and processing pattern for _cron_* methods."""

    chain_context: dict[str, Any] | None = None
    """Full chain awareness for compute methods on chain fields."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_stub_context(
    stub: StubInfo,
    spec: dict[str, Any],
    registry: ModelRegistry | None = None,
    module_dir: Path | None = None,
) -> StubContext:
    """Assemble rich context for *stub* from *spec* and *registry*.

    Steps:
    1. Locate the spec model matching ``stub.model_name``.
    2. Extract all field metadata into ``model_fields``.
    3. Look up comodel fields in the registry for relational fields.
    4. Aggregate business rules from multiple spec locations.
    5. Classify method_type, computation_hint, constraint_type.
    6. Build target_field_types and error_messages as appropriate.
    """
    model = _find_spec_model(stub.model_name, spec)
    if model is None:
        return StubContext(
            model_fields={},
            related_fields={},
            business_rules=[],
            registry_source=None,
            method_type=_classify_method_type(stub),
        )

    model_fields = _build_model_fields(model)
    related_fields, reg_source = _build_related_fields(model_fields, registry)
    business_rules = _aggregate_business_rules(stub, model, model_fields)

    method_type = _classify_method_type(stub)

    computation_hint = ""
    if method_type == "compute":
        computation_hint = _classify_computation_hint(stub, model_fields, business_rules)

    constraint_type = ""
    if method_type == "constraint":
        constraint_type = _classify_constraint_type(business_rules)

    target_field_types: dict[str, dict[str, Any]] = {}
    if method_type == "compute":
        target_field_types = _build_target_field_types(stub, model_fields)

    error_messages: tuple[dict[str, Any], ...] = ()
    if method_type == "constraint":
        error_messages = _generate_error_messages(
            constraint_type, business_rules, stub.target_fields, model_fields
        )

    # Phase 58: action_context, cron_context, stub_zone
    action_context: dict[str, Any] | None = None
    if method_type == "action":
        action_context = _build_action_context(stub, model, spec)

    cron_context: dict[str, Any] | None = None
    if method_type == "cron":
        cron_context = _build_cron_context(stub, model, spec)

    stub_zone: dict[str, Any] | None = None
    exclusion_zones: tuple[dict[str, Any], ...] = ()
    if method_type == "override" and module_dir is not None:
        stub_zone, exclusion_zones = _build_stub_zones_for_override(
            stub, module_dir
        )

    # Phase 61: chain_context for compute methods on chain fields
    chain_context: dict[str, Any] | None = None
    if method_type == "compute":
        chain_context = _build_chain_context(stub, model_fields, spec)

    return StubContext(
        model_fields=model_fields,
        related_fields=related_fields,
        business_rules=business_rules,
        registry_source=reg_source,
        method_type=method_type,
        computation_hint=computation_hint,
        constraint_type=constraint_type,
        target_field_types=target_field_types,
        error_messages=error_messages,
        stub_zone=stub_zone,
        exclusion_zones=exclusion_zones,
        action_context=action_context,
        cron_context=cron_context,
        chain_context=chain_context,
    )


# ---------------------------------------------------------------------------
# Method type classification
# ---------------------------------------------------------------------------


def _classify_method_type(stub: StubInfo) -> str:
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
    stub: StubInfo,
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
    stub: StubInfo,
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
# Action context builder
# ---------------------------------------------------------------------------

# Keywords for side_effects detection
_SIDE_EFFECT_KEYWORDS = frozenset({
    "notification", "email", "create record", "log", "send",
    "create", "notify",
})

# Keywords for preconditions detection
_PRECONDITION_KEYWORDS = frozenset({
    "cannot", "must have", "required", "must be",
})


def _build_action_context(
    stub: StubInfo,
    model: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any] | None:
    """Build action_context with full state machine for action_* methods.

    Returns ``None`` if no state machine data is found (graceful degradation).
    """
    # Collect workflow states
    workflow_states = model.get("workflow_states", [])
    states_from_spec = model.get("states", [])

    state_names: list[str] = []
    for ws in workflow_states:
        name = ws.get("name", "")
        if name:
            state_names.append(name)
    for ws in states_from_spec:
        name = ws.get("name", "") if isinstance(ws, dict) else str(ws)
        if name and name not in state_names:
            state_names.append(name)

    if not state_names:
        return None

    # Build transitions from approval_levels and business rules
    transitions: list[dict[str, Any]] = []
    for level in model.get("approval_levels", []):
        from_state = level.get("from_state", "")
        to_state = level.get("to_state", "")
        method = level.get("method", "")
        role = level.get("name", "")
        if from_state and to_state:
            transitions.append({
                "from": from_state,
                "to": to_state,
                "method": method,
                "role": role,
            })

    # Extract side_effects from business rules
    all_rules = _collect_all_rules(model)
    side_effects: list[str] = []
    preconditions: list[str] = []

    for rule in all_rules:
        rule_lower = rule.lower()
        if any(kw in rule_lower for kw in _SIDE_EFFECT_KEYWORDS):
            side_effects.append(rule)
        if any(kw in rule_lower for kw in _PRECONDITION_KEYWORDS):
            preconditions.append(rule)

    return {
        "full_state_machine": {
            "states": state_names,
            "transitions": transitions,
        },
        "side_effects": side_effects,
        "preconditions": preconditions,
    }


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
# Cron context builder
# ---------------------------------------------------------------------------

# Keywords for processing_pattern classification
_CRON_BATCH_KEYWORDS = frozenset({"for each", "per record", "each record"})
_CRON_GENERATE_KEYWORDS = frozenset({"generate", "create", "schedule"})
_CRON_CLEANUP_KEYWORDS = frozenset({"archive", "expire", "older than", "delete", "clean"})
_CRON_AGGREGATE_KEYWORDS = frozenset({"calculate", "summarize", "report", "aggregate"})


def _build_cron_context(
    stub: StubInfo,
    model: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any] | None:
    """Build cron_context with domain hint and processing pattern for _cron_* methods.

    Returns ``None`` if no cron data is found in the spec.
    """
    # Look up cron section
    cron_entries = spec.get("cron", spec.get("scheduled_actions", []))
    if not cron_entries:
        return None

    # Find matching cron entry
    cron_entry: dict[str, Any] | None = None
    for entry in cron_entries:
        if entry.get("method") == stub.method_name:
            cron_entry = entry
            break

    if cron_entry is None:
        return None

    # Extract domain_hint
    domain_hint = cron_entry.get("domain", "")

    # If no domain in cron entry, try to infer from business rules
    if not domain_hint:
        all_rules = _collect_all_rules(model)
        for rule in all_rules:
            if "domain" in rule.lower() or "[(" in rule:
                domain_hint = rule
                break

    # Classify processing_pattern
    all_rules = _collect_all_rules(model)
    desc = model.get("description", "")
    all_text = " ".join(all_rules + [desc, cron_entry.get("name", "")]).lower()

    processing_pattern = _classify_cron_pattern(all_text)

    # batch_size_hint
    batch_size_hint = cron_entry.get("batch_size", 100)

    # error_handling
    error_handling = cron_entry.get("error_handling", "log_and_continue")

    return {
        "domain_hint": domain_hint,
        "processing_pattern": processing_pattern,
        "batch_size_hint": batch_size_hint,
        "error_handling": error_handling,
    }


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
# Chain context builder
# ---------------------------------------------------------------------------


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


def _build_chain_context(
    stub: StubInfo,
    model_fields: dict[str, dict[str, Any]],
    spec: dict[str, Any],
) -> dict[str, Any] | None:
    """Build chain_context for compute stubs on chain-enriched fields.

    Returns ``None`` if:
    - stub is not a compute method
    - target field has no ``_chain_meta`` key

    Otherwise returns a dict with chain_id, position, steps,
    upstream/downstream, and computation_pattern hint.
    """
    if not stub.method_name.startswith("_compute_"):
        return None

    # Find the first target field with _chain_meta
    chain_meta: dict[str, Any] | None = None
    target_field_name: str = ""
    for tf in stub.target_fields:
        meta = model_fields.get(tf, {}).get("_chain_meta")
        if meta is not None:
            chain_meta = meta
            target_field_name = tf
            break

    if chain_meta is None:
        return None

    source = chain_meta.get("source", "")
    aggregation = chain_meta.get("aggregation")
    lookup_table = chain_meta.get("lookup_table")

    # Build this_step dict
    this_step: dict[str, Any] = {"source": source}
    if aggregation is not None:
        this_step["aggregation"] = aggregation
    if lookup_table is not None:
        this_step["lookup_table"] = lookup_table

    # Parse depends to extract field references
    depends_args = _parse_depends_args(stub.decorator)

    # Build computation_pattern
    computation_pattern = _build_computation_pattern(
        source, aggregation, depends_args, model_fields, target_field_name,
    )

    return {
        "chain_id": chain_meta["chain_id"],
        "chain_description": chain_meta.get("chain_description", ""),
        "position_in_chain": chain_meta["position_in_chain"],
        "total_steps": chain_meta["total_steps"],
        "this_step": this_step,
        "upstream_steps": list(chain_meta.get("upstream_steps", [])),
        "downstream_steps": list(chain_meta.get("downstream_steps", [])),
        "computation_pattern": computation_pattern,
    }


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


# ---------------------------------------------------------------------------
# Stub zone builder for overrides
# ---------------------------------------------------------------------------


def _build_stub_zones_for_override(
    stub: StubInfo,
    module_dir: Path,
) -> tuple[dict[str, Any] | None, tuple[dict[str, Any], ...]]:
    """Read source file and find BUSINESS LOGIC marker zones for override stubs.

    For create(): first zone is ``"pre_super"``, second is ``"post_super"``.
    For write(): single zone is ``"post_super"``.

    Returns ``(stub_zone_for_this_stub, exclusion_zones_tuple)``.
    """
    source_path = module_dir / stub.file
    if not source_path.exists():
        return None, ()

    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError:
        return None, ()

    source_lines = source.splitlines()
    zones = _find_stub_zones(source_lines)

    if not zones:
        return None, ()

    # Assign position based on method name
    if stub.method_name == "create" and len(zones) >= 2:
        zones[0]["position"] = "pre_super"
        zones[1]["position"] = "post_super"
        # Return the first zone as the primary stub_zone
        # (future: could return both as separate report entries)
        stub_zone = zones[0]
    elif stub.method_name == "create" and len(zones) == 1:
        zones[0]["position"] = "post_super"
        stub_zone = zones[0]
    elif stub.method_name == "write" and zones:
        zones[0]["position"] = "post_super"
        stub_zone = zones[0]
    else:
        stub_zone = zones[0] if zones else None

    # Build exclusion_zones from lines outside markers within the method
    # For now, just return the zones not used as stub_zone
    exclusion_zones: list[dict[str, Any]] = []
    # Exclusion zones would be template-generated code around the markers
    # This is a simplified version -- full implementation would diff against skeleton

    return stub_zone, tuple(exclusion_zones)


# ---------------------------------------------------------------------------
# Internal helpers (original)
# ---------------------------------------------------------------------------


def _find_spec_model(
    model_name: str, spec: dict[str, Any]
) -> dict[str, Any] | None:
    """Locate a model dict in *spec* by ``name`` or ``_name``.

    Searches ``spec["models"]`` first, then ``spec.get("wizards", [])``.
    """
    for model in spec.get("models", []):
        if model.get("name") == model_name or model.get("_name") == model_name:
            return model
    for wizard in spec.get("wizards", []):
        if (
            wizard.get("name") == model_name
            or wizard.get("_name") == model_name
        ):
            return wizard
    return None


def _build_model_fields(
    model: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract field metadata from *model* into a name-keyed dict."""
    result: dict[str, dict[str, Any]] = {}
    for field_def in model.get("fields", []):
        name = field_def.get("name", "")
        if not name:
            continue
        entry: dict[str, Any] = {}
        for key in (
            "type",
            "string",
            "help",
            "compute",
            "store",
            "depends",
            "constrains",
            "comodel_name",
            "inverse_name",
            "relation",
            "required",
            "readonly",
            "default",
            "currency_field",
            "digits",
            "_chain_meta",
        ):
            if key in field_def:
                entry[key] = field_def[key]
        result[name] = entry
    return result


def _build_related_fields(
    model_fields: dict[str, dict[str, Any]],
    registry: ModelRegistry | None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Look up comodel fields for relational fields in *model_fields*.

    Returns ``(related_fields_dict, registry_source_string)``.
    ``registry_source`` is ``"registry"`` if any comodel came from
    registered modules, ``"known_models"`` if from standard Odoo models,
    or ``None`` if no comodels were found anywhere.
    """
    if registry is None:
        return {}, None

    related: dict[str, dict[str, Any]] = {}
    source: str | None = None

    for _field_name, field_meta in model_fields.items():
        ftype = field_meta.get("type", "")
        comodel = field_meta.get("comodel_name")
        if ftype not in _RELATIONAL_TYPES or not comodel:
            continue
        if comodel in related:
            continue  # already looked up

        # Try registered modules first
        entry: ModelEntry | None = registry.show_model(comodel)
        if entry is not None:
            related[comodel] = dict(entry.fields)
            source = "registry"
            continue

        # Try known Odoo models
        # Access _known_models directly (loaded via load_known_models)
        known = registry._known_models.get(comodel)  # noqa: SLF001
        if known is not None:
            related[comodel] = dict(known.get("fields", {}))
            if source is None:
                source = "known_models"
            continue

        logger.debug("Comodel %s not found in registry or known models", comodel)

    return related, source


def _aggregate_business_rules(
    stub: StubInfo,
    model: dict[str, Any],
    model_fields: dict[str, dict[str, Any]],
) -> list[str]:
    """Collect business-rule strings from all spec locations.

    Sources:
    1. Model description
    2. Field ``help`` texts for target fields
    3. ``complex_constraints`` messages
    4. ``workflow_states`` name + description
    5. ``approval_levels`` name + description
    6. Field ``depends`` lists for target fields
    """
    rules: list[str] = []

    # 1. Model description
    desc = model.get("description", "")
    if desc:
        rules.append(desc)

    # 2. Field help texts for target fields
    for target in stub.target_fields:
        field_meta = model_fields.get(target, {})
        help_text = field_meta.get("help", "")
        if help_text:
            rules.append(help_text)

    # 3. Complex constraints
    for cc in model.get("complex_constraints", []):
        msg = cc.get("message", "")
        if msg:
            rules.append(msg)

    # 4. Workflow states
    for state in model.get("workflow_states", []):
        name = state.get("name", "")
        desc = state.get("description", "")
        if name:
            entry = f"{name}: {desc}" if desc else name
            rules.append(entry)

    # 5. Approval levels
    for level in model.get("approval_levels", []):
        name = level.get("name", "")
        desc = level.get("description", "")
        if name:
            entry = f"{name}: {desc}" if desc else name
            rules.append(entry)

    # 6. Depends for target fields
    for target in stub.target_fields:
        field_meta = model_fields.get(target, {})
        depends = field_meta.get("depends", [])
        if depends:
            rules.append(f"{target} depends on: {', '.join(depends)}")

    return rules
