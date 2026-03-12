"""Deterministic complexity classification for detected method stubs.

Routes each stub to ``"budget"`` (simple, single-field) or ``"quality"``
(cross-model, multi-field, conditional rules, create/write overrides,
action_*/cron_* patterns) based on the locked rules from CONTEXT.md.

This module is a **leaf** -- it imports only from sibling
``stub_detector`` to access the :class:`StubInfo` type.
"""

from __future__ import annotations

from odoo_gen_utils.logic_writer.stub_detector import StubInfo

# Keywords in business rules that indicate conditional logic -> quality
_CONDITIONAL_KEYWORDS: frozenset[str] = frozenset(
    {"if", "when", "unless", "except", "only", "between"}
)


def classify_complexity(
    stub: StubInfo,
    business_rules: list[str],
) -> str:
    """Classify *stub* complexity as ``"budget"`` or ``"quality"``.

    Rules are applied in priority order (first match wins, though all
    quality triggers produce the same result):

    1. **Cross-model depends:** dot notation in ``@api.depends`` decorator
    2. **Multiple target fields:** more than one field set in compute body
    3. **Conditional business rules:** keywords like if/when/unless in rules
    4. **create/write overrides:** method named ``create`` or ``write``
    5. **action_*/cron_*:** method starts with ``action_`` or ``_cron_``
    6. **Default:** ``"budget"``
    """
    # Rule 1: Cross-model depends (dot in @api.depends)
    if _has_cross_model_depends(stub):
        return "quality"

    # Rule 2: Multiple target fields
    if len(stub.target_fields) > 1:
        return "quality"

    # Rule 3: Conditional business rules
    if _has_conditional_rules(business_rules):
        return "quality"

    # Rule 4: create/write overrides
    if stub.method_name in ("create", "write"):
        return "quality"

    # Rule 5: action_* / _cron_* patterns
    if stub.method_name.startswith("action_") or stub.method_name.startswith(
        "_cron_"
    ):
        return "quality"

    # Rule 6: Default
    return "budget"


def _has_cross_model_depends(stub: StubInfo) -> bool:
    """Return ``True`` if the stub decorator has dot notation in @api.depends args.

    The decorator text looks like ``@api.depends("partner_id.name", "field")``.
    We need dots *inside* the quoted argument strings, not in ``api.depends``
    itself.  Extract the argument portion (after the opening paren) and check
    for dots in the quoted field names.
    """
    dec = stub.decorator
    if "depends" not in dec:
        return False
    # Extract the arguments portion: everything between ( and )
    paren_start = dec.find("(")
    if paren_start == -1:
        return False
    args_portion = dec[paren_start + 1 :]
    # Check for dot in quoted strings within the arguments
    # A dot in something like "partner_id.name" indicates cross-model
    return "." in args_portion


def _has_conditional_rules(business_rules: list[str]) -> bool:
    """Return ``True`` if any business rule contains conditional keywords."""
    for rule in business_rules:
        words = set(rule.lower().split())
        if words & _CONDITIONAL_KEYWORDS:
            return True
    return False
