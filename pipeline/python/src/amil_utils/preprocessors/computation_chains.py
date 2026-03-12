"""Sequence-based computation chain preprocessor.

Registered at order=22 (after relationships@10, extensions@12,
init_override_sources@15). Parses computation_chains entries via
ChainSpec Pydantic model, auto-adds fields, sets @api.depends
with dot notation, and enriches field dicts with chain metadata.

Includes 5 chain-specific validators (E18-E22) that run BEFORE
field enrichment to catch type mismatches, traversal errors,
store gaps, cycles, and missing fields.

Pure function -- never mutates input spec.
"""

from __future__ import annotations

import logging
from graphlib import CycleError, TopologicalSorter
from typing import Any

from pydantic import ValidationError

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.preprocessors.relationships import _resolve_comodel
from odoo_gen_utils.spec_schema import ChainSpec, ChainStepSpec
from odoo_gen_utils.utils.copy import deep_copy_model

logger = logging.getLogger(__name__)

# Numeric field types for aggregation validation
_NUMERIC_TYPES: frozenset[str] = frozenset({"Float", "Integer", "Monetary"})

# Relational field types that support dot-path traversal
_RELATIONAL_TYPES: frozenset[str] = frozenset({
    "One2many", "Many2many", "Many2one",
})


# ---------------------------------------------------------------------------
# Validators (E18-E22)
# ---------------------------------------------------------------------------


def _find_field_in_spec(
    spec: dict[str, Any], model_name: str, field_name: str,
) -> dict[str, Any] | None:
    """Find a field dict in spec by model and field name."""
    for model in spec.get("models", []):
        if model["name"] == model_name:
            for field in model.get("fields", []):
                if field.get("name") == field_name:
                    return field
    return None


def _find_model_in_spec(
    spec: dict[str, Any], model_name: str,
) -> dict[str, Any] | None:
    """Find a model dict in spec by name."""
    for model in spec.get("models", []):
        if model["name"] == model_name:
            return model
    return None


def _validate_chain_types(
    steps: list[ChainStepSpec],
    spec: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """E18: Validate type compatibility for aggregation and source types.

    Returns list of (severity, code, message) tuples.
    """
    issues: list[tuple[str, str, str]] = []

    for step in steps:
        # Aggregation type checks
        if step.source == "aggregation" and step.aggregation:
            agg = step.aggregation

            # count works on any type
            if agg == "count":
                continue

            # sum, average, min, max require numeric result type
            if agg in ("sum", "average", "min", "max"):
                if step.type not in _NUMERIC_TYPES:
                    issues.append((
                        "error",
                        "E18",
                        f"Aggregation '{agg}' on non-numeric field "
                        f"'{step.model}.{step.field}' (type={step.type}). "
                        f"Only {sorted(_NUMERIC_TYPES)} are supported.",
                    ))

            # weighted_average needs numeric result type
            if agg == "weighted_average":
                if step.type not in _NUMERIC_TYPES:
                    issues.append((
                        "error",
                        "E18",
                        f"weighted_average on non-numeric field "
                        f"'{step.model}.{step.field}' (type={step.type}).",
                    ))

        # lookup source type check
        if step.source == "lookup":
            # Lookup result type should ideally be numeric for mapping
            # but the SOURCE field (what we look up from) should be
            # Selection or Char. If result type is Integer, warn.
            if step.type == "Integer":
                issues.append((
                    "warning",
                    "E18",
                    f"Lookup on Integer field '{step.model}.{step.field}'. "
                    f"Consider using Float for lookup results.",
                ))

    return issues


def _validate_chain_traversal(
    steps: list[ChainStepSpec],
    spec: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """E19: Validate dot-path traversal correctness.

    For each depends entry containing dots, verify:
    1. First segment is a relational field on the model
    2. Second segment exists on the comodel

    Returns list of (severity, code, message) tuples.
    """
    issues: list[tuple[str, str, str]] = []

    for step in steps:
        for dep in step.depends:
            if "." not in dep:
                continue

            segments = dep.split(".", 1)
            rel_field_name = segments[0]
            target_field_name = segments[1]

            # Find the relational field on the step's model
            rel_field = _find_field_in_spec(spec, step.model, rel_field_name)
            if rel_field is None:
                # Field not found -- could be auto-added by chain
                continue

            field_type = rel_field.get("type", "")
            if field_type not in _RELATIONAL_TYPES:
                issues.append((
                    "error",
                    "E19",
                    f"Dot-path '{dep}' in '{step.model}.{step.field}': "
                    f"'{rel_field_name}' is type '{field_type}', not relational. "
                    f"Only {sorted(_RELATIONAL_TYPES)} support dot-path traversal.",
                ))
                continue

            # Check comodel field exists
            comodel_name = rel_field.get("comodel_name")
            if not comodel_name:
                continue

            comodel = _find_model_in_spec(spec, comodel_name)
            if comodel is None:
                issues.append((
                    "warning",
                    "E19",
                    f"Cannot validate dot-path '{dep}': comodel "
                    f"'{comodel_name}' not found in spec models.",
                ))
                continue

            # Check target field on comodel (handle nested dots)
            # For "course_id.credit_hours", we only need to check
            # the immediate next segment on the comodel
            next_segment = target_field_name.split(".", 1)[0]
            target = _find_field_in_spec(spec, comodel_name, next_segment)
            if target is None:
                issues.append((
                    "error",
                    "E19",
                    f"Dot-path '{dep}' in '{step.model}.{step.field}': "
                    f"field '{next_segment}' not found on comodel "
                    f"'{comodel_name}'.",
                ))

    return issues


def _validate_chain_store_propagation(
    steps: list[ChainStepSpec],
    stored_overrides: dict[str, bool] | None = None,
) -> list[tuple[str, str, str]]:
    """E20: Validate store=True propagation through chain.

    A stored computed step depending on a non-stored upstream computed
    step means broken recomputation. direct_input steps are always
    considered stored.

    stored_overrides: optional dict of "model.field" -> bool for testing.

    Returns list of (severity, code, message) tuples.
    """
    issues: list[tuple[str, str, str]] = []
    overrides = stored_overrides or {}

    # Build step lookup by field name for intra-chain dependency checking
    step_by_field: dict[str, ChainStepSpec] = {}
    for step in steps:
        step_by_field[step.field] = step
        step_by_field[f"{step.model}.{step.field}"] = step

    for step in steps:
        if step.source == "direct_input":
            continue

        # Check this step's dependencies against upstream steps
        for dep in step.depends:
            # Only check local (non-dotted) dependencies for store prop
            if "." in dep:
                continue

            upstream = step_by_field.get(dep)
            if upstream is None:
                continue

            if upstream.source == "direct_input":
                continue  # direct_input always stored

            # Check if upstream is stored
            upstream_key = f"{upstream.model}.{upstream.field}"
            this_key = f"{step.model}.{step.field}"

            upstream_stored = overrides.get(upstream_key, True)  # default stored
            this_stored = overrides.get(this_key, True)

            if this_stored and not upstream_stored:
                issues.append((
                    "error",
                    "E20",
                    f"Stored computed field '{step.model}.{step.field}' depends on "
                    f"non-stored computed field '{upstream.model}.{upstream.field}'. "
                    f"This will break recomputation.",
                ))

    return issues


def _validate_chain_cycles(
    all_chains: list[ChainSpec],
    spec: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """E21: Detect cross-chain circular dependencies.

    Builds a directed graph of ALL chain dependencies across ALL chains.
    Uses graphlib.TopologicalSorter for cycle detection.

    Returns list of (severity, code, message) tuples.
    """
    issues: list[tuple[str, str, str]] = []

    graph: dict[str, set[str]] = {}
    for chain in all_chains:
        for step in chain.steps:
            node = f"{step.model}.{step.field}"
            deps: set[str] = set()
            for dep in step.depends:
                if "." in dep:
                    rel_field, target_field = dep.split(".", 1)
                    comodel = _resolve_comodel(spec, step.model, rel_field)
                    if comodel:
                        # Handle nested dots: "course_id.credit_hours"
                        deps.add(f"{comodel}.{target_field}")
                else:
                    local_node = f"{step.model}.{dep}"
                    deps.add(local_node)
            graph[node] = deps

    try:
        ts = TopologicalSorter(graph)
        list(ts.static_order())
    except CycleError as exc:
        cycle_nodes = exc.args[1]
        cycle_str = " -> ".join(str(n) for n in cycle_nodes)
        issues.append((
            "error",
            "E21",
            f"Circular dependency detected across chains: {cycle_str}. "
            f"Break the cycle by removing one dependency.",
        ))

    return issues


def _validate_chain_field_existence(
    steps: list[ChainStepSpec],
    spec: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """E22: Validate that depends paths reference existing fields.

    For every dot-path depends entry, verify the target field exists
    on the target model.

    Returns list of (severity, code, message) tuples.
    """
    issues: list[tuple[str, str, str]] = []

    for step in steps:
        for dep in step.depends:
            if "." not in dep:
                continue

            rel_field_name = dep.split(".", 1)[0]
            target_field_name = dep.split(".", 1)[1]

            # Resolve comodel
            comodel_name = _resolve_comodel(spec, step.model, rel_field_name)
            if comodel_name is None:
                # Try to find field and its comodel_name directly
                rel_field = _find_field_in_spec(spec, step.model, rel_field_name)
                if rel_field:
                    comodel_name = rel_field.get("comodel_name")

            if comodel_name is None:
                continue  # Cannot resolve, skip

            comodel = _find_model_in_spec(spec, comodel_name)
            if comodel is None:
                issues.append((
                    "warning",
                    "E22",
                    f"Cannot validate '{dep}' in '{step.model}.{step.field}': "
                    f"model '{comodel_name}' not in spec.",
                ))
                continue

            # Handle nested dots: check first segment on comodel
            next_segment = target_field_name.split(".", 1)[0]
            target = _find_field_in_spec(spec, comodel_name, next_segment)
            if target is None:
                issues.append((
                    "error",
                    "E22",
                    f"Field '{next_segment}' not found on model "
                    f"'{comodel_name}' (referenced in '{dep}' "
                    f"from '{step.model}.{step.field}').",
                ))

    return issues


def _build_augmented_spec(
    spec: dict[str, Any],
    validated_chains: list[ChainSpec],
) -> dict[str, Any]:
    """Build a spec augmented with chain-declared fields for validation.

    Chain steps declare fields that will be auto-added to models.
    Validators need to see these fields to avoid false positives
    on cross-step dependencies within the same chain set.
    """
    # Collect chain-declared fields per model
    chain_fields: dict[str, list[dict[str, Any]]] = {}
    for chain in validated_chains:
        for step in chain.steps:
            chain_fields.setdefault(step.model, []).append({
                "name": step.field,
                "type": step.type,
            })

    # Build augmented models with chain fields appended
    new_models = []
    for model in spec.get("models", []):
        model_name = model["name"]
        existing_names = {f.get("name") for f in model.get("fields", [])}
        extra = [
            f for f in chain_fields.get(model_name, [])
            if f["name"] not in existing_names
        ]
        if extra:
            new_models.append({
                **model,
                "fields": [*model.get("fields", []), *extra],
            })
        else:
            new_models.append(model)

    return {**spec, "models": new_models}


def _run_all_validators(
    validated_chains: list[ChainSpec],
    spec: dict[str, Any],
) -> None:
    """Run all 5 validators. Raise ValueError on errors, log warnings."""
    all_issues: list[tuple[str, str, str]] = []

    all_steps = [step for chain in validated_chains for step in chain.steps]

    # Build augmented spec so validators can see chain-declared fields
    aug_spec = _build_augmented_spec(spec, validated_chains)

    # E18: Type compatibility
    all_issues.extend(_validate_chain_types(all_steps, aug_spec))

    # E19: Dot-path traversal
    all_issues.extend(_validate_chain_traversal(all_steps, aug_spec))

    # E20: Store propagation (per chain)
    for chain in validated_chains:
        all_issues.extend(_validate_chain_store_propagation(chain.steps))

    # E21: Cross-chain cycles
    all_issues.extend(_validate_chain_cycles(validated_chains, aug_spec))

    # E22: Comodel field existence
    all_issues.extend(_validate_chain_field_existence(all_steps, aug_spec))

    # Separate errors from warnings
    errors = [i for i in all_issues if i[0] == "error"]
    warnings = [i for i in all_issues if i[0] == "warning"]

    for severity, code, msg in warnings:
        logger.warning("[%s] %s", code, msg)

    if errors:
        error_msgs = [f"[{code}] {msg}" for _, code, msg in errors]
        raise ValueError(
            f"Chain validation failed with {len(errors)} error(s):\n"
            + "\n".join(error_msgs)
        )


def _ensure_chain_field(
    model_fields: list[dict[str, Any]],
    step: ChainStepSpec,
) -> list[dict[str, Any]]:
    """Ensure a chain step's field exists on the model.

    If the field is missing, creates a new field dict.
    If it already exists, returns a copy of the list unchanged --
    merging happens in _merge_chain_into_field.

    Returns a NEW list (never mutates the input).
    """
    existing = [f for f in model_fields if f.get("name") == step.field]
    if existing:
        return list(model_fields)

    new_field: dict[str, Any] = {
        "name": step.field,
        "type": step.type,
    }
    if step.digits is not None:
        new_field["digits"] = step.digits
    return [*model_fields, new_field]


def _merge_chain_into_field(
    field: dict[str, Any],
    step: ChainStepSpec,
) -> dict[str, Any]:
    """Merge chain attributes into an existing field dict.

    For direct_input steps: no compute, no store override.
    For computed steps: set store=True, compute, depends.

    Returns a NEW dict (never mutates input).
    """
    if step.source == "direct_input":
        return dict(field)

    merged = {
        **field,
        "store": True,
        "compute": field.get("compute") or f"_compute_{step.field}",
        "depends": list(step.depends),
    }
    return merged


def _build_chain_meta(
    chain: ChainSpec,
    step: ChainStepSpec,
    step_index: int,
) -> dict[str, Any]:
    """Build _chain_meta dict for a chain step."""
    upstream = [
        {
            "model": s.model,
            "field": s.field,
            "source": s.source,
            "type": s.type,
        }
        for s in chain.steps[:step_index]
    ]
    downstream = [
        {
            "model": s.model,
            "field": s.field,
            "source": s.source,
            "type": s.type,
        }
        for s in chain.steps[step_index + 1:]
    ]
    meta: dict[str, Any] = {
        "chain_id": chain.chain_id,
        "chain_description": chain.description,
        "position_in_chain": step_index,
        "total_steps": len(chain.steps),
        "source": step.source,
        "upstream_steps": upstream,
        "downstream_steps": downstream,
    }
    if step.aggregation is not None:
        meta["aggregation"] = step.aggregation
    if step.lookup_table is not None:
        meta["lookup_table"] = dict(step.lookup_table)
    return meta


def _enrich_model(
    model: dict[str, Any],
    steps_for_model: list[tuple[ChainSpec, ChainStepSpec, int]],
) -> dict[str, Any]:
    """Apply all chain steps targeting this model.

    Returns a NEW model dict with enriched fields.
    """
    fields = list(model.get("fields", []))

    for chain, step, step_index in steps_for_model:
        # Ensure field exists
        fields = _ensure_chain_field(fields, step)

        # Merge chain attrs and attach meta
        new_fields = []
        for f in fields:
            if f.get("name") == step.field:
                merged = _merge_chain_into_field(f, step)
                merged["_chain_meta"] = _build_chain_meta(chain, step, step_index)
                new_fields.append(merged)
            else:
                new_fields.append(dict(f))
        fields = new_fields

    return {**model, "fields": fields}


@register_preprocessor(order=22, name="computation_chains")
def _process_computation_chains(spec: dict[str, Any]) -> dict[str, Any]:
    """Enrich computed field specs from sequence-based computation_chains.

    For each validated chain:
    1. Parse via ChainSpec Pydantic model
    2. For each step, ensure field exists on model
    3. Set store=True, compute, depends for non-direct_input steps
    4. Attach _chain_meta with full chain awareness
    5. Store validated chains in spec["_computation_chains"]

    Returns a new spec dict. Pure function.
    """
    raw_chains = spec.get("computation_chains", [])
    if not raw_chains:
        return spec

    # Parse and validate chains -- support both old and new format
    validated_chains: list[ChainSpec] = []
    old_format_chains: list[dict[str, Any]] = []

    for raw in raw_chains:
        # Old per-field format has "field" key, not "chain_id"
        if "field" in raw and "chain_id" not in raw:
            old_format_chains.append(raw)
            continue
        try:
            chain = ChainSpec(**raw)
            validated_chains.append(chain)
        except ValidationError as exc:
            chain_id = raw.get("chain_id", "unknown")
            logger.warning("Skipping invalid chain '%s': %s", chain_id, exc)
            continue

    # If only old-format chains, fall back to legacy behavior
    if not validated_chains and old_format_chains:
        return _process_old_format(spec, old_format_chains)

    if not validated_chains:
        return spec

    # Run validators BEFORE field enrichment (per CONTEXT.md)
    _run_all_validators(validated_chains, spec)

    # Build lookup: model_name -> [(chain, step, step_index)]
    model_steps: dict[str, list[tuple[ChainSpec, ChainStepSpec, int]]] = {}
    for chain in validated_chains:
        for idx, step in enumerate(chain.steps):
            model_steps.setdefault(step.model, []).append((chain, step, idx))

    # Enrich models
    new_models = []
    seen_models: set[str] = set()
    for model in spec.get("models", []):
        model_name = model["name"]
        seen_models.add(model_name)
        steps = model_steps.get(model_name)
        if steps:
            new_models.append(_enrich_model(model, steps))
        else:
            new_models.append(deep_copy_model(model))

    # Warn about chain steps targeting models not in spec
    for model_name in model_steps:
        if model_name not in seen_models:
            logger.warning(
                "Chain step references model '%s' not found in spec models",
                model_name,
            )

    return {
        **spec,
        "models": new_models,
        "_computation_chains": [c.model_dump() for c in validated_chains],
    }


def _process_old_format(
    spec: dict[str, Any],
    chains: list[dict[str, Any]],
) -> dict[str, Any]:
    """Legacy handler for old per-field chain format.

    Maintains backward compatibility with specs using:
      {"field": "model.field_name", "depends_on": [...]}
    """
    chain_lookup: dict[str, dict[str, dict[str, Any]]] = {}
    for chain in chains:
        parts = chain["field"].rsplit(".", 1)
        model_name, field_name = parts[0], parts[1]
        chain_lookup.setdefault(model_name, {})[field_name] = chain

    new_models = []
    for model in spec.get("models", []):
        model_chains = chain_lookup.get(model["name"], {})
        if not model_chains:
            new_models.append(model)
            continue

        new_fields = []
        for field in model.get("fields", []):
            fname = field.get("name", "")
            if fname in model_chains:
                chain = model_chains[fname]
                field = {
                    **field,
                    "depends": chain["depends_on"],
                    "store": True,
                    "compute": field.get("compute", f"_compute_{fname}"),
                }
            new_fields.append(field)
        new_models.append({**model, "fields": new_fields})

    return {**spec, "models": new_models}
