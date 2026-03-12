"""Relationship processing and override_sources initialization."""

from __future__ import annotations

from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.renderer_utils import _to_class, _to_python_var
from odoo_gen_utils.utils.copy import deep_copy_model, has_field as _has_field


@register_preprocessor(order=10, name="relationships")
def _process_relationships(spec: dict[str, Any]) -> dict[str, Any]:
    """Pre-process relationships section, synthesizing through-models.

    Returns a new spec dict with:
    - Through-models appended to spec["models"]
    - One2many fields injected on parent models for through-models
    - Self-referential M2M fields enriched with relation/column params

    Pure function -- does NOT mutate the input spec.
    """
    relationships = spec.get("relationships", [])
    if not relationships:
        return spec

    # Deep-copy models to avoid mutating the original spec
    new_models = [deep_copy_model(m) for m in spec.get("models", [])]

    for rel in relationships:
        if rel["type"] == "m2m_through":
            through_model = _synthesize_through_model(rel, spec)
            new_models.append(through_model)
            _inject_one2many_links(new_models, rel)
        elif rel["type"] == "self_m2m":
            _enrich_self_referential_m2m(new_models, rel)
        elif rel["type"] == "hierarchical":
            _enrich_hierarchical(new_models, rel)
        elif rel["type"] == "delegation":
            _enrich_delegation(new_models, rel)

    return {**spec, "models": new_models}


def _synthesize_through_model(
    rel: dict[str, Any], spec: dict[str, Any]
) -> dict[str, Any]:
    """Synthesize a through-model dict from a m2m_through relationship.

    Returns a model dict suitable for appending to spec["models"].
    Raises ValueError if auto-generated FK names collide with through_fields.
    """
    from_model = rel["from"]
    to_model = rel["to"]
    through_name = rel["through_model"]

    # Derive FK field names from model names
    from_fk = _to_python_var(from_model.rsplit(".", 1)[-1]) + "_id"
    to_fk = _to_python_var(to_model.rsplit(".", 1)[-1]) + "_id"

    # Check for collisions with through_fields
    through_field_names = {f["name"] for f in rel.get("through_fields", [])}
    for fk_name in (from_fk, to_fk):
        if fk_name in through_field_names:
            msg = (
                f"FK name collision: auto-generated '{fk_name}' collides with "
                f"a through_field name in '{through_name}'"
            )
            raise ValueError(msg)

    fields: list[dict[str, Any]] = [
        {
            "name": from_fk,
            "type": "Many2one",
            "comodel_name": from_model,
            "string": from_model.rsplit(".", 1)[-1].replace("_", " ").title(),
            "required": True,
            "ondelete": "cascade",
        },
        {
            "name": to_fk,
            "type": "Many2one",
            "comodel_name": to_model,
            "string": to_model.rsplit(".", 1)[-1].replace("_", " ").title(),
            "required": True,
            "ondelete": "cascade",
        },
    ]
    fields.extend(rel.get("through_fields", []))

    return {
        "name": through_name,
        "description": through_name.rsplit(".", 1)[-1].replace("_", " ").title(),
        "fields": fields,
        "_synthesized": True,
    }


def _inject_one2many_links(
    models: list[dict[str, Any]], rel: dict[str, Any]
) -> None:
    """Inject One2many fields on parent models pointing to through-model.

    Mutates the models list in-place (caller provides a copy).
    Skips injection if a field with the target name already exists.
    """
    through_name = rel["through_model"]
    through_last = through_name.rsplit(".", 1)[-1]
    target_field_name = f"{_to_python_var(through_last)}_ids"

    from_fk = _to_python_var(rel["from"].rsplit(".", 1)[-1]) + "_id"
    to_fk = _to_python_var(rel["to"].rsplit(".", 1)[-1]) + "_id"

    for model in models:
        if model["name"] == rel["from"]:
            if not any(f.get("name") == target_field_name for f in model.get("fields", [])):
                model["fields"].append({
                    "name": target_field_name,
                    "type": "One2many",
                    "comodel_name": through_name,
                    "inverse_name": from_fk,
                    "string": through_last.replace("_", " ").title() + "s",
                })
        elif model["name"] == rel["to"]:
            if not any(f.get("name") == target_field_name for f in model.get("fields", [])):
                model["fields"].append({
                    "name": target_field_name,
                    "type": "One2many",
                    "comodel_name": through_name,
                    "inverse_name": to_fk,
                    "string": through_last.replace("_", " ").title() + "s",
                })


def _enrich_self_referential_m2m(
    models: list[dict[str, Any]], rel: dict[str, Any]
) -> None:
    """Enrich model fields with self-referential M2M relation/column params.

    Mutates the models list in-place (caller provides a copy).
    Adds/replaces fields with explicit relation, column1, column2.
    """
    model_name = rel["model"]
    target_model = next((m for m in models if m["name"] == model_name), None)
    if target_model is None:
        return

    table_base = _to_python_var(model_name)
    field_name = rel["field_name"]
    relation_table = f"{table_base}_{field_name}_rel"

    primary_field: dict[str, Any] = {
        "name": field_name,
        "type": "Many2many",
        "comodel_name": model_name,
        "relation": relation_table,
        "column1": f"{table_base}_id",
        "column2": f"{field_name.rstrip('_ids')}_id",
        "string": rel.get("string", field_name.replace("_", " ").title()),
    }

    inverse_name = rel.get("inverse_field_name")
    inverse_field: dict[str, Any] | None = None
    if inverse_name:
        inverse_field = {
            "name": inverse_name,
            "type": "Many2many",
            "comodel_name": model_name,
            "relation": relation_table,
            "column1": f"{field_name.rstrip('_ids')}_id",  # REVERSED
            "column2": f"{table_base}_id",                   # REVERSED
            "string": rel.get("inverse_string", inverse_name.replace("_", " ").title()),
        }

    # Replace or append fields on the target model
    names_to_remove = {field_name}
    if inverse_name:
        names_to_remove.add(inverse_name)
    fields = [f for f in target_model.get("fields", []) if f.get("name") not in names_to_remove]
    fields.append(primary_field)
    if inverse_field:
        fields.append(inverse_field)
    target_model["fields"] = fields


def _enrich_hierarchical(
    models: list[dict[str, Any]], rel: dict[str, Any]
) -> None:
    """Enrich a model with hierarchical (parent/child) pattern.

    Injects parent_id, parent_path, child_ids fields and sets
    _parent_name metadata. Mutates models in-place (caller provides a copy).

    Relationship spec:
        {"type": "hierarchical", "model": "uni.department",
         "parent_field": "parent_id",  # optional, defaults to parent_id
         "string": "Parent Department"}  # optional
    """
    model_name = rel["model"]
    target = next((m for m in models if m["name"] == model_name), None)
    if target is None:
        return

    parent_field = rel.get("parent_field", "parent_id")
    parent_string = rel.get("string", "Parent")

    if not _has_field(target, parent_field):
        target["fields"].append({
            "name": parent_field,
            "type": "Many2one",
            "comodel_name": model_name,
            "string": parent_string,
            "index": True,
            "ondelete": "cascade",
        })

    if not _has_field(target, "parent_path"):
        target["fields"].append({
            "name": "parent_path",
            "type": "Char",
            "index": True,
            "unaccent": False,
        })

    child_field = rel.get("child_field", "child_ids")
    if not _has_field(target, child_field):
        target["fields"].append({
            "name": child_field,
            "type": "One2many",
            "comodel_name": model_name,
            "inverse_name": parent_field,
            "string": rel.get("child_string", "Children"),
        })

    target["_parent_name"] = parent_field
    target["hierarchical"] = True


def _enrich_delegation(
    models: list[dict[str, Any]], rel: dict[str, Any]
) -> None:
    """Enrich a model with delegation inheritance (_inherits).

    Injects the delegation Many2one field and sets _inherits metadata.
    Mutates models in-place (caller provides a copy).

    Relationship spec:
        {"type": "delegation", "model": "uni.student",
         "delegate_model": "res.partner", "delegate_field": "partner_id",
         "string": "Related Partner", "required": true, "ondelete": "cascade"}
    """
    model_name = rel["model"]
    target = next((m for m in models if m["name"] == model_name), None)
    if target is None:
        return

    delegate_model = rel["delegate_model"]
    delegate_field = rel.get("delegate_field", delegate_model.rsplit(".", 1)[-1] + "_id")
    delegate_string = rel.get("string", delegate_model.rsplit(".", 1)[-1].replace("_", " ").title())

    if not _has_field(target, delegate_field):
        target["fields"].append({
            "name": delegate_field,
            "type": "Many2one",
            "comodel_name": delegate_model,
            "string": delegate_string,
            "required": rel.get("required", True),
            "ondelete": rel.get("ondelete", "cascade"),
            "delegate": True,
        })

    inherits = dict(target.get("_inherits", {}))
    inherits[delegate_model] = delegate_field
    target["_inherits"] = inherits
    target["has_delegation"] = True


def _resolve_comodel(
    spec: dict[str, Any], model_name: str, field_name: str
) -> str | None:
    """Resolve the comodel_name of a relational field on a model."""
    for model in spec.get("models", []):
        if model["name"] == model_name:
            for field in model.get("fields", []):
                if field.get("name") == field_name:
                    return field.get("comodel_name")
    return None


@register_preprocessor(order=15, name="init_override_sources")
def _init_override_sources(spec: dict[str, Any]) -> dict[str, Any]:
    """Initialize override_sources on all models after relationship processing.

    Returns a new spec dict. Pure function -- does NOT mutate the input spec.
    Models that already have ``override_sources`` keep theirs (deep-copied);
    models without it get an empty plain ``dict``.
    """
    new_models = []
    for model in spec.get("models", []):
        if "override_sources" not in model:
            new_models.append({**model, "override_sources": {}})
        else:
            new_models.append(model)
    return {**spec, "models": new_models}
