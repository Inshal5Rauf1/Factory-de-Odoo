"""Spec Completeness — Scores how well-specified a module is (0-100).

Ported from orchestrator/amil/bin/lib/spec-completeness.cjs (225 lines).

Scoring drives automated triage:
- Score >= 70: ready for spec generation (no discussion needed)
- Score 40-69: needs brief discussion (1-2 questions)
- Score < 40: needs full discussion (5+ questions)
"""
from __future__ import annotations

import math


def score_module(module_data: dict, all_module_names: list[str] | None = None) -> dict:
    """Score a single module's completeness (0-100)."""
    score = 0
    gaps: list[str] = []
    cross_module_issues: list[str] = []

    # Models defined: +20
    models = module_data.get("models", [])
    if models:
        score += 20
    else:
        gaps.append("No models defined — need model names and primary fields")

    # Model detail (each model has >2 fields): +15
    if models:
        detailed = [m for m in models if len(m.get("fields", [])) > 2]
        if len(detailed) == len(models):
            score += 15
        else:
            under = [m for m in models if len(m.get("fields", [])) <= 2]
            names = ", ".join(m.get("name", str(m)) for m in under)
            gaps.append(f"{len(under)} model(s) have <=2 fields: {names}")

    # Security roles: +15
    security = module_data.get("security", {})
    if security.get("roles") and len(security["roles"]) > 0:
        score += 15
    else:
        gaps.append("No security roles defined — who can CRUD?")

    # Workflow states: +10
    if module_data.get("workflow") or module_data.get("states"):
        score += 10
    else:
        gaps.append("No workflow/states — is this a simple CRUD or stateful?")

    # Dependencies: +10
    deps = module_data.get("depends") or module_data.get("base_depends") or []
    if deps:
        score += 10
    else:
        gaps.append("No dependencies listed")

    # Description quality: +10
    if len(module_data.get("description", "")) > 20:
        score += 10
    else:
        gaps.append("Description too brief — need functional purpose")

    # Computation chains: +10
    if module_data.get("computation_chains"):
        score += 10

    # View hints: +10
    if module_data.get("view_hints"):
        score += 10

    # Cross-module scoring (bonus points)
    if all_module_names and len(all_module_names) > 0:
        unresolved_refs: list[str] = []
        for field in (f for m in models for f in m.get("fields", [])):
            comodel = field.get("comodel_name")
            if comodel and not any(
                comodel.startswith(prefix)
                for prefix in ("res.", "ir.", "mail.")
            ):
                unresolved_refs.append(comodel)

        if not unresolved_refs:
            score += 5
        else:
            cross_module_issues.append(
                f"Unresolved comodel references: {', '.join(unresolved_refs)}"
            )

        own_model_names = {m.get("name", m) for m in models}
        has_circular_risk = any(ref in own_model_names for ref in unresolved_refs)
        if not has_circular_risk:
            score += 5
        else:
            cross_module_issues.append(
                "Circular dependency risk: comodel references own models via external path"
            )

    # Determine discussion depth
    if score >= 70:
        discussion_depth = "none"
    elif score >= 40:
        discussion_depth = "brief"
    else:
        discussion_depth = "full"

    return {
        "score": score,
        "gaps": gaps,
        "cross_module_issues": cross_module_issues,
        "ready": score >= 70,
        "needs_discussion": score < 70,
        "discussion_depth": discussion_depth,
    }


def score_all_modules(
    decomposition: dict,
    all_module_names: list[str] | None = None,
) -> dict:
    """Score all modules in a decomposition."""
    modules = decomposition.get("modules", [])
    names = all_module_names or [m["name"] for m in modules]
    return {mod["name"]: score_module(mod, names) for mod in modules}


def get_discussion_batches(scores: dict, module_data: dict) -> list[dict]:
    """Group underspecified modules by tier and depth for batch discussion."""
    full_discussion = [
        name for name, s in scores.items() if s["discussion_depth"] == "full"
    ]
    brief_discussion = [
        name for name, s in scores.items() if s["discussion_depth"] == "brief"
    ]

    tiers: dict[str, dict] = {}
    for mod in module_data.get("modules", []):
        name = mod["name"]
        in_full = name in full_discussion
        in_brief = name in brief_discussion
        if not in_full and not in_brief:
            continue

        tier = mod.get("tier", "unknown")
        depth = "full" if in_full else "brief"
        key = f"{tier}-{depth}"
        if key not in tiers:
            tiers[key] = {"tier": tier, "depth": depth, "modules": []}
        tiers[key]["modules"].append({
            "name": name,
            "score": scores[name]["score"],
            "gaps": scores[name]["gaps"],
            "cross_module_issues": scores[name]["cross_module_issues"],
        })

    # Sort: full before brief, then by tier
    sorted_keys = sorted(tiers.keys(), key=lambda k: (
        0 if k.split("-")[1] == "full" else 1,
        k.split("-")[0],
    ))

    batches: list[dict] = []
    for key in sorted_keys:
        entry = tiers[key]
        modules = entry["modules"]
        for i in range(0, len(modules), 5):
            batches.append({
                "tier": entry["tier"],
                "depth": entry["depth"],
                "modules": modules[i:i + 5],
            })

    return batches


def get_discussion_summary(scores: dict) -> dict:
    """Summarize discussion needs across all scored modules."""
    total = len(scores)
    if total == 0:
        return {
            "total": 0, "ready": 0, "brief": 0, "full": 0,
            "avg_score": 0, "estimated_batches": 0, "estimated_questions": 0,
        }

    vals = list(scores.values())
    ready = sum(1 for s in vals if s.get("ready"))
    brief = sum(1 for s in vals if s.get("discussion_depth") == "brief")
    full = sum(1 for s in vals if s.get("discussion_depth") == "full")
    avg_score = round(sum(s["score"] for s in vals) / total)

    return {
        "total": total,
        "ready": ready,
        "brief": brief,
        "full": full,
        "avg_score": avg_score,
        "estimated_batches": math.ceil(full / 5) + math.ceil(brief / 5),
        "estimated_questions": full * 5 + brief * 2,
    }
