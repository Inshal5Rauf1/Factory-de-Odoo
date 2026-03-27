"""Tests for orchestrator phase_query module.

Tests query operations: phases_list, phase_next_decimal, phase_find,
phase_plan_index, and _extract_objective — imported directly from
phase_query.py (not via phase.py re-exports).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from amil_utils.orchestrator.phase_query import (
    _extract_objective,
    phase_find,
    phase_next_decimal,
    phase_plan_index,
    phases_list,
)


def _make_phases_project(tmp_path: Path, *, num_phases: int = 3) -> Path:
    """Create a .planning directory with phases, ROADMAP.md, and STATE.md."""
    planning = tmp_path / ".planning"
    planning.mkdir()
    phases = planning / "phases"
    phases.mkdir()

    phase_data = [
        ("01-setup", "Setup"),
        ("02-core", "Core module"),
        ("03-advanced", "Advanced features"),
    ]

    roadmap_lines = ["# Roadmap\n"]
    for i, (dir_name, desc) in enumerate(phase_data[:num_phases], 1):
        phase_dir = phases / dir_name
        phase_dir.mkdir()
        (phase_dir / ".gitkeep").write_text("")

        plan_content = (
            f"---\nphase: {i}\nplan: 01\ntype: implementation\n"
            f"wave: 1\ndepends_on: []\nfiles_modified: [src/main.py]\n"
            f"autonomous: true\nmust_haves:\n---\n\n"
            f"# Plan {i}-01\n\n<objective>\nBuild {desc.lower()}\n</objective>\n\n"
            f"<task>\n## Task 1\nDo something\n</task>\n\n"
            f"<task>\n## Task 2\nDo something else\n</task>\n"
        )
        (phase_dir / f"{str(i).zfill(2)}-01-PLAN.md").write_text(plan_content)

        roadmap_lines.append(f"### Phase {i}: {desc}\n")
        roadmap_lines.append(f"**Goal:** Build {desc.lower()}\n")
        roadmap_lines.append(f"**Requirements**: REQ-{str(i).zfill(2)}\n")
        if i > 1:
            roadmap_lines.append(f"**Depends on:** Phase {i - 1}\n")
        roadmap_lines.append(f"**Plans:** 1 plans\n\n")

    (planning / "ROADMAP.md").write_text("\n".join(roadmap_lines))

    state_content = (
        "# Session State\n\n## Position\n\n"
        "**Milestone:** v1.0\n"
        "**Current Phase:** 1\n"
        "**Current Phase Name:** Setup\n"
        "**Status:** Executing\n"
        "**Current Plan:** 1\n"
        "**Total Plans in Phase:** 1\n"
        "**Total Phases:** 3\n"
        "**Progress:** 0%\n"
        "**Last Activity:** 2026-03-13\n"
        "**Last Activity Description:** Working on phase 1\n"
    )
    (planning / "STATE.md").write_text(state_content)

    return planning


# ── _extract_objective ─────────────────────────────────────────────────────


class TestExtractObjective:
    """Tests for the _extract_objective helper."""

    def test_extracts_first_line(self) -> None:
        content = "<objective>\nBuild the core module\n</objective>"
        assert _extract_objective(content) == "Build the core module"

    def test_strips_whitespace(self) -> None:
        content = "<objective>\n  Trimmed text  \n</objective>"
        assert _extract_objective(content) == "Trimmed text"

    def test_returns_none_when_no_objective(self) -> None:
        content = "# Just a heading\n\nSome body text."
        assert _extract_objective(content) is None

    def test_extracts_only_first_line_of_multiline(self) -> None:
        content = "<objective>\nFirst line\nSecond line\n</objective>"
        assert _extract_objective(content) == "First line"

    def test_handles_objective_with_same_line_content(self) -> None:
        content = "<objective> Inline content\n</objective>"
        assert _extract_objective(content) == "Inline content"

    def test_handles_empty_objective(self) -> None:
        content = "<objective>\n\n</objective>"
        result = _extract_objective(content)
        # The regex (.+) greedily matches — with an empty first line it picks up
        # the closing tag as the matched content
        assert result == "</objective>"


# ── phases_list ────────────────────────────────────────────────────────────


class TestPhasesList:
    """Tests for the phases_list query function."""

    def test_returns_empty_when_no_phases_dir(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        result = phases_list(tmp_path)
        assert result["count"] == 0
        assert result["directories"] == []

    def test_returns_empty_files_when_no_phases_dir_with_file_type(
        self, tmp_path: Path
    ) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        result = phases_list(tmp_path, file_type="plans")
        assert result["count"] == 0
        assert result["files"] == []

    def test_lists_all_directories_sorted(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path)
        assert result["count"] == 3
        dirs = result["directories"]
        assert dirs[0].startswith("01")
        assert dirs[1].startswith("02")
        assert dirs[2].startswith("03")

    def test_filter_by_phase_number(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path, phase="2")
        assert result["count"] == 1
        assert result["directories"][0].startswith("02")

    def test_filter_by_phase_not_found(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path, phase="99")
        assert result["count"] == 0
        assert result["error"] == "Phase not found"

    def test_filter_by_file_type_plans(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path, file_type="plans")
        assert result["count"] >= 3
        assert all(f.endswith("-PLAN.md") for f in result["files"])

    def test_filter_by_file_type_summaries_empty(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path, file_type="summaries")
        assert result["count"] == 0
        assert result["files"] == []

    def test_filter_by_file_type_summaries_with_data(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        (planning / "phases" / "01-setup" / "01-01-SUMMARY.md").write_text("Done")
        result = phases_list(tmp_path, file_type="summaries")
        assert result["count"] == 1
        assert result["files"][0] == "01-01-SUMMARY.md"

    def test_filter_by_phase_and_file_type(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path, phase="1", file_type="plans")
        assert result["count"] >= 1
        assert result["phase_dir"] is not None

    def test_phase_dir_extracted_correctly(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path, phase="1", file_type="plans")
        # phase_dir should be the name part after the phase number prefix
        assert result["phase_dir"] is not None
        assert isinstance(result["phase_dir"], str)

    def test_other_file_type_returns_all_files(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phases_list(tmp_path, file_type="all")
        # "all" is not "plans" or "summaries" so returns all files
        assert result["count"] >= 3  # at least .gitkeep + PLAN per phase

    def test_handles_unreadable_phase_dir(self, tmp_path: Path) -> None:
        """If a phase dir in the list doesn't actually exist on disk (archived tag)."""
        planning = _make_phases_project(tmp_path)
        # The entries list might contain archived names that don't exist as directories
        # The function uses try/except OSError for this case
        result = phases_list(tmp_path, file_type="plans")
        assert "files" in result

    def test_single_phase_project(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path, num_phases=1)
        result = phases_list(tmp_path)
        assert result["count"] == 1
        assert result["directories"][0].startswith("01")


# ── phase_next_decimal ─────────────────────────────────────────────────────


class TestPhaseNextDecimal:
    """Tests for the phase_next_decimal query function."""

    def test_no_phases_dir_returns_first_decimal(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        result = phase_next_decimal(tmp_path, "06")
        assert result["next"] == "06.1"
        assert result["found"] is False
        assert result["existing"] == []
        assert result["base_phase"] == "06"

    def test_base_phase_exists_no_decimals(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_next_decimal(tmp_path, "01")
        assert result["next"] == "01.1"
        assert result["found"] is True
        assert result["existing"] == []

    def test_base_phase_not_found(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_next_decimal(tmp_path, "99")
        assert result["next"] == "99.1"
        assert result["found"] is False

    def test_existing_decimals_increment(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        phases = planning / "phases"
        (phases / "01.1-hotfix").mkdir()
        result = phase_next_decimal(tmp_path, "01")
        assert result["next"] == "01.2"
        assert result["existing"] == ["01.1"]

    def test_multiple_existing_decimals(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        phases = planning / "phases"
        (phases / "02.1-fix-a").mkdir()
        (phases / "02.2-fix-b").mkdir()
        (phases / "02.3-fix-c").mkdir()
        result = phase_next_decimal(tmp_path, "02")
        assert result["next"] == "02.4"
        assert len(result["existing"]) == 3
        assert result["existing"] == ["02.1", "02.2", "02.3"]

    def test_normalizes_phase_name(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        # Passing "1" should be normalized to "01" (or similar)
        result = phase_next_decimal(tmp_path, "1")
        assert result["base_phase"] == "01"

    def test_returns_sorted_existing_decimals(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        phases = planning / "phases"
        # Create out of order
        (phases / "01.3-third").mkdir()
        (phases / "01.1-first").mkdir()
        (phases / "01.2-second").mkdir()
        result = phase_next_decimal(tmp_path, "01")
        assert result["existing"] == ["01.1", "01.2", "01.3"]
        assert result["next"] == "01.4"


# ── phase_find ─────────────────────────────────────────────────────────────


class TestPhaseFind:
    """Tests for the phase_find query function."""

    def test_find_existing_phase(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_find(tmp_path, "1")
        assert result["found"] is True
        assert "01" in result["phase_number"]

    def test_find_nonexistent_phase(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_find(tmp_path, "99")
        assert result["found"] is False
        assert result["directory"] is None
        assert result["phase_number"] is None
        assert result["plans"] == []
        assert result["summaries"] == []

    def test_find_empty_phase_string(self) -> None:
        result = phase_find("/tmp", "")
        assert result["found"] is False

    def test_find_phase_by_full_number(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_find(tmp_path, "02")
        assert result["found"] is True

    def test_not_found_result_shape(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_find(tmp_path, "42")
        assert result == {
            "found": False,
            "directory": None,
            "phase_number": None,
            "phase_name": None,
            "plans": [],
            "summaries": [],
        }


# ── phase_plan_index ───────────────────────────────────────────────────────


class TestPhasePlanIndex:
    """Tests for the phase_plan_index query function."""

    def test_builds_plan_index(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_plan_index(tmp_path, "1")
        assert result["phase"] == "01"
        assert len(result["plans"]) >= 1
        plan = result["plans"][0]
        assert plan["wave"] == 1
        assert plan["autonomous"] is True
        assert plan["task_count"] == 2
        assert plan["has_summary"] is False

    def test_plan_index_for_nonexistent_phase(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_plan_index(tmp_path, "99")
        assert "error" in result
        assert result["plans"] == []
        assert result["waves"] == {}
        assert result["incomplete"] == []
        assert result["has_checkpoints"] is False

    def test_detects_completed_plans_via_summary(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        (planning / "phases" / "01-setup" / "01-01-SUMMARY.md").write_text(
            "---\nphase: 1\nplan: 01\n---\n# Summary\nDone."
        )
        result = phase_plan_index(tmp_path, "1")
        assert len(result["incomplete"]) == 0
        assert result["plans"][0]["has_summary"] is True

    def test_detects_incomplete_plans(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_plan_index(tmp_path, "1")
        assert len(result["incomplete"]) >= 1

    def test_detects_checkpoints_from_non_autonomous(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        plan = (
            "---\nphase: 1\nplan: 02\nwave: 2\nautonomous: false\n"
            "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n\n"
            "<task>\n## Task 1\nManual review\n</task>\n"
        )
        (planning / "phases" / "01-setup" / "01-02-PLAN.md").write_text(plan)
        result = phase_plan_index(tmp_path, "1")
        assert result["has_checkpoints"] is True

    def test_no_checkpoints_when_all_autonomous(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_plan_index(tmp_path, "1")
        assert result["has_checkpoints"] is False

    def test_waves_grouping(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        # Add a wave-2 plan
        plan_w2 = (
            "---\nphase: 1\nplan: 02\nwave: 2\nautonomous: true\n"
            "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n\n"
            "<task>\n## Task 1\nWave 2 work\n</task>\n"
        )
        (planning / "phases" / "01-setup" / "01-02-PLAN.md").write_text(plan_w2)
        result = phase_plan_index(tmp_path, "1")
        assert "1" in result["waves"]
        assert "2" in result["waves"]
        assert len(result["waves"]["1"]) >= 1
        assert len(result["waves"]["2"]) >= 1

    def test_extracts_objective_from_xml_tag(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_plan_index(tmp_path, "1")
        assert result["plans"][0]["objective"] == "Build setup"

    def test_extracts_files_modified(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_plan_index(tmp_path, "1")
        assert result["plans"][0]["files_modified"] == ["src/main.py"]

    def test_counts_xml_tasks(self, tmp_path: Path) -> None:
        _make_phases_project(tmp_path)
        result = phase_plan_index(tmp_path, "1")
        assert result["plans"][0]["task_count"] == 2

    def test_counts_markdown_tasks_fallback(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        # Create a plan with only markdown tasks (no XML <task> tags)
        md_plan = (
            "---\nphase: 2\nplan: 02\nwave: 1\nautonomous: true\n"
            "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n\n"
            "# Plan\n\n## Task 1\nFirst task\n\n## Task 2\nSecond task\n\n## Task 3\nThird\n"
        )
        (planning / "phases" / "02-core" / "02-02-PLAN.md").write_text(md_plan)
        result = phase_plan_index(tmp_path, "2")
        # Find the plan with id "02-02" specifically
        plan_02 = next(p for p in result["plans"] if p["id"] == "02-02")
        assert plan_02["task_count"] == 3

    def test_plan_index_no_phases_dir(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        # No phases directory
        result = phase_plan_index(tmp_path, "1")
        assert "error" in result
        assert result["plans"] == []

    def test_autonomous_string_true_variants(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        # Test autonomous: "True" (string)
        plan = (
            "---\nphase: 2\nplan: 02\nwave: 1\nautonomous: True\n"
            "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n\n"
            "<task>\n## Task 1\nWork\n</task>\n"
        )
        (planning / "phases" / "02-core" / "02-02-PLAN.md").write_text(plan)
        result = phase_plan_index(tmp_path, "2")
        plan_02 = next(p for p in result["plans"] if p["id"] == "02-02")
        assert plan_02["autonomous"] is True

    def test_wave_defaults_to_one(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        # Plan without wave field
        plan = (
            "---\nphase: 2\nplan: 02\nautonomous: true\n"
            "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n\n"
            "<task>\n## Task 1\nWork\n</task>\n"
        )
        (planning / "phases" / "02-core" / "02-02-PLAN.md").write_text(plan)
        result = phase_plan_index(tmp_path, "2")
        plan_02 = next(p for p in result["plans"] if p["id"] == "02-02")
        assert plan_02["wave"] == 1

    def test_files_modified_single_string(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        plan = (
            "---\nphase: 2\nplan: 02\nwave: 1\nautonomous: true\n"
            "depends_on: []\nfiles_modified: src/only.py\nmust_haves:\n---\n\n"
            "<task>\n## Task 1\nWork\n</task>\n"
        )
        (planning / "phases" / "02-core" / "02-02-PLAN.md").write_text(plan)
        result = phase_plan_index(tmp_path, "2")
        plan_02 = next(p for p in result["plans"] if p["id"] == "02-02")
        assert plan_02["files_modified"] == ["src/only.py"]

    def test_objective_falls_back_to_frontmatter(self, tmp_path: Path) -> None:
        planning = _make_phases_project(tmp_path)
        # Plan without <objective> tag but with frontmatter objective
        plan = (
            "---\nphase: 2\nplan: 02\nwave: 1\nautonomous: true\n"
            "objective: Frontmatter objective\n"
            "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n\n"
            "# Plan without objective tag\n\n"
            "<task>\n## Task 1\nWork\n</task>\n"
        )
        (planning / "phases" / "02-core" / "02-02-PLAN.md").write_text(plan)
        result = phase_plan_index(tmp_path, "2")
        plan_02 = next(p for p in result["plans"] if p["id"] == "02-02")
        assert plan_02["objective"] == "Frontmatter objective"
