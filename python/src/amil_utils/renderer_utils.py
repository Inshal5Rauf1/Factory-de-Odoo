"""Shared utility functions and constants for the Odoo module renderer."""

from __future__ import annotations

import re
from graphlib import CycleError, TopologicalSorter
from typing import Any


# Sequence field names that trigger ir.sequence generation.
SEQUENCE_FIELD_NAMES: frozenset[str] = frozenset({"reference", "ref", "number", "code", "sequence"})

# Phase 26: Monetary field name patterns that trigger Float -> Monetary rewrite.
MONETARY_FIELD_PATTERNS: frozenset[str] = frozenset({
    "amount", "fee", "salary", "price", "cost", "balance",
    "total", "subtotal", "tax", "discount", "payment",
    "revenue", "expense", "budget", "wage", "rate",
    "charge", "premium", "debit", "credit",
})

# Phase 33: Indexable field types for automatic index=True enrichment.
INDEXABLE_TYPES: frozenset[str] = frozenset({
    "Char", "Integer", "Float", "Date", "Datetime",
    "Boolean", "Selection", "Many2one", "Monetary",
})

# Phase 33: Virtual/non-indexable field types (never get index=True).
NON_INDEXABLE_TYPES: frozenset[str] = frozenset({
    "One2many", "Many2many", "Html", "Text", "Binary",
})


def _is_monetary_field(field: dict[str, Any]) -> bool:
    """Check whether a field should be rendered as fields.Monetary.

    Returns True when:
    - field type is already "Monetary", OR
    - field type is "Float" AND the field name contains a monetary pattern keyword.

    Returns False when:
    - field has explicit ``"monetary": False`` opt-out
    - field type is not Float/Monetary
    - field name does not contain any monetary pattern
    """
    if field.get("monetary") is False:
        return False
    field_type = field.get("type", "")
    if field_type == "Monetary":
        return True
    if field_type != "Float":
        return False
    name = field.get("name", "")
    return any(pattern in name for pattern in MONETARY_FIELD_PATTERNS)


def _model_ref(name: str) -> str:
    """Convert Odoo dot-notation model name to external ID format.

    Example: "inventory.item" -> "model_inventory_item"
    """
    return f"model_{name.replace('.', '_')}"


def _to_class(name: str) -> str:
    """Convert Odoo dot-notation model name to Python class name.

    Example: "inventory.item" -> "InventoryItem"
    """
    return "".join(word.capitalize() for word in name.replace(".", "_").split("_"))


def _to_python_var(name: str) -> str:
    """Convert Odoo dot-notation model name to Python variable name.

    Example: "inventory.item" -> "inventory_item"
    """
    return name.replace(".", "_")


def _to_xml_id(name: str) -> str:
    """Convert Odoo dot-notation model name to XML id attribute format.

    Example: "inventory.item" -> "inventory_item"
    """
    return name.replace(".", "_")


def _topologically_sort_fields(
    computed_fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort computed fields so dependencies come before dependents.

    Uses graphlib.TopologicalSorter. If fields have no inter-dependencies
    (common case), preserves original order.
    """
    field_names = {f["name"] for f in computed_fields}
    field_map = {f["name"]: f for f in computed_fields}

    graph: dict[str, set[str]] = {}
    for field in computed_fields:
        deps = set()
        for dep in field.get("depends", []):
            # Only consider local dependencies (no dots) that are
            # themselves computed fields
            if "." not in dep and dep in field_names:
                deps.add(dep)
        graph[field["name"]] = deps

    try:
        ts = TopologicalSorter(graph)
        sorted_names = list(ts.static_order())
    except CycleError:
        # Intra-model cycles caught by _validate_no_cycles already
        return computed_fields

    # Rebuild list in sorted order
    result = []
    for name in sorted_names:
        if name in field_map:
            result.append(field_map[name])
    return result
