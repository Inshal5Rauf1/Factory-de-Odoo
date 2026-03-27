"""Tests for orchestrator uat_checkpoint module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from amil_utils.orchestrator.uat_checkpoint import (
    generate_checklist,
    get_uat_summary,
    is_checkpoint_due,
    record_result,
)


class TestIsCheckpointDue:
    def test_due_at_interval(self) -> None:
        assert is_checkpoint_due(list(range(10)), 0) is True

    def test_not_due_before_interval(self) -> None:
        assert is_checkpoint_due(list(range(5)), 0) is False

    def test_custom_interval(self) -> None:
        assert is_checkpoint_due(list(range(5)), 0, interval=5) is True

    def test_respects_last_checkpoint(self) -> None:
        assert is_checkpoint_due(list(range(15)), 10) is False
        assert is_checkpoint_due(list(range(20)), 10) is True


class TestGenerateChecklist:
    def test_basic_module(self) -> None:
        modules = [{
            "name": "hr_payroll",
            "models": [{"name": "hr.payroll.slip", "fields": []}],
        }]
        result = generate_checklist(modules, {})
        assert len(result["per_module"]) == 1
        assert result["per_module"][0]["module"] == "hr_payroll"
        assert len(result["per_module"][0]["flows"]) > 0

    def test_workflow_model_generates_state_flow(self) -> None:
        modules = [{
            "name": "hr_leave",
            "models": [{"name": "hr.leave", "fields": [], "description": "Leave Request"}],
            "workflow": [{"model": "hr.leave", "states": ["draft", "confirm", "done"]}],
        }]
        result = generate_checklist(modules, {})
        flows = result["per_module"][0]["flows"]
        assert any("draft" in f and "done" in f for f in flows)

    def test_computed_fields_generate_flow(self) -> None:
        modules = [{
            "name": "mod_a",
            "models": [{"name": "test.model", "fields": [
                {"name": "total", "compute": "_compute_total"},
            ]}],
        }]
        result = generate_checklist(modules, {})
        flows = result["per_module"][0]["flows"]
        assert any("total" in f for f in flows)

    def test_cross_module_flow(self) -> None:
        modules = [
            {
                "name": "mod_a",
                "models": [{"name": "model.a", "fields": [
                    {"name": "b_id", "comodel_name": "model.b"},
                ]}],
            },
            {
                "name": "mod_b",
                "models": [{"name": "model.b", "fields": []}],
            },
        ]
        result = generate_checklist(modules, {})
        assert len(result["cross_module"]) > 0

    def test_empty_modules(self) -> None:
        result = generate_checklist([], {})
        assert result["per_module"] == []
        assert result["cross_module"] == []


class TestRecordResult:
    def test_creates_result_file(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning" / "modules" / "hr_payroll"
        planning.mkdir(parents=True)
        data = record_result(tmp_path, "hr_payroll", "pass")
        result_file = planning / "uat-result.json"
        assert result_file.exists()
        stored = json.loads(result_file.read_text())
        assert stored["result"] == "pass"

    def test_creates_dir_if_needed(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        record_result(tmp_path, "hr_payroll", "pass")
        assert (tmp_path / ".planning" / "modules" / "hr_payroll" / "uat-result.json").exists()

    def test_fail_creates_feedback_file(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        record_result(tmp_path, "hr_payroll", "fail", "Button not working")
        feedback_file = tmp_path / ".planning" / "modules" / "hr_payroll" / "uat-feedback.md"
        assert feedback_file.exists()
        assert "Button not working" in feedback_file.read_text()

    def test_invalid_module_name_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid module name"):
            record_result(tmp_path, "Bad-Name!", "pass")

    def test_pass_no_feedback_file(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        record_result(tmp_path, "hr_payroll", "pass", "all good")
        feedback_file = tmp_path / ".planning" / "modules" / "hr_payroll" / "uat-feedback.md"
        assert not feedback_file.exists()


class TestGetUATSummary:
    def test_counts_results(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        record_result(tmp_path, "mod_a", "pass")
        record_result(tmp_path, "mod_b", "fail", "broken")
        result = get_uat_summary(tmp_path, ["mod_a", "mod_b", "mod_c"])
        assert result["summary"]["pass"] == 1
        assert result["summary"]["fail"] == 1
        assert result["summary"]["untested"] == 1

    def test_all_untested(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        result = get_uat_summary(tmp_path, ["mod_a", "mod_b"])
        assert result["summary"]["untested"] == 2
        assert len(result["details"]) == 2
