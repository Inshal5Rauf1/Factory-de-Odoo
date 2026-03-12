"""Bulk operations preprocessor: enriches spec with wizard model dicts and rendering context.

Registered at order=85 (after approval@80, before notifications@90).
Sets has_bulk_operations, bulk_wizards, auto-adds "bus" to depends,
and assigns default batch_size per operation type.
"""

from __future__ import annotations

from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.renderer_utils import _to_class, _to_python_var

# Default batch sizes per operation type
_BATCH_DEFAULTS: dict[str, int] = {
    "state_transition": 50,
    "create_related": 100,
    "update_fields": 200,
}


def _enrich_bulk_op(op: dict[str, Any]) -> dict[str, Any]:
    """Enrich a single bulk operation dict with computed metadata.

    Sets batch_size from defaults if None, computes wizard_var,
    source_model_var, and source_model_class.
    """
    enriched = {**op}

    # Assign default batch_size if not specified
    if enriched.get("batch_size") is None:
        enriched["batch_size"] = _BATCH_DEFAULTS.get(
            enriched.get("operation", ""), 100
        )

    # Computed names for template rendering
    enriched["wizard_var"] = _to_python_var(enriched["wizard_model"])
    enriched["source_model_var"] = _to_python_var(enriched["source_model"])
    enriched["source_model_class"] = _to_class(enriched["source_model"])

    return enriched


def _build_wizard_model_dict(op: dict[str, Any]) -> dict[str, Any]:
    """Build a wizard model dict for a bulk operation.

    Returns a model dict with _name, state machine fields, result fields,
    and any wizard_fields from the spec.
    """
    wizard_model_name = op["wizard_model"]
    line_model_name = f"{wizard_model_name}.line"

    # Base fields for every bulk wizard
    fields: list[dict[str, Any]] = [
        {
            "name": "state",
            "type": "Selection",
            "selection": [
                ["select", "Select Records"],
                ["preview", "Preview"],
                ["process", "Processing"],
                ["done", "Complete"],
            ],
            "default": "select",
            "required": True,
        },
        {
            "name": "record_count",
            "type": "Integer",
            "string": "Record Count",
            "compute": "_compute_record_count",
        },
        {
            "name": "preview_line_ids",
            "type": "One2many",
            "comodel_name": line_model_name,
            "inverse_name": "wizard_id",
            "string": "Preview Lines",
        },
        {
            "name": "success_count",
            "type": "Integer",
            "string": "Success Count",
            "readonly": True,
        },
        {
            "name": "fail_count",
            "type": "Integer",
            "string": "Fail Count",
            "readonly": True,
        },
        {
            "name": "error_log",
            "type": "Text",
            "string": "Error Log",
            "readonly": True,
        },
    ]

    # Add wizard_fields from spec (extra fields the user fills)
    for wf in op.get("wizard_fields", []):
        field_dict: dict[str, Any] = {
            "name": wf["name"],
            "type": wf["type"],
            "required": wf.get("required", False),
        }
        if wf.get("comodel"):
            field_dict["comodel_name"] = wf["comodel"]
        fields.append(field_dict)

    return {
        "_name": wizard_model_name,
        "name": wizard_model_name,
        "description": op.get("name", "Bulk Operation Wizard"),
        "fields": fields,
        "is_transient": True,
        "is_bulk_wizard": True,
        "bulk_op": op,
    }


def _build_wizard_line_dict(op: dict[str, Any]) -> dict[str, Any]:
    """Build a wizard line model dict for preview records.

    Returns a model dict with wizard_id M2o, preview_fields as related
    fields, and a selected Boolean.
    """
    wizard_model_name = op["wizard_model"]
    line_model_name = f"{wizard_model_name}.line"

    fields: list[dict[str, Any]] = [
        {
            "name": "wizard_id",
            "type": "Many2one",
            "comodel_name": wizard_model_name,
            "string": "Wizard",
            "ondelete": "cascade",
            "required": True,
        },
        {
            "name": "selected",
            "type": "Boolean",
            "default": True,
            "string": "Selected",
        },
    ]

    # Add preview_fields as related fields (simplified -- actual type resolution
    # happens at render time)
    for field_name in op.get("preview_fields", []):
        fields.append({
            "name": field_name,
            "type": "Char",
            "string": field_name.replace("_", " ").title(),
            "related": True,
        })

    return {
        "_name": line_model_name,
        "name": line_model_name,
        "description": f"{op.get('name', 'Bulk')} Preview Line",
        "fields": fields,
        "is_transient": True,
        "is_bulk_wizard_line": True,
        "bulk_op": op,
    }


@register_preprocessor(order=85, name="bulk_operations")
def _process_bulk_operations(spec: dict[str, Any]) -> dict[str, Any]:
    """Enrich spec with bulk operation rendering context.

    If no ``bulk_operations`` key or empty list, returns spec unchanged.
    Otherwise:
    - Enriches each operation with computed metadata and default batch_size
    - Builds wizard + line model dicts for rendering
    - Auto-adds "bus" to depends for progress notifications
    - Sets has_bulk_operations flag
    - Sets bulk_post_processing_batch_size on source models
    """
    bulk_ops = spec.get("bulk_operations", [])
    if not bulk_ops:
        return spec

    # Handle Pydantic models -- convert to dicts
    enriched_ops: list[dict[str, Any]] = []
    for op in bulk_ops:
        if hasattr(op, "model_dump"):
            op_dict = op.model_dump()
        elif isinstance(op, dict):
            op_dict = op
        else:
            continue
        enriched_ops.append(_enrich_bulk_op(op_dict))

    # Build wizard + line model dicts
    extra_wizards: list[dict[str, Any]] = []
    for op in enriched_ops:
        extra_wizards.append(_build_wizard_model_dict(op))
        if op.get("preview_fields"):
            extra_wizards.append(_build_wizard_line_dict(op))

    # Auto-add "bus" to depends (immutable -- new list)
    old_depends = spec.get("depends", ["base"])
    new_depends = list(old_depends)
    if "bus" not in new_depends:
        new_depends.append("bus")

    # Set bulk_post_processing_batch_size on matching source models
    models = spec.get("models", [])
    source_batch_map: dict[str, int] = {}
    for op in enriched_ops:
        source_batch_map[op["source_model"]] = op["batch_size"]

    new_models = []
    for model in models:
        model_dict = dict(model) if not isinstance(model, dict) else {**model}
        model_name = model_dict.get("name", "")
        if model_name in source_batch_map:
            model_dict["bulk_post_processing_batch_size"] = source_batch_map[model_name]
        new_models.append(model_dict)

    return {
        **spec,
        "has_bulk_operations": True,
        "bulk_operations": enriched_ops,
        "bulk_wizards": extra_wizards,
        "depends": new_depends,
        "models": new_models,
    }
