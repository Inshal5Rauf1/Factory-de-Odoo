"""Tests for orchestrator state module."""
from __future__ import annotations

from pathlib import Path

import pytest

from amil_utils.orchestrator.state import (
    build_state_frontmatter,
    state_add_blocker,
    state_add_decision,
    state_advance_plan,
    state_extract_field,
    state_get,
    state_json,
    state_load,
    state_patch,
    state_record_metric,
    state_record_session,
    state_replace_field,
    state_resolve_blocker,
    state_snapshot,
    state_update,
    state_update_progress,
    sync_state_frontmatter,
    write_state_md,
)

SAMPLE_STATE = """\
# State

**Current Phase:** 2
**Current Phase Name:** Features
**Total Phases:** 5
**Current Plan:** 1
**Total Plans in Phase:** 3
**Status:** Executing plan 1
**Progress:** [████░░░░░░] 40%
**Last Activity:** 2026-03-10

## Decisions Made

| Phase | Decision | Rationale |
|-------|----------|-----------|
| 1 | Use PostgreSQL | Better JSON support |

### Accumulated Decisions
- [Phase 1]: Chose RBAC over simple ACL

## Blockers
- Waiting for API credentials

### Blockers/Concerns
None

## Session
**Last Date:** 2026-03-10T12:00:00Z
**Stopped At:** Task 3 of Plan 1
**Resume File:** None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 1 P01 | 25min | 4 tasks | 12 files |
"""


def _make_state(tmp_path: Path, content: str = SAMPLE_STATE) -> Path:
    planning = tmp_path / ".planning"
    planning.mkdir(exist_ok=True)
    state_path = planning / "STATE.md"
    state_path.write_text(content)
    return state_path


class TestStateExtractField:
    def test_bold_format(self) -> None:
        assert state_extract_field(SAMPLE_STATE, "Current Phase") == "2"

    def test_plain_format(self) -> None:
        plain = "Current Phase: 2\nStatus: working"
        assert state_extract_field(plain, "Status") == "working"

    def test_returns_none_for_missing(self) -> None:
        assert state_extract_field(SAMPLE_STATE, "Nonexistent") is None

    def test_case_insensitive(self) -> None:
        assert state_extract_field(SAMPLE_STATE, "current phase") == "2"


class TestStateReplaceField:
    def test_replaces_bold_field(self) -> None:
        result = state_replace_field(SAMPLE_STATE, "Status", "Paused")
        assert result is not None
        assert "**Status:** Paused" in result

    def test_replaces_plain_field(self) -> None:
        plain = "Status: working\nOther: thing"
        result = state_replace_field(plain, "Status", "done")
        assert result is not None
        assert "Status: done" in result

    def test_returns_none_for_missing(self) -> None:
        assert state_replace_field(SAMPLE_STATE, "Nonexistent", "val") is None


class TestStateLoad:
    def test_returns_config_and_state(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_load(tmp_path)
        assert "config" in result
        assert result["state_exists"] is True

    def test_handles_missing_state(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        result = state_load(tmp_path)
        assert result["state_exists"] is False


class TestStateGet:
    def test_returns_full_content(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_get(tmp_path)
        assert "content" in result
        assert "Current Phase" in result["content"]

    def test_returns_field_value(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_get(tmp_path, "Current Phase")
        assert result["Current Phase"] == "2"

    def test_returns_section(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_get(tmp_path, "Session")
        assert "Session" in result
        assert "Last Date" in result["Session"]

    def test_not_found(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_get(tmp_path, "Nonexistent")
        assert "error" in result


class TestStatePatch:
    def test_updates_multiple_fields(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_patch(tmp_path, {"Status": "Paused", "Current Plan": "2"})
        assert "Status" in result["updated"]
        assert "Current Plan" in result["updated"]

    def test_reports_failed_fields(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_patch(tmp_path, {"Nonexistent": "val"})
        assert "Nonexistent" in result["failed"]


class TestStateUpdate:
    def test_updates_field(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_update(tmp_path, "Status", "Paused")
        assert result["updated"] is True

    def test_returns_false_for_missing(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_update(tmp_path, "Nonexistent", "val")
        assert result["updated"] is False


class TestStateAdvancePlan:
    def test_advances_plan(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_advance_plan(tmp_path)
        assert result["advanced"] is True
        assert result["current_plan"] == 2

    def test_last_plan_triggers_verification(self, tmp_path: Path) -> None:
        content = SAMPLE_STATE.replace(
            "**Current Plan:** 1", "**Current Plan:** 3"
        )
        _make_state(tmp_path, content)
        result = state_advance_plan(tmp_path)
        assert result["advanced"] is False
        assert result["status"] == "ready_for_verification"


class TestStateRecordMetric:
    def test_records_metric(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_record_metric(
            tmp_path, phase="2", plan="01", duration="15min", tasks="3", files="8"
        )
        assert result["recorded"] is True

    def test_missing_fields(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_record_metric(tmp_path, phase="", plan="", duration="")
        assert "error" in result


class TestStateUpdateProgress:
    def test_updates_progress(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        # Create a phase with plans and summaries
        phases_dir = tmp_path / ".planning" / "phases" / "02-features"
        phases_dir.mkdir(parents=True)
        (phases_dir / "01-PLAN.md").write_text("# Plan")
        (phases_dir / "01-SUMMARY.md").write_text("# Summary")
        (phases_dir / "02-PLAN.md").write_text("# Plan")
        result = state_update_progress(tmp_path)
        assert result["updated"] is True
        assert result["total"] == 2

    def test_no_progress_field(self, tmp_path: Path) -> None:
        content = "# State\n\n**Status:** Working"
        _make_state(tmp_path, content)
        result = state_update_progress(tmp_path)
        assert result["updated"] is False


class TestStateAddDecision:
    def test_adds_decision(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_add_decision(
            tmp_path, phase="2", summary="Use Redis for caching"
        )
        assert result["added"] is True

    def test_missing_summary(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_add_decision(tmp_path, phase="2", summary="")
        assert "error" in result


class TestStateAddBlocker:
    def test_adds_blocker(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_add_blocker(tmp_path, "Docker registry down")
        assert result["added"] is True

    def test_no_section(self, tmp_path: Path) -> None:
        content = "# State\n\n**Status:** Working"
        _make_state(tmp_path, content)
        result = state_add_blocker(tmp_path, "issue")
        assert result["added"] is False


class TestStateResolveBlocker:
    def test_resolves_blocker(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_resolve_blocker(tmp_path, "API credentials")
        assert result["resolved"] is True

    def test_no_section(self, tmp_path: Path) -> None:
        content = "# State\n\n**Status:** Working"
        _make_state(tmp_path, content)
        result = state_resolve_blocker(tmp_path, "issue")
        assert result["resolved"] is False


class TestStateRecordSession:
    def test_records_session(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_record_session(
            tmp_path, stopped_at="Task 5 of Plan 2"
        )
        assert result["recorded"] is True

    def test_no_session_fields(self, tmp_path: Path) -> None:
        content = "# State\n\n**Status:** Working"
        _make_state(tmp_path, content)
        result = state_record_session(tmp_path)
        assert result["recorded"] is False


class TestStateSnapshot:
    def test_extracts_fields(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        result = state_snapshot(tmp_path)
        assert result["current_phase"] == "2"
        assert result["status"] == "Executing plan 1"
        assert result["total_plans_in_phase"] == 3

    def test_missing_state(self, tmp_path: Path) -> None:
        result = state_snapshot(tmp_path)
        assert "error" in result


class TestBuildStateFrontmatter:
    def test_builds_from_body(self) -> None:
        fm = build_state_frontmatter(SAMPLE_STATE)
        assert fm["current_phase"] == "2"
        assert fm["status"] == "executing"
        assert fm["amil_state_version"] == "1.0"

    def test_normalizes_paused_status(self) -> None:
        content = "**Status:** Paused\n**Paused At:** Task 3"
        fm = build_state_frontmatter(content)
        assert fm["status"] == "paused"

    def test_normalizes_complete_status(self) -> None:
        content = "**Status:** Phase complete"
        fm = build_state_frontmatter(content)
        assert fm["status"] == "completed"


class TestSyncStateFrontmatter:
    def test_adds_frontmatter(self) -> None:
        result = sync_state_frontmatter(SAMPLE_STATE)
        assert result.startswith("---\n")
        assert "amil_state_version" in result
        assert "# State" in result


class TestWriteStateMd:
    def test_writes_with_frontmatter(self, tmp_path: Path) -> None:
        state_path = tmp_path / "STATE.md"
        write_state_md(state_path, SAMPLE_STATE, tmp_path)
        content = state_path.read_text()
        assert content.startswith("---\n")
        assert "# State" in content


class TestStateJson:
    def test_returns_frontmatter(self, tmp_path: Path) -> None:
        _make_state(tmp_path)
        # Write with frontmatter first
        state_path = tmp_path / ".planning" / "STATE.md"
        write_state_md(state_path, SAMPLE_STATE, tmp_path)
        result = state_json(tmp_path)
        assert "amil_state_version" in result

    def test_missing_state(self, tmp_path: Path) -> None:
        result = state_json(tmp_path)
        assert "error" in result
