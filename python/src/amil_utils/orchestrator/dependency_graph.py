"""Dependency Graph — Topological sort, cycle detection, tier grouping, generation blocking.

Ported from orchestrator/amil/bin/lib/dependency-graph.cjs (202 lines, since deleted).
Reads module dependency data from module_status.json and provides:
- Topological ordering for generation sequence
- Circular dependency detection with cycle path reporting
- Tier grouping based on dependency depth
- Generation readiness checking (all deps must be >= "generated")
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from amil_utils.orchestrator.module_status import read_status_file


@lru_cache(maxsize=1)
def _load_external_module_names() -> frozenset[str]:
    """Load known Odoo module names that are external (not generated)."""
    data_file = Path(__file__).parent.parent / "data" / "known_odoo_models.json"
    try:
        raw = json.loads(data_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "models" in raw:
            modules = set()
            for model_name in raw["models"]:
                parts = model_name.split(".")
                if parts:
                    modules.add(parts[0])
            modules.update({"base", "web", "mail", "account", "stock", "hr", "sale", "purchase", "project", "crm", "website", "portal", "board", "bus"})
            return frozenset(modules)
    except (OSError, json.JSONDecodeError):
        pass
    return frozenset({"base", "web", "mail"})

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
    *,
    strict: bool = True,
    external_modules: frozenset[str] | None = None,
) -> None:
    """DFS visit for topological sort with cycle detection.

    Args:
        strict: If True (default), raise ValueError on unknown dependencies.
                If False, log a warning and skip the phantom.
        external_modules: Known external Odoo module names to skip silently.
    """
    if name in visited:
        return

    if name in visiting:
        cycle_start = ancestors.index(name)
        cycle_path = ancestors[cycle_start:] + [name]
        raise ValueError(f"Circular dependency detected: {' -> '.join(cycle_path)}")

    if external_modules and name not in modules and name in external_modules:
        visited.add(name)
        return

    if name not in modules:
        referrer = ancestors[-1] if ancestors else "<root>"
        if strict:
            raise ValueError(
                f"Unknown dependency '{name}' referenced by {referrer}"
            )
        else:
            import logging

            logging.getLogger(__name__).warning(
                "Unknown dependency '%s' referenced by %s — skipping",
                name,
                referrer,
            )
            visited.add(name)
            return

    visiting.add(name)

    mod = modules[name]
    if mod.get("depends"):
        for dep in mod["depends"]:
            _visit(
                dep, modules, visited, visiting, result, [*ancestors, name],
                strict=strict,
                external_modules=external_modules,
            )

    visiting.discard(name)
    visited.add(name)
    result.append(name)


# ── Public API ───────────────────────────────────────────────────────────────


def topo_sort(
    modules: dict[str, dict],
    *,
    strict: bool = True,
    external_modules: frozenset[str] | None = None,
) -> list[str]:
    """DFS-based topological sort with cycle detection.

    Args:
        modules: Mapping of {name: {"depends": [dep1, dep2]}}.
        strict: If True (default), raise ValueError when a dependency references
                a name not present in *modules*. If False, log a warning and
                skip the phantom dependency.
        external_modules: Known external Odoo module names to skip silently.
                          Defaults to names derived from known_odoo_models.json.

    Returns:
        Module names in dependency order (deps before dependents).

    Raises:
        ValueError: If a circular dependency is detected, or if strict=True
                    and an unknown dependency is encountered.
    """
    external_modules = external_modules or _load_external_module_names()
    visited: set[str] = set()
    visiting: set[str] = set()
    result: list[str] = []

    for name in modules:
        _visit(
            name, modules, visited, visiting, result, [],
            strict=strict,
            external_modules=external_modules,
        )

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
