"""Dependency Graph — Topological sort, cycle detection, tier grouping, generation blocking.

Ported from orchestrator/amil/bin/lib/dependency-graph.cjs (202 lines).
Reads module dependency data from module_status.json and provides:
- Topological ordering for generation sequence
- Circular dependency detection with cycle path reporting
- Tier grouping based on dependency depth
- Generation readiness checking (all deps must be >= "generated")
"""
from __future__ import annotations

from pathlib import Path

from amil_utils.orchestrator.module_status import read_status_file

# ── Constants ────────────────────────────────────────────────────────────────

TIER_LABELS: list[str] = ["foundation", "core", "operations", "communication"]

GENERATED_OR_BEYOND: frozenset[str] = frozenset({"generated", "checked", "shipped"})


# ── Internal helpers ─────────────────────────────────────────────────────────


def _visit(
    name: str,
    modules: dict[str, dict],
    visited: set[str],
    visiting: set[str],
    result: list[str],
    ancestors: list[str],
) -> None:
    """DFS visit for topological sort with cycle detection."""
    if name in visited:
        return

    if name in visiting:
        cycle_start = ancestors.index(name)
        cycle_path = ancestors[cycle_start:] + [name]
        raise ValueError(f"Circular dependency detected: {' -> '.join(cycle_path)}")

    visiting.add(name)

    mod = modules.get(name)
    if mod and mod.get("depends"):
        for dep in mod["depends"]:
            _visit(dep, modules, visited, visiting, result, [*ancestors, name])

    visiting.discard(name)
    visited.add(name)
    result.append(name)


# ── Public API ───────────────────────────────────────────────────────────────


def topo_sort(modules: dict[str, dict]) -> list[str]:
    """DFS-based topological sort with cycle detection.

    Args:
        modules: Mapping of {name: {"depends": [dep1, dep2]}}.

    Returns:
        Module names in dependency order (deps before dependents).

    Raises:
        ValueError: If a circular dependency is detected.
    """
    visited: set[str] = set()
    visiting: set[str] = set()
    result: list[str] = []

    for name in modules:
        _visit(name, modules, visited, visiting, result, [])

    return result


def compute_tiers(modules: dict[str, dict]) -> dict:
    """Compute tier labels based on max dependency depth.

    Returns:
        {"tiers": {label: [names]}, "depths": {name: int}, "order": [names]}
    """
    order = topo_sort(modules)
    depths: dict[str, int] = {}

    # Process in topological order so deps are computed first
    for name in order:
        mod = modules.get(name)
        deps = (mod.get("depends") or []) if mod else []
        if not deps:
            depths[name] = 0
        else:
            depths[name] = max(depths.get(d, 0) for d in deps) + 1

    # Group by tier label
    tiers: dict[str, list[str]] = {}
    for name in order:
        depth = depths[name]
        tier_index = min(depth, len(TIER_LABELS) - 1)
        tier_label = TIER_LABELS[tier_index]
        if tier_label not in tiers:
            tiers[tier_label] = []
        tiers[tier_label].append(name)

    return {"tiers": tiers, "depths": depths, "order": order}


def dep_graph_build(cwd: str | Path) -> dict:
    """Build adjacency list from module_status.json."""
    data = read_status_file(cwd)
    modules: dict[str, dict] = {}

    for name, mod in data.get("modules", {}).items():
        modules[name] = {"depends": mod.get("depends", [])}

    return {"modules": modules}


def dep_graph_order(cwd: str | Path) -> list[str]:
    """Return modules in topological (generation) order."""
    data = read_status_file(cwd)
    modules: dict[str, dict] = {}

    for name, mod in data.get("modules", {}).items():
        modules[name] = {"depends": mod.get("depends", [])}

    return topo_sort(modules)


def dep_graph_tiers(cwd: str | Path) -> dict:
    """Return tier groupings based on dependency depth."""
    data = read_status_file(cwd)
    modules: dict[str, dict] = {}

    for name, mod in data.get("modules", {}).items():
        modules[name] = {"depends": mod.get("depends", [])}

    return compute_tiers(modules)


def dep_graph_can_generate(cwd: str | Path, module_name: str) -> dict:
    """Check if a module's dependencies have all reached 'generated' status or beyond."""
    if not module_name:
        raise ValueError("Usage: dep-graph can-generate <module_name>")

    data = read_status_file(cwd)
    mod = data.get("modules", {}).get(module_name)

    if not mod:
        raise ValueError(f'Module "{module_name}" not found in module_status.json')

    depends = mod.get("depends", [])
    blocked_by: list[dict] = []

    for dep in depends:
        dep_mod = data.get("modules", {}).get(dep)
        dep_status = dep_mod["status"] if dep_mod else "planned"
        if dep_status not in GENERATED_OR_BEYOND:
            blocked_by.append({"module": dep, "status": dep_status})

    return {
        "can_generate": len(blocked_by) == 0,
        "blocked_by": blocked_by,
    }
