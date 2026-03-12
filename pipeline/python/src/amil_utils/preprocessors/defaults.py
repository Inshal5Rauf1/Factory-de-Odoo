"""Default field injection preprocessor.

TMPL-04: Auto-injects an ``active`` field into every non-transient model
that does not already declare one, unless the model opts out via
``no_active: true``.

Runs at order=5 so subsequent preprocessors can rely on the field's
presence (e.g. archival, security).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from amil_utils.preprocessors._registry import register_preprocessor


@register_preprocessor(order=5, name="defaults")
def inject_default_fields(spec: dict[str, Any]) -> dict[str, Any]:
    """Ensure non-transient models have an ``active`` field."""
    spec = deepcopy(spec)
    for model in spec.get("models", []):
        if model.get("transient") or model.get("is_transient"):
            continue
        if model.get("no_active"):
            continue
        field_names = {f["name"] for f in model.get("fields", [])}
        if "active" not in field_names:
            model.setdefault("fields", []).append(
                {
                    "name": "active",
                    "type": "Boolean",
                    "default": True,
                    "string": "Active",
                    "index": True,
                }
            )
    return spec
