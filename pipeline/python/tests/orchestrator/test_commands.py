"""Tests for orchestrator commands module."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pytest

from amil_utils.orchestrator.commands import (
    commit,
    current_timestamp,
    generate_slug,
    history_digest,
    list_todos,
    progress_render,
    resolve_model,
    scaffold,
    summary_extract,
    todo_complete,
    verify_path_exists,
)


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal .planning directory for command tests."""
    planning = tmp_path / ".planning"
    planning.mkdir()
    phases = planning / "phases"
    phases.mkdir()

    # config.json
    (planning / "config.json").write_text(
        '{"model_profile": "balanced", "commit_docs": true}'
    )

    # Phase 1 with plan + summary
    phase1 = phases / "01-setup"
    phase1.mkdir()
    (phase1 / "01-01-PLAN.md").write_text(
        "---\nphase: 1\nplan: 01\n---\n# Plan\n## Task 1\nSetup\n"
    )
    (phase1 / "01-01-SUMMARY.md").write_text(
        "---\none-liner: Set up project structure\nphase: 1\nplan: 01\n"
        "key-decisions:\n  - Use Python: Better ecosystem\n"
        "patterns-established:\n  - Repository pattern\n"
        "tech-stack:\n  added:\n    - Python 3.12\n---\n"
        "# Summary\n## Task 1\nDone\n"
    )

    # Phase 2 with plan only (no summary)
    phase2 = phases / "02-core"
    phase2.mkdir()
    (phase2 / "02-01-PLAN.md").write_text(
        "---\nphase: 2\nplan: 01\n---\n# Plan\n## Task 1\n## Task 2\n"
    )

    # ROADMAP.md
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## v1.0: First Release\n\n"
        "### Phase 1: Setup\n\n**Goal:** Project setup\n"
        "**Plans:** 1 plans\n\n"
        "### Phase 2: Core\n\n**Goal:** Core module\n"
        "**Plans:** 1 plans\n"
    )

    # STATE.md
    (planning / "STATE.md").write_text(
        "# Session State\n\n"
        "**Milestone:** v1.0\n"
        "**Status:** Executing\n"
    )

    return planning


class TestGenerateSlug:
    def test_basic_slug(self) -> None:
        result = generate_slug("Hello World")
        assert result["slug"] == "hello-world"

    def test_special_chars(self) -> None:
        result = generate_slug("My Project!! (v2.0)")
        assert result["slug"] == "my-project-v2-0"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="text required"):
            generate_slug("")


class TestCurrentTimestamp:
    def test_date_format(self) -> None:
        result = current_timestamp("date")
        assert re.match(r"\d{4}-\d{2}-\d{2}$", result["timestamp"])

    def test_filename_format(self) -> None:
        result = current_timestamp("filename")
        assert ":" not in result["timestamp"]
        assert "T" in result["timestamp"]

    def test_full_format(self) -> None:
        result = current_timestamp("full")
        assert "T" in result["timestamp"]

    def test_default_is_full(self) -> None:
        result = current_timestamp()
        assert "T" in result["timestamp"]


class TestListTodos:
    def test_empty(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        result = list_todos(tmp_path)
        assert result["count"] == 0

    def test_finds_todos(self, tmp_path: Path) -> None:
        pending = tmp_path / ".planning" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "01-fix-bug.md").write_text(
            "title: Fix bug\ncreated: 2026-03-13\narea: general\n"
        )
        result = list_todos(tmp_path)
        assert result["count"] == 1

    def test_area_filter(self, tmp_path: Path) -> None:
        pending = tmp_path / ".planning" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "01-fix.md").write_text(
            "title: Fix\ncreated: 2026-03-13\narea: bugs\n"
        )
        (pending / "02-feat.md").write_text(
            "title: Feature\ncreated: 2026-03-13\narea: features\n"
        )
        result = list_todos(tmp_path, area="bugs")
        assert result["count"] == 1


class TestVerifyPathExists:
    def test_existing_file(self, tmp_path: Path) -> None:
        (tmp_path / "test.txt").write_text("hello")
        result = verify_path_exists(tmp_path, "test.txt")
        assert result["exists"] is True
        assert result["type"] == "file"

    def test_existing_directory(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        result = verify_path_exists(tmp_path, "subdir")
        assert result["exists"] is True
        assert result["type"] == "directory"

    def test_missing(self, tmp_path: Path) -> None:
        result = verify_path_exists(tmp_path, "nope.txt")
        assert result["exists"] is False

    def test_empty_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="path required"):
            verify_path_exists(tmp_path, "")


class TestHistoryDigest:
    def test_empty_project(self, tmp_path: Path) -> None:
        (tmp_path / ".planning" / "phases").mkdir(parents=True)
        result = history_digest(tmp_path)
        assert result["phases"] == {}
        assert result["tech_stack"] == []

    def test_collects_from_summaries(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = history_digest(tmp_path)
        assert "1" in result["phases"] or "01" in result["phases"]
        assert len(result["tech_stack"]) >= 1

    def test_collects_decisions(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = history_digest(tmp_path)
        assert len(result["decisions"]) >= 1


class TestResolveModel:
    def test_known_agent(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = resolve_model(tmp_path, "amil-executor")
        assert "model" in result
        assert "profile" in result

    def test_unknown_agent(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = resolve_model(tmp_path, "unknown-agent")
        assert result.get("unknown_agent") is True

    def test_missing_agent_type_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="agent-type required"):
            resolve_model(tmp_path, "")


class TestCommit:
    def test_skips_when_commit_docs_false(self, tmp_path: Path) -> None:
        planning = _make_project(tmp_path)
        (planning / "config.json").write_text('{"commit_docs": false}')
        result = commit(tmp_path, "test commit")
        assert result["committed"] is False
        assert result["reason"] == "skipped_commit_docs_false"

    def test_no_message_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="commit message required"):
            commit(tmp_path, "")


class TestSummaryExtract:
    def test_extracts_fields(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = summary_extract(
            tmp_path, ".planning/phases/01-setup/01-01-SUMMARY.md"
        )
        assert result["one_liner"] == "Set up project structure"
        assert "key_files" in result

    def test_filter_fields(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = summary_extract(
            tmp_path,
            ".planning/phases/01-setup/01-01-SUMMARY.md",
            fields=["one_liner"],
        )
        assert "one_liner" in result
        assert "patterns" not in result

    def test_missing_file(self, tmp_path: Path) -> None:
        result = summary_extract(tmp_path, "nope.md")
        assert "error" in result

    def test_empty_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="summary-path required"):
            summary_extract(tmp_path, "")


class TestProgressRender:
    def test_json_format(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = progress_render(tmp_path)
        assert "phases" in result
        assert "percent" in result
        assert result["total_plans"] == 2

    def test_table_format(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = progress_render(tmp_path, format="table")
        assert "rendered" in result
        assert "Phase" in result["rendered"]

    def test_bar_format(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = progress_render(tmp_path, format="bar")
        assert "bar" in result
        assert "percent" in result

    def test_empty_project(self, tmp_path: Path) -> None:
        (tmp_path / ".planning" / "phases").mkdir(parents=True)
        (tmp_path / ".planning" / "ROADMAP.md").write_text("# Roadmap\n")
        (tmp_path / ".planning" / "STATE.md").write_text(
            "**Milestone:** v1.0\n"
        )
        result = progress_render(tmp_path)
        assert result["percent"] == 0


class TestTodoComplete:
    def test_completes_todo(self, tmp_path: Path) -> None:
        pending = tmp_path / ".planning" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "01-fix.md").write_text("title: Fix\n")
        result = todo_complete(tmp_path, "01-fix.md")
        assert result["completed"] is True
        assert not (pending / "01-fix.md").exists()
        completed_dir = tmp_path / ".planning" / "todos" / "completed"
        assert (completed_dir / "01-fix.md").exists()

    def test_missing_todo_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            todo_complete(tmp_path, "nope.md")

    def test_empty_filename_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="filename required"):
            todo_complete(tmp_path, "")


class TestScaffold:
    def test_scaffold_context(self, tmp_path: Path) -> None:
        planning = _make_project(tmp_path)
        result = scaffold(tmp_path, "context", phase="1")
        assert result["created"] is True
        assert "CONTEXT" in result["path"]

    def test_scaffold_uat(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = scaffold(tmp_path, "uat", phase="1")
        assert result["created"] is True

    def test_scaffold_verification(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = scaffold(tmp_path, "verification", phase="1")
        assert result["created"] is True

    def test_scaffold_phase_dir(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = scaffold(tmp_path, "phase-dir", phase="4", name="testing")
        assert result["created"] is True
        assert "04-testing" in result["directory"]

    def test_scaffold_already_exists(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        scaffold(tmp_path, "context", phase="1")
        result = scaffold(tmp_path, "context", phase="1")
        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_unknown_type_raises(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        with pytest.raises(ValueError, match="Unknown scaffold type"):
            scaffold(tmp_path, "bogus", phase="1")
