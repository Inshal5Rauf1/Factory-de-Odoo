"""Integration tests for the orchestrator Click CLI.

Tests the thin CLI wiring layer — each command's library function
is already tested in its own module test file. These tests verify
the Click integration works end-to-end (args → JSON output).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from amil_utils.orchestrator.cli import orch_group


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal .planning directory for CLI tests."""
    planning = tmp_path / ".planning"
    planning.mkdir()
    phases = planning / "phases"
    phases.mkdir()

    (planning / "config.json").write_text(
        '{"model_profile": "balanced", "commit_docs": true}'
    )

    phase1 = phases / "01-setup"
    phase1.mkdir()
    (phase1 / "01-01-PLAN.md").write_text(
        "---\nphase: 1\nplan: 01\nwave: 1\nautonomous: true\n"
        "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n"
        "# Plan\n<objective>\nSetup\n</objective>\n<task>\n## Task 1\nDo it\n</task>\n"
    )

    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## v1.0: First\n\n"
        "### Phase 1: Setup\n\n**Goal:** Setup\n"
        "**Requirements**: REQ-01\n**Plans:** 1 plans\n"
    )
    (planning / "STATE.md").write_text(
        "# Session State\n\n"
        "**Milestone:** v1.0\n"
        "**Status:** Executing\n"
        "**Last Activity:** 2026-03-13\n"
    )
    (planning / "REQUIREMENTS.md").write_text(
        "# Requirements\n\n- [ ] **REQ-01** Setup\n\n"
        "## Traceability\n\n"
        "| Requirement | Phase | Status |\n"
        "|---|---|---|\n"
        "| REQ-01 | Phase 1 | Pending |\n"
    )
    return planning


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def project(tmp_path: Path):
    _make_project(tmp_path)
    return tmp_path


class TestStateCommands:
    def test_state_load(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["state", "load", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "config" in data

    def test_state_json(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["state", "json", "--cwd", str(project)])
        assert result.exit_code == 0

    def test_state_get(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["state", "get", "--cwd", str(project)])
        assert result.exit_code == 0

    def test_state_snapshot(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["state", "snapshot", "--cwd", str(project)])
        assert result.exit_code == 0


class TestPhaseCommands:
    def test_phase_find(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["find-phase", "1", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["found"] is True

    def test_phase_plan_index(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["phase-plan-index", "1", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "plans" in data

    def test_phase_next_decimal(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["phase", "next-decimal", "01", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "next" in data

    def test_phases_list(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["phases", "list", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "count" in data


class TestUtilityCommands:
    def test_generate_slug(self, runner) -> None:
        result = runner.invoke(orch_group, ["generate-slug", "Hello World"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "hello-world"

    def test_current_timestamp(self, runner) -> None:
        result = runner.invoke(orch_group, ["current-timestamp", "date"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "timestamp" in data

    def test_verify_path_exists(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["verify-path-exists", ".planning", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["exists"] is True

    def test_list_todos(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["list-todos", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0

    def test_resolve_model(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["resolve-model", "amil-executor", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "model" in data

    def test_progress(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["progress", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "percent" in data

    def test_history_digest(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["history-digest", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "phases" in data


class TestConfigCommands:
    def test_config_ensure_section(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["config-ensure-section", "--cwd", str(project)])
        assert result.exit_code == 0


class TestInitCommands:
    def test_init_execute_phase(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["init", "execute-phase", "1", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["phase_found"] is True

    def test_init_plan_phase(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["init", "plan-phase", "1", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "researcher_model" in data

    def test_init_new_project(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["init", "new-project", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "researcher_model" in data

    def test_init_resume(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["init", "resume", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "state_exists" in data

    def test_init_progress(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["init", "progress", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "phases" in data


class TestRoadmapCommands:
    def test_roadmap_get_phase(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["roadmap", "get-phase", "1", "--cwd", str(project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["found"] is True

    def test_roadmap_analyze(self, runner, project) -> None:
        result = runner.invoke(orch_group, ["roadmap", "analyze", "--cwd", str(project)])
        assert result.exit_code == 0


class TestRawOutput:
    def test_raw_flag(self, runner) -> None:
        result = runner.invoke(orch_group, ["generate-slug", "Test", "--raw"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "test"
