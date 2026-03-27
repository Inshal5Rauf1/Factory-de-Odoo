"""Tests for orchestrator spec_completeness module."""
from __future__ import annotations

from amil_utils.orchestrator.spec_completeness import (
    get_discussion_batches,
    get_discussion_summary,
    score_all_modules,
    score_module,
)


class TestScoreModule:
    def test_full_score_module(self) -> None:
        mod = {
            "models": [
                {"name": "hr.payroll.slip", "fields": [
                    {"name": "employee_id", "type": "Many2one"},
                    {"name": "date_from", "type": "Date"},
                    {"name": "amount", "type": "Float"},
                ]},
            ],
            "security": {"roles": ["manager", "user"]},
            "workflow": [{"model": "hr.payroll.slip", "states": ["draft", "done"]}],
            "depends": ["hr", "account"],
            "description": "Payroll management for employees with salary computation",
            "computation_chains": [{"name": "compute_amount"}],
            "view_hints": [{"type": "form"}],
        }
        result = score_module(mod, [])
        assert result["score"] >= 70
        assert result["ready"] is True
        assert result["discussion_depth"] == "none"

    def test_empty_module_low_score(self) -> None:
        result = score_module({}, [])
        assert result["score"] == 0
        assert result["ready"] is False
        assert result["discussion_depth"] == "full"
        assert len(result["gaps"]) > 0

    def test_models_defined_adds_20(self) -> None:
        mod = {"models": [{"name": "test.model", "fields": []}]}
        result = score_module(mod, [])
        assert result["score"] >= 20

    def test_detailed_models_adds_15(self) -> None:
        mod = {"models": [{"name": "test.model", "fields": [
            {"name": "a"}, {"name": "b"}, {"name": "c"},
        ]}]}
        result = score_module(mod, [])
        assert result["score"] >= 35  # 20 (models) + 15 (detail)

    def test_security_roles_adds_15(self) -> None:
        result_with = score_module({"security": {"roles": ["admin"]}}, [])
        result_without = score_module({}, [])
        assert result_with["score"] - result_without["score"] == 15

    def test_brief_discussion_depth(self) -> None:
        mod = {
            "models": [{"name": "m", "fields": [
                {"name": "a"}, {"name": "b"}, {"name": "c"},
            ]}],
            "security": {"roles": ["user"]},
        }
        result = score_module(mod, [])
        assert result["score"] >= 40
        assert result["discussion_depth"] in ("brief", "none")

    def test_cross_module_bonus(self) -> None:
        mod = {"models": [{"name": "test.model", "fields": [
            {"name": "partner_id", "type": "Many2one", "comodel_name": "res.partner"},
        ]}]}
        result = score_module(mod, ["other_module"])
        # res.partner is standard, so no unresolved refs -> +5 bonus
        assert result["cross_module_issues"] == []

    def test_unresolved_comodel_flagged(self) -> None:
        mod = {"models": [{"name": "test.model", "fields": [
            {"name": "custom_id", "type": "Many2one", "comodel_name": "custom.model"},
        ]}]}
        result = score_module(mod, ["some_module"])
        assert len(result["cross_module_issues"]) > 0


class TestScoreAllModules:
    def test_scores_all(self) -> None:
        decomp = {
            "modules": [
                {"name": "mod_a", "models": []},
                {"name": "mod_b", "models": [{"name": "m", "fields": []}]},
            ],
        }
        results = score_all_modules(decomp)
        assert "mod_a" in results
        assert "mod_b" in results

    def test_empty_decomposition(self) -> None:
        results = score_all_modules({"modules": []})
        assert results == {}


class TestGetDiscussionBatches:
    def test_groups_by_tier_and_depth(self) -> None:
        scores = {
            "mod_a": {"score": 20, "discussion_depth": "full", "gaps": [], "cross_module_issues": []},
            "mod_b": {"score": 50, "discussion_depth": "brief", "gaps": [], "cross_module_issues": []},
            "mod_c": {"score": 80, "discussion_depth": "none", "gaps": [], "cross_module_issues": []},
        }
        module_data = {
            "modules": [
                {"name": "mod_a", "tier": "core"},
                {"name": "mod_b", "tier": "core"},
                {"name": "mod_c", "tier": "core"},
            ],
        }
        batches = get_discussion_batches(scores, module_data)
        # mod_c is ready, so only mod_a and mod_b should be in batches
        total_mods = sum(len(b["modules"]) for b in batches)
        assert total_mods == 2

    def test_empty_when_all_ready(self) -> None:
        scores = {
            "mod_a": {"score": 80, "discussion_depth": "none", "gaps": [], "cross_module_issues": []},
        }
        module_data = {"modules": [{"name": "mod_a", "tier": "core"}]}
        batches = get_discussion_batches(scores, module_data)
        assert len(batches) == 0


class TestGetDiscussionSummary:
    def test_summary_counts(self) -> None:
        scores = {
            "a": {"score": 80, "ready": True, "discussion_depth": "none"},
            "b": {"score": 50, "ready": False, "discussion_depth": "brief"},
            "c": {"score": 20, "ready": False, "discussion_depth": "full"},
        }
        result = get_discussion_summary(scores)
        assert result["total"] == 3
        assert result["ready"] == 1
        assert result["brief"] == 1
        assert result["full"] == 1
        assert result["avg_score"] == 50

    def test_empty_scores(self) -> None:
        result = get_discussion_summary({})
        assert result["total"] == 0
        assert result["avg_score"] == 0
