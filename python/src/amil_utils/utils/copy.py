"""Canonical deep-copy utilities for preprocessor model dicts.

Consolidates 4+ ad-hoc copy patterns into one reusable function.
All preprocessors should use ``deep_copy_model`` instead of inline
``{**model, "fields": list(model.get("fields", []))}`` variants.
"""

from __future__ import annotations

from typing import Any

# Keys whose values are mutable lists that must be copied.
_LIST_KEYS = frozenset({
    "fields",
    "sql_constraints",
    "complex_constraints",
    "record_rule_scopes",
    "approval_action_methods",
    "approval_record_rules",
    "editable_fields",
    "reject_allowed_from",
    "notification_templates",
})

# Keys whose values are dicts-of-sets (override_sources pattern).
_DICT_OF_SETS_KEYS = frozenset({
    "override_sources",
})


def deep_copy_model(model: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of a preprocessor model dict.

    Copies:
    - Top-level dict (shallow spread)
    - All known mutable list values (new list of same items)
    - ``override_sources`` dict-of-sets (new dict, new sets)

    Items *inside* lists (individual field dicts, constraint dicts) are
    NOT deep-copied -- they are new list references to the same dicts.
    If a preprocessor needs to mutate individual field dicts, it should
    copy those explicitly (e.g. ``dict(field)``).
    """
    copied = {**model}

    for key in _LIST_KEYS:
        if key in copied:
            copied[key] = list(copied[key])

    for key in _DICT_OF_SETS_KEYS:
        if key in copied:
            copied[key] = {k: set(v) for k, v in copied[key].items()}

    return copied


def has_field(model: dict[str, Any], name: str) -> bool:
    """Check if a field with the given name exists in model's fields."""
    return any(f.get("name") == name for f in model.get("fields", []))


def merge_override_source(
    model: dict[str, Any], method: str, source: str
) -> None:
    """Add *source* to ``model["override_sources"][method]`` (in-place).

    Works with plain ``dict`` of ``set`` values (NOT ``defaultdict``).
    Creates the ``override_sources`` dict and/or the inner set if absent.

    Call on an already-copied model dict (from ``deep_copy_model``).
    """
    sources = model.setdefault("override_sources", {})
    sources.setdefault(method, set()).add(source)
