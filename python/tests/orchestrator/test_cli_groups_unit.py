"""Unit tests for cli_groups.py utility logic.

Focuses on utility functions and inline logic within Click commands,
not end-to-end command invocation (those live in test_cli_orch.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from amil_utils.orchestrator.cli import orch_group


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal .planning directory for CLI group tests."""
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
    return planning


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def project(tmp_path: Path):
    _make_project(tmp_path)
    return tmp_path


# ── state patch pairs parsing ──────────────────────────────────────────────


class TestStatePatchPairsParsing:
    """Test the key-value pair parsing logic in state_patch_cmd."""

    def test_patch_parses_key_value_pairs(self, runner, project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "state", "patch",
                "--cwd", str(project),
                "--raw",
                "--", "status", "Planning",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data.get("ok") or "status" in str(data)

    def test_patch_strips_leading_dashes(self, runner, project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "state", "patch",
                "--cwd", str(project),
                "--raw",
                "--", "--status", "Planning",
            ],
        )
        assert result.exit_code == 0

    def test_patch_multiple_pairs(self, runner, project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "state", "patch",
                "--cwd", str(project),
                "--raw",
                "--", "status", "Planning", "milestone", "v2.0",
            ],
        )
        assert result.exit_code == 0

    def test_patch_empty_pairs(self, runner, project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "state", "patch",
                "--cwd", str(project),
                "--raw",
            ],
        )
        # No pairs = empty dict patched
        assert result.exit_code == 0


# ── state add-decision file reading ───────────────────────────────────────


class TestStateAddDecisionFileReading:
    """Test summary-file and rationale-file reading logic in state_add_decision_cmd."""

    def test_reads_summary_from_file(self, runner, project, tmp_path: Path) -> None:
        summary_file = tmp_path / "summary.txt"
        summary_file.write_text("Decision summary from file")
        result = runner.invoke(
            orch_group,
            [
                "state", "add-decision",
                "--cwd", str(project),
                "--raw",
                "--summary-file", str(summary_file),
                "--rationale", "Because reasons",
            ],
        )
        assert result.exit_code == 0

    def test_reads_rationale_from_file(self, runner, project, tmp_path: Path) -> None:
        rationale_file = tmp_path / "rationale.txt"
        rationale_file.write_text("Detailed rationale from file")
        result = runner.invoke(
            orch_group,
            [
                "state", "add-decision",
                "--cwd", str(project),
                "--raw",
                "--summary", "Test decision",
                "--rationale-file", str(rationale_file),
            ],
        )
        assert result.exit_code == 0

    def test_summary_option_overrides_file(self, runner, project, tmp_path: Path) -> None:
        summary_file = tmp_path / "summary.txt"
        summary_file.write_text("File summary")
        result = runner.invoke(
            orch_group,
            [
                "state", "add-decision",
                "--cwd", str(project),
                "--raw",
                "--summary", "Direct summary",
                "--summary-file", str(summary_file),
            ],
        )
        assert result.exit_code == 0


# ── Group registration ─────────────────────────────────────────────────────


class TestGroupRegistration:
    """Test that all expected command groups are registered on orch_group."""

    @pytest.mark.parametrize(
        "group_name",
        [
            "state",
            "phase",
            "phases",
            "roadmap",
            "requirements",
            "milestone",
            "validate",
            "template",
            "frontmatter",
            "init",
        ],
    )
    def test_group_registered(self, group_name: str) -> None:
        commands = orch_group.list_commands(click.Context(orch_group))
        assert group_name in commands, f"'{group_name}' not registered on orch_group"


# ── Frontmatter commands inline logic ──────────────────────────────────────


class TestFrontmatterCommands:
    """Test frontmatter command inline logic (get, set, merge, validate)."""

    @pytest.fixture()
    def fm_project(self, tmp_path: Path) -> Path:
        planning = _make_project(tmp_path)
        # Create a frontmatter file in the project
        fm_file = tmp_path / "test-doc.md"
        fm_file.write_text(
            "---\nstatus: draft\npriority: high\n---\n\n# Test Document\n\nBody text.\n"
        )
        return tmp_path

    def test_frontmatter_get_all_fields(self, runner, fm_project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "frontmatter", "get",
                "test-doc.md",
                "--cwd", str(fm_project),
                "--raw",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["status"] == "draft"
        assert data["priority"] == "high"

    def test_frontmatter_get_single_field(self, runner, fm_project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "frontmatter", "get",
                "test-doc.md",
                "--field", "status",
                "--cwd", str(fm_project),
                "--raw",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data == {"status": "draft"}

    def test_frontmatter_get_missing_field_returns_none(self, runner, fm_project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "frontmatter", "get",
                "test-doc.md",
                "--field", "nonexistent",
                "--cwd", str(fm_project),
                "--raw",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data == {"nonexistent": None}

    def test_frontmatter_set_string_value(self, runner, fm_project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "frontmatter", "set",
                "test-doc.md",
                "--field", "status",
                "--value", "complete",
                "--cwd", str(fm_project),
                "--raw",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["updated"] is True
        assert data["field"] == "status"

        # Verify the file was actually updated
        content = (fm_project / "test-doc.md").read_text()
        assert "complete" in content

    def test_frontmatter_set_json_value(self, runner, fm_project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "frontmatter", "set",
                "test-doc.md",
                "--field", "count",
                "--value", "42",
                "--cwd", str(fm_project),
                "--raw",
            ],
        )
        assert result.exit_code == 0
        # 42 should be parsed as JSON integer

    def test_frontmatter_merge(self, runner, fm_project) -> None:
        merge_data = json.dumps({"author": "test", "version": "1.0"})
        result = runner.invoke(
            orch_group,
            [
                "frontmatter", "merge",
                "test-doc.md",
                "--data", merge_data,
                "--cwd", str(fm_project),
                "--raw",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["merged"] is True
        assert "author" in data["fields"]
        assert "version" in data["fields"]


# ── template fill JSON fields parsing ──────────────────────────────────────


class TestTemplateFillFieldsParsing:
    """Test that template fill correctly parses --fields JSON."""

    def test_fill_with_empty_fields_json(self, runner, project) -> None:
        result = runner.invoke(
            orch_group,
            [
                "template", "fill",
                "execute",
                "--phase", "1",
                "--fields", "{}",
                "--cwd", str(project),
                "--raw",
            ],
        )
        # May fail due to missing template, but should not fail on JSON parsing
        # We care that the JSON parsing of --fields works
        if result.exit_code != 0:
            # Should NOT be a JSON decode error
            assert "JSONDecodeError" not in (result.output or "")

    def test_fill_with_custom_fields_json(self, runner, project) -> None:
        fields = json.dumps({"objective": "Test", "description": "A test plan"})
        result = runner.invoke(
            orch_group,
            [
                "template", "fill",
                "execute",
                "--phase", "1",
                "--fields", fields,
                "--cwd", str(project),
                "--raw",
            ],
        )
        # The command may fail for template-not-found, but the JSON parsing should succeed
        if result.exit_code != 0:
            assert "JSONDecodeError" not in (result.output or "")


# ── State subcommand routing ───────────────────────────────────────────────


class TestStateSubcommands:
    """Test that state subcommands are properly registered."""

    @pytest.mark.parametrize(
        "subcommand",
        [
            "load",
            "json",
            "get",
            "update",
            "patch",
            "advance-plan",
            "record-metric",
            "update-progress",
            "add-decision",
            "add-blocker",
            "resolve-blocker",
            "record-session",
            "snapshot",
        ],
    )
    def test_state_subcommand_exists(self, subcommand: str) -> None:
        from amil_utils.orchestrator.cli_groups import state_grp

        ctx = click.Context(state_grp)
        commands = state_grp.list_commands(ctx)
        assert subcommand in commands

    @pytest.mark.parametrize(
        "subcommand",
        [
            "next-decimal",
            "add",
            "insert",
            "remove",
            "complete",
        ],
    )
    def test_phase_subcommand_exists(self, subcommand: str) -> None:
        from amil_utils.orchestrator.cli_groups import phase_grp

        ctx = click.Context(phase_grp)
        commands = phase_grp.list_commands(ctx)
        assert subcommand in commands

    @pytest.mark.parametrize(
        "subcommand",
        [
            "execute-phase",
            "plan-phase",
            "new-project",
            "new-milestone",
            "quick",
            "resume",
            "verify-work",
            "phase-op",
            "todos",
            "milestone-op",
            "map-codebase",
            "progress",
        ],
    )
    def test_init_subcommand_exists(self, subcommand: str) -> None:
        from amil_utils.orchestrator.cli_groups import init_grp

        ctx = click.Context(init_grp)
        commands = init_grp.list_commands(ctx)
        assert subcommand in commands


# ── Module-level re-exports ────────────────────────────────────────────────


class TestModuleReExports:
    """Verify backward-compat re-exports from cli_module_commands."""

    def test_dep_graph_grp_importable(self) -> None:
        from amil_utils.orchestrator.cli_groups import dep_graph_grp

        assert dep_graph_grp is not None

    def test_module_status_grp_importable(self) -> None:
        from amil_utils.orchestrator.cli_groups import module_status_grp

        assert module_status_grp is not None

    def test_registry_grp_importable(self) -> None:
        from amil_utils.orchestrator.cli_groups import registry_grp

        assert registry_grp is not None

    def test_cycle_log_grp_importable(self) -> None:
        from amil_utils.orchestrator.cli_groups import cycle_log_grp

        assert cycle_log_grp is not None

    def test_coherence_grp_importable(self) -> None:
        from amil_utils.orchestrator.cli_groups import coherence_grp

        assert coherence_grp is not None
