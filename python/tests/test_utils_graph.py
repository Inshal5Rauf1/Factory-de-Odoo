"""Tests for shared graph utilities."""
from __future__ import annotations

import pytest
from amil_utils.utils.graph import check_no_cycles, topo_sort_safe


class TestCheckNoCycles:
    def test_passes_clean_dag(self):
        graph = {"a": {"b"}, "b": {"c"}, "c": set()}
        check_no_cycles(graph, "test")

    def test_raises_on_cycle(self):
        graph = {"a": {"b"}, "b": {"a"}}
        with pytest.raises(ValueError, match="Circular dependency"):
            check_no_cycles(graph, "test")

    def test_empty_graph(self):
        check_no_cycles({}, "test")


class TestTopoSortSafe:
    def test_returns_order(self):
        graph = {"a": {"b"}, "b": {"c"}, "c": set()}
        order = topo_sort_safe(graph, "test")
        assert order.index("c") < order.index("b") < order.index("a")

    def test_raises_on_cycle(self):
        graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        with pytest.raises(ValueError, match="Circular dependency"):
            topo_sort_safe(graph, "test")

    def test_single_node(self):
        order = topo_sort_safe({"a": set()}, "test")
        assert order == ["a"]
