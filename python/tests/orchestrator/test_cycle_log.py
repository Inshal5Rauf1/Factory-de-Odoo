"""Tests for orchestrator cycle_log module."""
from __future__ import annotations

from pathlib import Path

from amil_utils.orchestrator.cycle_log import (
    LOG_FILENAME,
    append_blocked_module,
    append_coherence_event,
    append_entry,
    finalize_log,
    get_log_path,
    init_log,
    update_compact_summary,
)


class TestGetLogPath:
    def test_returns_planning_path(self, tmp_path: Path) -> None:
        result = get_log_path(tmp_path)
        assert result == tmp_path / ".planning" / LOG_FILENAME

    def test_filename_constant(self) -> None:
        assert LOG_FILENAME == "ERP_CYCLE_LOG.md"


class TestInitLog:
    def test_creates_log_file(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        path = init_log(tmp_path, "Test Project")
        assert path.exists()

    def test_header_contains_project_name(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "My ERP")
        content = get_log_path(tmp_path).read_text()
        assert "My ERP" in content

    def test_header_has_compact_summary(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        content = get_log_path(tmp_path).read_text()
        assert "<!-- COMPACT-SUMMARY-START -->" in content
        assert "<!-- COMPACT-SUMMARY-END -->" in content

    def test_initial_summary_values(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        content = get_log_path(tmp_path).read_text()
        assert "**Last Iteration:** 0" in content
        assert "**Shipped:** 0/0" in content


class TestUpdateCompactSummary:
    def test_replaces_summary_block(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        update_compact_summary(tmp_path, {
            "iteration": 5,
            "shipped": 10,
            "total": 20,
            "in_progress": 3,
            "blocked": 2,
            "next_action": "generate module_x",
            "wave": 3,
            "coherence_warnings": 1,
        })
        content = get_log_path(tmp_path).read_text()
        assert "**Last Iteration:** 5" in content
        assert "**Shipped:** 10/20" in content
        assert "**Blocked:** 2" in content
        assert "**Coherence Warnings:** 1" in content


class TestAppendEntry:
    def test_appends_iteration_block(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        append_entry(tmp_path, {
            "iteration": 1,
            "module": "hr_payroll",
            "action": "generate",
            "result": "success",
            "wave": 1,
            "stats": {"shipped": 1, "total": 10, "in_progress": 2, "remaining": 7},
        })
        content = get_log_path(tmp_path).read_text()
        assert "### Iteration 1" in content
        assert "**Module:** hr_payroll" in content
        assert "**Action:** generate" in content
        assert "**Result:** success" in content

    def test_updates_compact_summary(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        append_entry(tmp_path, {
            "iteration": 3,
            "module": "mod_a",
            "action": "test",
            "result": "pass",
            "stats": {"shipped": 3, "total": 10, "blocked": 1},
        })
        content = get_log_path(tmp_path).read_text()
        assert "**Last Iteration:** 3" in content
        assert "**Shipped:** 3/10" in content


class TestAppendBlockedModule:
    def test_appends_blocked_entry(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        append_blocked_module(tmp_path, "hr_leave", "missing dependency")
        content = get_log_path(tmp_path).read_text()
        assert "BLOCKED" in content
        assert "hr_leave" in content
        assert "missing dependency" in content


class TestAppendCoherenceEvent:
    def test_appends_coherence_event(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        append_coherence_event(tmp_path, {
            "type": "model_conflict",
            "source_module": "hr_payroll",
            "target_module": "hr_contract",
            "details": "Model name collision",
            "resolution": "Renamed model",
        })
        content = get_log_path(tmp_path).read_text()
        assert "COHERENCE [model_conflict]" in content
        assert "hr_payroll" in content
        assert "hr_contract" in content

    def test_without_resolution(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        append_coherence_event(tmp_path, {
            "type": "field_mismatch",
            "source_module": "mod_a",
            "target_module": "mod_b",
            "details": "Field type mismatch",
        })
        content = get_log_path(tmp_path).read_text()
        assert "COHERENCE" in content
        assert "Resolution" not in content


class TestFinalizeLog:
    def test_appends_completion_footer(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        init_log(tmp_path, "Test")
        finalize_log(tmp_path, {
            "total": 90,
            "shipped": 85,
            "blocked": 5,
            "iterations": 120,
            "errors": 10,
            "coherence_warnings": 3,
            "context_resets": 2,
            "shipped_list": ["mod_a", "mod_b"],
            "blocked_list": [{"name": "mod_c", "reason": "missing dep"}],
        })
        content = get_log_path(tmp_path).read_text()
        assert "Cycle Complete" in content
        assert "**Total Modules:** 90" in content
        assert "**Shipped:** 85" in content
        assert "mod_a" in content
        assert "mod_c" in content
