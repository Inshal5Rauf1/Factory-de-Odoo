"""Extension module preprocessor (Phase 59).

Normalizes the 'extends' block in a module spec:
- Injects base_module into depends if not present
- Normalizes Selection field 'values' key to 'selection'
- Computes extension_model_files list for init_models.py.j2
- Sets has_extensions flag
"""

from __future__ import annotations

from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.renderer_utils import _to_class, _to_python_var


@register_preprocessor(order=12, name="extensions")
def _process_extensions(spec: dict[str, Any]) -> dict[str, Any]:
    """Pre-process extension entries in the spec.

    If no 'extends' key exists, returns spec unchanged.
    Otherwise:
    - Injects each extension's base_module into depends (no duplicates)
    - Normalizes 'values' -> 'selection' on Selection fields
    - Builds extension_model_files list
    - Sets has_extensions = True

    Returns a new spec dict (immutable pattern).
    """
    extends_raw = spec.get("extends")
    if not extends_raw:
        return spec

    # Build new depends list with base_module injection
    new_depends = list(spec.get("depends", ["base"]))
    new_extends: list[dict[str, Any]] = []
    extension_model_files: list[str] = []

    for ext in extends_raw:
        # Convert Pydantic models to dicts if needed
        if hasattr(ext, "model_dump"):
            ext_dict: dict[str, Any] = ext.model_dump(exclude_none=True)
        else:
            ext_dict = dict(ext)

        base_module = ext_dict.get("base_module", "")
        base_model = ext_dict.get("base_model", "")

        # Inject base_module into depends if not already present
        if base_module and base_module not in new_depends:
            new_depends.append(base_module)

        # Normalize Selection field 'values' -> 'selection'
        new_fields: list[dict[str, Any]] = []
        for field in ext_dict.get("add_fields", []):
            if hasattr(field, "model_dump"):
                field = field.model_dump(exclude_none=True)
            else:
                field = dict(field)
            if field.get("type") == "Selection" and "values" in field:
                field = {**field, "selection": field.pop("values")}
            # Normalize comodel -> comodel_name for template compatibility
            if "comodel" in field and "comodel_name" not in field:
                field = {**field, "comodel_name": field.pop("comodel")}
            new_fields.append(field)

        ext_dict = {**ext_dict, "add_fields": new_fields}

        # Normalize add_computed, add_constraints, add_methods to dicts
        ext_dict["add_computed"] = [
            c.model_dump(exclude_none=True) if hasattr(c, "model_dump") else dict(c)
            for c in ext_dict.get("add_computed", [])
        ]
        ext_dict["add_constraints"] = [
            c.model_dump(exclude_none=True) if hasattr(c, "model_dump") else dict(c)
            for c in ext_dict.get("add_constraints", [])
        ]
        ext_dict["add_methods"] = [
            m.model_dump(exclude_none=True) if hasattr(m, "model_dump") else dict(m)
            for m in ext_dict.get("add_methods", [])
        ]
        ext_dict["view_extensions"] = [
            v.model_dump(exclude_none=True) if hasattr(v, "model_dump") else dict(v)
            for v in ext_dict.get("view_extensions", [])
        ]

        # Compute metadata for this extension
        base_model_var = _to_python_var(base_model)
        class_name = _to_class(base_model)
        ext_dict["base_model_var"] = base_model_var
        ext_dict["class_name"] = class_name
        ext_dict["file_name"] = base_model_var

        extension_model_files.append(base_model_var)
        new_extends.append(ext_dict)

    return {
        **spec,
        "depends": new_depends,
        "extends": new_extends,
        "has_extensions": True,
        "extension_model_files": extension_model_files,
    }
