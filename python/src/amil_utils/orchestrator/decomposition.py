"""Decomposition — Merge agent outputs into a unified module decomposition.

Ported from orchestrator/amil/bin/lib/decomposition.cjs (255 lines, since deleted).
Provides:
- merge_decomposition: 5-step merge of agent JSON files
- format_decomposition_table: Structured text presentation
- generate_roadmap_markdown: Flat ROADMAP.md content
"""
from __future__ import annotations

import json
from pathlib import Path

from amil_utils.orchestrator.dependency_graph import TIER_LABELS, compute_tiers

# ── Internal helpers ─────────────────────────────────────────────────────────


def _tier_label(depth: int) -> str:
    """Map a dependency depth to a tier label."""
    return TIER_LABELS[min(depth, len(TIER_LABELS) - 1)]


# ── Public API ───────────────────────────────────────────────────────────────


def merge_decomposition(research_dir: str | Path, cwd: str | Path) -> dict:
    """5-step merge of 4 agent JSON outputs into decomposition.json.

    Args:
        research_dir: Path to directory containing agent outputs.
        cwd: Project root (unused but passed for consistency).

    Returns:
        The decomposition object.
    """
    research_dir = Path(research_dir)

    # Step 1: Read module-boundaries.json as base module list
    boundaries = json.loads((research_dir / "module-boundaries.json").read_text(encoding="utf-8"))
    modules = [
        {
            "name": m["name"],
            "description": m["description"],
            "models": list(m["models"]),
            "base_depends": list(m["base_depends"]),
            "custom_depends": [],
            "estimated_complexity": m["estimated_complexity"],
            "build_recommendation": "build_new",
            "oca_module": None,
            "tier": "foundation",
            "tier_index": 0,
            "computation_chains": [],
        }
        for m in boundaries["modules"]
    ]
    module_map = {m["name"]: m for m in modules}

    # Step 2: Cross-reference OCA analysis — annotate build_recommendation
    oca = json.loads((research_dir / "oca-analysis.json").read_text(encoding="utf-8"))
    for finding in oca["findings"]:
        mod = module_map.get(finding["odoo_module"])
        if mod:
            mod["build_recommendation"] = finding["recommendation"]
            mod["oca_module"] = finding.get("oca_module")

    # Step 3: Extract custom depends, run topoSort + computeTiers
    dep_map = json.loads((research_dir / "dependency-map.json").read_text(encoding="utf-8"))
    custom_module_names = {m["name"] for m in modules}

    for dep in dep_map["dependencies"]:
        mod = module_map.get(dep["module"])
        if mod:
            mod["custom_depends"] = [
                d for d in dep["depends_on"] if d in custom_module_names
            ]

    # Build adjacency for topoSort (custom deps only)
    adjacency = {mod["name"]: {"depends": mod["custom_depends"]} for mod in modules}
    tier_result = compute_tiers(adjacency)

    for mod in modules:
        depth = tier_result["depths"].get(mod["name"], 0)
        mod["tier"] = _tier_label(depth)
        mod["tier_index"] = depth

    # Step 4: Attach computation chains by step prefix matching
    chains = json.loads((research_dir / "computation-chains.json").read_text(encoding="utf-8"))
    for chain in chains["chains"]:
        for mod in modules:
            has_match = any(step.startswith(mod["name"] + ".") for step in chain["steps"])
            if has_match:
                mod["computation_chains"].append({
                    "name": chain["name"],
                    "description": chain["description"],
                    "steps": list(chain["steps"]),
                    "cross_module": chain["cross_module"],
                })

    # Step 5: Generate warnings
    warnings: list[str] = []

    for mod in modules:
        if mod["estimated_complexity"] == "unknown":
            warnings.append(f'Module "{mod["name"]}" has unknown complexity — review manually')

    for mod in modules:
        same_tier_deps = [
            d for d in mod["custom_depends"]
            if module_map.get(d) and module_map[d]["tier"] == mod["tier"]
        ]
        if len(same_tier_deps) >= 3:
            warnings.append(
                f'Module "{mod["name"]}" has {len(same_tier_deps)} same-tier dependencies — consider splitting'
            )

    # Build tiers object
    tiers: dict[str, list[str]] = {}
    for mod in modules:
        if mod["tier"] not in tiers:
            tiers[mod["tier"]] = []
        tiers[mod["tier"]].append(mod["name"])

    decomposition = {
        "modules": modules,
        "tiers": tiers,
        "generation_order": tier_result["order"],
        "computation_chains": chains["chains"],
        "warnings": warnings,
    }

    # Write decomposition.json
    (research_dir / "decomposition.json").write_text(
        json.dumps(decomposition, indent=2), encoding="utf-8"
    )

    return decomposition


def format_decomposition_table(decomposition: dict) -> str:
    """Format decomposition as structured text for human review."""
    modules = decomposition["modules"]
    tiers = decomposition["tiers"]
    computation_chains = decomposition.get("computation_chains", [])
    warnings = decomposition.get("warnings", [])
    tier_count = len(tiers)

    lines: list[str] = []
    lines.append(f"ERP MODULE DECOMPOSITION -- {len(modules)} modules across {tier_count} tiers")
    lines.append("")

    # Group by tier in TIER_LABELS order
    tier_num = 0
    for label in TIER_LABELS:
        tier_modules = tiers.get(label)
        if not tier_modules:
            continue
        tier_num += 1
        capital_label = label[0].upper() + label[1:]
        note = "generate first" if tier_num == 1 else "depends on previous"
        lines.append(f"TIER {tier_num}: {capital_label} ({note})")
        lines.append("  | Module | Models | Build | Depends |")
        lines.append("  |--------|--------|-------|---------|")
        for mod_name in tier_modules:
            mod = next((m for m in modules if m["name"] == mod_name), None)
            if not mod:
                continue
            all_deps = ", ".join([*mod["base_depends"], *mod["custom_depends"]])
            build_label = (
                "NEW" if mod["build_recommendation"] == "build_new"
                else mod["build_recommendation"].upper()
            )
            lines.append(f"  | {mod['name']} | {len(mod['models'])} | {build_label} | {all_deps} |")
        lines.append("")

    # Computation chains
    if computation_chains:
        lines.append("COMPUTATION CHAINS (cross-module):")
        for i, chain in enumerate(computation_chains, 1):
            lines.append(f"  {i}. {chain['name']}: {' -> '.join(chain['steps'])}")
        lines.append("")

    # Warnings
    if warnings:
        lines.append("WARNINGS:")
        for w in warnings:
            lines.append(f"  - {w}")
        lines.append("")

    lines.append("Approve this decomposition? (yes / modify / regenerate)")

    return "\n".join(lines)


def generate_roadmap_markdown(decomposition: dict) -> str:
    """Generate flat ROADMAP.md content from decomposition."""
    modules = decomposition["modules"]
    generation_order = decomposition["generation_order"]
    module_map = {m["name"]: m for m in modules}

    lines: list[str] = []
    for i, name in enumerate(generation_order, 1):
        mod = module_map.get(name)
        if not mod:
            continue

        all_deps = ", ".join([*mod["base_depends"], *mod["custom_depends"]])
        build_label = (
            "NEW" if mod["build_recommendation"] == "build_new"
            else mod["build_recommendation"].upper()
        )
        tier_index = mod["tier_index"] + 1
        tier_name = mod["tier"][0].upper() + mod["tier"][1:]

        lines.append(f"### Phase {i}: {name}")
        lines.append(f"- Tier: {tier_index} ({tier_name})")
        lines.append(f"- Models: {', '.join(mod['models'])}")
        lines.append(f"- Depends: {all_deps}")
        lines.append(f"- Build: {build_label}")
        lines.append("- Status: not_started")
        lines.append("")

    return "\n".join(lines)
