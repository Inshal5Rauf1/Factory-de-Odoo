"""Tests for orchestrator decomposition module."""
from __future__ import annotations

import json
from pathlib import Path

from amil_utils.orchestrator.decomposition import (
    format_decomposition_table,
    generate_roadmap_markdown,
    merge_decomposition,
)


def _make_research(tmp_path: Path) -> Path:
    """Create research directory with 4 agent output files."""
    research = tmp_path / "research"
    research.mkdir()

    boundaries = {
        "modules": [
            {
                "name": "hr_core",
                "description": "Core HR",
                "models": ["hr.employee", "hr.department"],
                "base_depends": ["base", "mail"],
                "estimated_complexity": "medium",
            },
            {
                "name": "hr_leave",
                "description": "Leave management",
                "models": ["hr.leave", "hr.leave.type"],
                "base_depends": ["base"],
                "estimated_complexity": "low",
            },
            {
                "name": "hr_payroll",
                "description": "Payroll",
                "models": ["hr.payslip"],
                "base_depends": ["account"],
                "estimated_complexity": "high",
            },
        ],
    }
    (research / "module-boundaries.json").write_text(json.dumps(boundaries))

    oca = {
        "findings": [
            {"odoo_module": "hr_leave", "recommendation": "fork_extend", "oca_module": "hr_holidays"},
        ],
    }
    (research / "oca-analysis.json").write_text(json.dumps(oca))

    dep_map = {
        "dependencies": [
            {"module": "hr_core", "depends_on": []},
            {"module": "hr_leave", "depends_on": ["hr_core"]},
            {"module": "hr_payroll", "depends_on": ["hr_core", "hr_leave"]},
        ],
    }
    (research / "dependency-map.json").write_text(json.dumps(dep_map))

    chains = {
        "chains": [
            {
                "name": "leave_to_payroll",
                "description": "Leave deductions",
                "steps": ["hr_leave.compute_days", "hr_payroll.compute_deduction"],
                "cross_module": True,
            },
        ],
    }
    (research / "computation-chains.json").write_text(json.dumps(chains))

    return research


class TestMergeDecomposition:
    def test_merges_all_sources(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        result = merge_decomposition(str(research), str(tmp_path))
        assert len(result["modules"]) == 3
        assert "generation_order" in result
        assert "tiers" in result

    def test_assigns_tiers(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        result = merge_decomposition(str(research), str(tmp_path))
        mod_map = {m["name"]: m for m in result["modules"]}
        assert mod_map["hr_core"]["tier"] == "foundation"
        assert mod_map["hr_leave"]["tier"] == "core"

    def test_applies_oca_recommendation(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        result = merge_decomposition(str(research), str(tmp_path))
        mod_map = {m["name"]: m for m in result["modules"]}
        assert mod_map["hr_leave"]["build_recommendation"] == "fork_extend"
        assert mod_map["hr_leave"]["oca_module"] == "hr_holidays"

    def test_attaches_computation_chains(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        result = merge_decomposition(str(research), str(tmp_path))
        mod_map = {m["name"]: m for m in result["modules"]}
        assert len(mod_map["hr_leave"]["computation_chains"]) >= 1
        assert len(mod_map["hr_payroll"]["computation_chains"]) >= 1

    def test_writes_decomposition_json(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        merge_decomposition(str(research), str(tmp_path))
        assert (research / "decomposition.json").exists()

    def test_generation_order(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        result = merge_decomposition(str(research), str(tmp_path))
        order = result["generation_order"]
        assert order.index("hr_core") < order.index("hr_leave")
        assert order.index("hr_leave") < order.index("hr_payroll")


class TestFormatDecompositionTable:
    def test_formats_table(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        decomp = merge_decomposition(str(research), str(tmp_path))
        text = format_decomposition_table(decomp)
        assert "MODULE DECOMPOSITION" in text
        assert "hr_core" in text
        assert "TIER" in text

    def test_includes_chains(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        decomp = merge_decomposition(str(research), str(tmp_path))
        text = format_decomposition_table(decomp)
        assert "COMPUTATION CHAINS" in text
        assert "leave_to_payroll" in text


class TestGenerateRoadmapMarkdown:
    def test_generates_phases(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        decomp = merge_decomposition(str(research), str(tmp_path))
        md = generate_roadmap_markdown(decomp)
        assert "### Phase 1:" in md
        assert "hr_core" in md
        assert "Status: not_started" in md

    def test_follows_generation_order(self, tmp_path: Path) -> None:
        research = _make_research(tmp_path)
        decomp = merge_decomposition(str(research), str(tmp_path))
        md = generate_roadmap_markdown(decomp)
        core_pos = md.index("hr_core")
        leave_pos = md.index("hr_leave")
        payroll_pos = md.index("hr_payroll")
        assert core_pos < leave_pos < payroll_pos
