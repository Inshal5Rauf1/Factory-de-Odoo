"""Shared graph utilities — cycle detection and topological sort."""
from __future__ import annotations

from graphlib import CycleError, TopologicalSorter


def check_no_cycles(graph: dict[str, set[str]], context: str) -> None:
    """Raise ValueError if the graph contains a cycle.

    Parameters
    ----------
    graph:
        Adjacency dict mapping node → set of dependencies.
    context:
        Human-readable label for error messages (e.g., "computed field").
    """
    try:
        ts = TopologicalSorter(graph)
        list(ts.static_order())
    except CycleError as exc:
        cycle_str = " -> ".join(str(n) for n in exc.args[1])
        raise ValueError(f"Circular dependency in {context}: {cycle_str}") from exc


def topo_sort_safe(graph: dict[str, set[str]], context: str) -> list[str]:
    """Return topological order or raise ValueError on cycle.

    Parameters
    ----------
    graph:
        Adjacency dict mapping node → set of dependencies.
    context:
        Human-readable label for error messages.

    Returns
    -------
    list[str]
        Nodes in topological order (dependencies before dependents).
    """
    try:
        ts = TopologicalSorter(graph)
        return list(ts.static_order())
    except CycleError as exc:
        cycle_str = " -> ".join(str(n) for n in exc.args[1])
        raise ValueError(f"Circular dependency in {context}: {cycle_str}") from exc
