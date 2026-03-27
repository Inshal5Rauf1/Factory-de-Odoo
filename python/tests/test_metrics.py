"""Tests for JSONL metrics logging."""
from __future__ import annotations

import json
from pathlib import Path

from amil_utils.metrics import ModuleMetrics, append_metrics


class TestModuleMetrics:
    def test_create_with_defaults(self):
        m = ModuleMetrics(module_name="test", odoo_version="19.0",
                          started_at="2026-03-26T00:00:00Z")
        assert m.module_name == "test"
        assert m.duration_seconds == 0.0
        assert m.validation_passed is False
        assert m.error_categories == []

    def test_append_creates_jsonl(self, tmp_path: Path):
        m = ModuleMetrics(module_name="test", odoo_version="19.0",
                          started_at="2026-03-26T00:00:00Z")
        append_metrics(m, tmp_path)
        lines = (tmp_path / ".planning" / "metrics.jsonl").read_text().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["module_name"] == "test"
        assert data["odoo_version"] == "19.0"

    def test_append_appends_not_overwrites(self, tmp_path: Path):
        for i in range(3):
            m = ModuleMetrics(module_name=f"mod_{i}", odoo_version="19.0",
                              started_at="2026-03-26T00:00:00Z")
            append_metrics(m, tmp_path)
        lines = (tmp_path / ".planning" / "metrics.jsonl").read_text().splitlines()
        assert len(lines) == 3
        names = [json.loads(line)["module_name"] for line in lines]
        assert names == ["mod_0", "mod_1", "mod_2"]

    def test_append_creates_parent_directories(self, tmp_path: Path):
        nested = tmp_path / "deep" / "nested"
        m = ModuleMetrics(module_name="test", odoo_version="19.0",
                          started_at="2026-03-26T00:00:00Z")
        append_metrics(m, nested)
        assert (nested / ".planning" / "metrics.jsonl").exists()

    def test_metrics_with_all_fields(self, tmp_path: Path):
        m = ModuleMetrics(
            module_name="hr_payroll",
            odoo_version="19.0",
            started_at="2026-03-26T10:00:00Z",
            duration_seconds=45.2,
            pylint_fix_iterations=3,
            docker_fix_iterations=1,
            pylint_violations_initial=12,
            pylint_violations_remaining=2,
            docker_errors_initial=1,
            docker_errors_remaining=0,
            semantic_errors=0,
            semantic_warnings=3,
            files_generated=15,
            validation_passed=True,
            error_categories=["W8113", "W8161"],
        )
        append_metrics(m, tmp_path)
        data = json.loads(
            (tmp_path / ".planning" / "metrics.jsonl").read_text().strip()
        )
        assert data["duration_seconds"] == 45.2
        assert data["pylint_fix_iterations"] == 3
        assert data["validation_passed"] is True
        assert data["error_categories"] == ["W8113", "W8161"]
