"""Circular Dependency Breaker — Resolves circular module dependencies.

Ported from orchestrator/amil/bin/lib/circular-dep-breaker.cjs (120 lines).

Strategy: When modules A and B circularly reference each other:
1. Identify which direction is "primary" (the Many2one / FK owner side)
2. Build the primary module first WITHOUT the back-reference
3. Build the secondary module WITH its forward reference
4. Update the primary module to add the back-reference (patch round)
"""
from __future__ import annotations


def analyze_circular_pair(circular_risk: dict, prov_registry: object) -> dict:
    """Analyze a circular dependency pair and determine build order.

    The side with more Many2one references is "primary" (owns the FK).
    """
    mod_a, mod_b = circular_risk["modules"]
    refs_a_to_b = circular_risk["refs_a_to_b"]
    refs_b_to_a = circular_risk["refs_b_to_a"]

    m2o_a_to_b = [r for r in refs_a_to_b if r.get("type", "").lower() == "many2one"]
    m2o_b_to_a = [r for r in refs_b_to_a if r.get("type", "").lower() == "many2one"]

    if len(m2o_a_to_b) >= len(m2o_b_to_a):
        primary = mod_a
        secondary = mod_b
        deferred_refs = refs_b_to_a
    else:
        primary = mod_b
        secondary = mod_a
        deferred_refs = refs_a_to_b

    return {
        "primary": primary,
        "secondary": secondary,
        "build_order": [primary, secondary],
        "deferred_refs": deferred_refs,
        "patch_required": len(deferred_refs) > 0,
    }


def generate_patch_spec(resolution: dict) -> dict | None:
    """Generate patch spec for deferred references.

    After both modules are built, this produces the field additions
    needed to complete the circular reference.
    """
    if not resolution["patch_required"]:
        return None

    patches = []
    for ref in resolution["deferred_refs"]:
        patches.append({
            "module": ref.get("from_module"),
            "model": ref.get("from_model"),
            "field": {
                "name": ref.get("field"),
                "type": ref.get("type", "Many2one"),
                "comodel_name": ref.get("to_model"),
            },
        })

    return {
        "module": resolution["primary"],
        "patches": patches,
    }


def plan_build_order(
    topo_order: list[str],
    circular_risks: list[dict],
    prov_registry: object,
) -> dict:
    """Plan build order considering circular dependencies.

    Augments the topological sort with circular dep resolution.
    Returns {"order": [...], "patch_rounds": [...]}.
    """
    if not circular_risks:
        return {"order": list(topo_order), "patch_rounds": []}

    resolutions = [
        analyze_circular_pair(cr, prov_registry) for cr in circular_risks
    ]

    adjusted_order = list(topo_order)
    for res in resolutions:
        pri = res["primary"]
        sec = res["secondary"]
        if pri in adjusted_order and sec in adjusted_order:
            pri_idx = adjusted_order.index(pri)
            sec_idx = adjusted_order.index(sec)
            if pri_idx > sec_idx:
                adjusted_order.pop(pri_idx)
                adjusted_order.insert(sec_idx, pri)

    patch_rounds = [
        generate_patch_spec(r)
        for r in resolutions
        if r["patch_required"]
    ]
    patch_rounds = [p for p in patch_rounds if p is not None]

    return {"order": adjusted_order, "patch_rounds": patch_rounds}
