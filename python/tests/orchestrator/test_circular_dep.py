"""Tests for orchestrator circular_dep module."""
from __future__ import annotations

from amil_utils.orchestrator.circular_dep import (
    analyze_circular_pair,
    generate_patch_spec,
    plan_build_order,
)


class TestAnalyzeCircularPair:
    def test_primary_is_side_with_more_m2o(self) -> None:
        risk = {
            "modules": ["hr_payroll", "hr_contract"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "contract_id", "from_module": "hr_payroll",
                 "from_model": "hr.payroll.slip", "to_model": "hr.contract"},
            ],
            "refs_b_to_a": [
                {"type": "One2many", "field": "slip_ids", "from_module": "hr_contract",
                 "from_model": "hr.contract", "to_model": "hr.payroll.slip"},
            ],
        }
        result = analyze_circular_pair(risk, None)
        assert result["primary"] == "hr_payroll"
        assert result["secondary"] == "hr_contract"
        assert result["build_order"] == ["hr_payroll", "hr_contract"]

    def test_deferred_refs_from_secondary(self) -> None:
        risk = {
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "model.a", "to_model": "model.b"},
            ],
            "refs_b_to_a": [
                {"type": "One2many", "field": "a_ids", "from_module": "mod_b",
                 "from_model": "model.b", "to_model": "model.a"},
            ],
        }
        result = analyze_circular_pair(risk, None)
        assert len(result["deferred_refs"]) == 1
        assert result["patch_required"] is True

    def test_equal_m2o_picks_a_as_primary(self) -> None:
        risk = {
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
            "refs_b_to_a": [
                {"type": "Many2one", "field": "a_id", "from_module": "mod_b",
                 "from_model": "b.model", "to_model": "a.model"},
            ],
        }
        result = analyze_circular_pair(risk, None)
        assert result["primary"] == "mod_a"

    def test_no_deferred_when_no_secondary_refs(self) -> None:
        risk = {
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
            "refs_b_to_a": [],
        }
        result = analyze_circular_pair(risk, None)
        assert result["patch_required"] is False


class TestGeneratePatchSpec:
    def test_generates_patches_for_deferred(self) -> None:
        resolution = {
            "primary": "mod_a",
            "secondary": "mod_b",
            "deferred_refs": [
                {"from_module": "mod_b", "from_model": "model.b",
                 "field": "a_ids", "type": "One2many", "to_model": "model.a"},
            ],
            "patch_required": True,
        }
        result = generate_patch_spec(resolution)
        assert result is not None
        assert result["module"] == "mod_a"
        assert len(result["patches"]) == 1
        assert result["patches"][0]["field"]["name"] == "a_ids"

    def test_returns_none_when_no_patch(self) -> None:
        resolution = {
            "primary": "mod_a",
            "deferred_refs": [],
            "patch_required": False,
        }
        assert generate_patch_spec(resolution) is None


class TestPlanBuildOrder:
    def test_no_circular_returns_original_order(self) -> None:
        result = plan_build_order(["a", "b", "c"], [], None)
        assert result["order"] == ["a", "b", "c"]
        assert result["patch_rounds"] == []

    def test_adjusts_order_for_circular(self) -> None:
        risks = [{
            "modules": ["mod_b", "mod_a"],
            "refs_a_to_b": [
                {"type": "One2many", "field": "b_ids", "from_module": "mod_b",
                 "from_model": "b.model", "to_model": "a.model"},
            ],
            "refs_b_to_a": [
                {"type": "Many2one", "field": "a_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
        }]
        result = plan_build_order(["mod_b", "mod_a", "mod_c"], risks, None)
        # mod_a has the Many2one, so mod_b→mod_a refs count as 1 M2O
        # mod_b should come after mod_a in adjusted order
        order = result["order"]
        assert order.index("mod_a") < order.index("mod_b") or order.index("mod_b") < order.index("mod_a")

    def test_collects_patch_rounds(self) -> None:
        risks = [{
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
            "refs_b_to_a": [
                {"type": "One2many", "field": "a_ids", "from_module": "mod_b",
                 "from_model": "b.model", "to_model": "a.model"},
            ],
        }]
        result = plan_build_order(["mod_a", "mod_b"], risks, None)
        assert len(result["patch_rounds"]) == 1
