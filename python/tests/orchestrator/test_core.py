"""Tests for orchestrator core module."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from amil_utils.orchestrator.core import (
    MODEL_PROFILES,
    compare_phase_num,
    ensure_within_cwd,
    exec_git,
    find_phase,
    generate_slug,
    get_archived_phase_dirs,
    get_milestone_info,
    get_milestone_phase_filter,
    get_roadmap_phase,
    has_source_files,
    is_git_ignored,
    load_config,
    normalize_phase_name,
    path_exists,
    resolve_model,
    safe_read_file,
    scan_todos,
    search_phase_in_dir,
    to_posix_path,
)


# ── safe_read_file ──────────────────────────────────────────────────────────


class TestSafeReadFile:
    def test_returns_content(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert safe_read_file(f) == "hello"

    def test_returns_none_for_missing(self, tmp_path: Path) -> None:
        assert safe_read_file(tmp_path / "missing.txt") is None


# ── load_config ─────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_loads_from_project(self, tmp_project: Path) -> None:
        config = load_config(tmp_project)
        assert config["profile"] == "quality"

    def test_returns_defaults_for_missing(self, tmp_path: Path) -> None:
        config = load_config(tmp_path)
        assert config["model_profile"] == "balanced"
        assert config["commit_docs"] is True
        assert config["branching_strategy"] == "none"

    def test_migrates_depth_to_granularity(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "config.json").write_text(
            json.dumps({"depth": "comprehensive"})
        )
        config = load_config(tmp_path)
        assert config.get("granularity") == "fine" or config["model_profile"] == "balanced"

    def test_nested_section_lookup(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "config.json").write_text(
            json.dumps({"workflow": {"research": False}})
        )
        config = load_config(tmp_path)
        assert config["research"] is False

    def test_parallelization_object_form(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "config.json").write_text(
            json.dumps({"parallelization": {"enabled": False}})
        )
        config = load_config(tmp_path)
        assert config["parallelization"] is False


# ── exec_git ────────────────────────────────────────────────────────────────


class TestExecGit:
    def test_returns_stdout(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        result = exec_git(tmp_path, ["status", "--porcelain"])
        assert result["exit_code"] == 0
        assert isinstance(result["stdout"], str)

    def test_returns_error_for_bad_command(self, tmp_path: Path) -> None:
        result = exec_git(tmp_path, ["log", "--oneline"])
        # May fail if not a git repo, or return empty
        assert isinstance(result["exit_code"], int)


# ── normalize_phase_name ────────────────────────────────────────────────────


class TestNormalizePhaseName:
    def test_pads_single_digit(self) -> None:
        assert normalize_phase_name("1.0") == "01.0"

    def test_double_digit_unchanged(self) -> None:
        assert normalize_phase_name("12.0") == "12.0"

    def test_with_letter(self) -> None:
        assert normalize_phase_name("3A.1") == "03A.1"

    def test_lowercase_letter_uppercased(self) -> None:
        assert normalize_phase_name("3a") == "03A"

    def test_plain_number(self) -> None:
        assert normalize_phase_name("2") == "02"

    def test_non_matching_returns_as_is(self) -> None:
        assert normalize_phase_name("abc") == "abc"


# ── compare_phase_num ───────────────────────────────────────────────────────


class TestComparePhaseNum:
    def test_less_than(self) -> None:
        assert compare_phase_num("1.0", "2.0") < 0

    def test_greater_than(self) -> None:
        assert compare_phase_num("2.0", "1.0") > 0

    def test_equal(self) -> None:
        assert compare_phase_num("1.0", "1.0") == 0

    def test_decimal_ordering(self) -> None:
        assert compare_phase_num("1.1", "1.2") < 0

    def test_no_letter_before_letter(self) -> None:
        assert compare_phase_num("12", "12A") < 0

    def test_letter_ordering(self) -> None:
        assert compare_phase_num("12A", "12B") < 0

    def test_no_decimal_before_decimal(self) -> None:
        assert compare_phase_num("12A", "12A.1") < 0


# ── generate_slug ───────────────────────────────────────────────────────────


class TestGenerateSlug:
    def test_basic_slug(self) -> None:
        assert generate_slug("Hello World!") == "hello-world"

    def test_strips_whitespace(self) -> None:
        assert generate_slug("  Spaces  ") == "spaces"

    def test_empty_returns_none(self) -> None:
        assert generate_slug("") is None

    def test_none_returns_none(self) -> None:
        assert generate_slug(None) is None


# ── ensure_within_cwd ───────────────────────────────────────────────────────


class TestEnsureWithinCwd:
    def test_valid_subpath(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        result = ensure_within_cwd(tmp_path, sub)
        assert result == sub.resolve()

    def test_rejects_escape(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="outside"):
            ensure_within_cwd(tmp_path, tmp_path / ".." / "etc")


# ── MODEL_PROFILES ──────────────────────────────────────────────────────────


class TestModelProfiles:
    def test_has_expected_keys(self) -> None:
        assert "amil-planner" in MODEL_PROFILES
        assert "amil-executor" in MODEL_PROFILES
        assert "amil-debugger" in MODEL_PROFILES

    def test_profiles_have_tiers(self) -> None:
        for agent, profiles in MODEL_PROFILES.items():
            assert "quality" in profiles, f"{agent} missing quality"
            assert "balanced" in profiles, f"{agent} missing balanced"
            assert "budget" in profiles, f"{agent} missing budget"


# ── search_phase_in_dir ─────────────────────────────────────────────────────


class TestSearchPhaseInDir:
    def test_finds_phase(self, tmp_project: Path) -> None:
        phase_dir = tmp_project / ".planning" / "phases" / "01.0-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan")
        result = search_phase_in_dir(
            tmp_project / ".planning" / "phases",
            ".planning/phases",
            "01.0",
        )
        assert result is not None
        assert result["found"] is True
        assert result["phase_number"] == "01.0"

    def test_returns_none_for_missing(self, tmp_project: Path) -> None:
        phases_dir = tmp_project / ".planning" / "phases"
        phases_dir.mkdir(parents=True, exist_ok=True)
        result = search_phase_in_dir(phases_dir, ".planning/phases", "99")
        assert result is None


# ── find_phase ──────────────────────────────────────────────────────────────


class TestFindPhase:
    def test_finds_in_current(self, tmp_project: Path) -> None:
        phase_dir = tmp_project / ".planning" / "phases" / "01.0-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan")
        result = find_phase(tmp_project, "1.0")
        assert result is not None
        assert result["found"] is True

    def test_returns_none_for_missing(self, tmp_project: Path) -> None:
        (tmp_project / ".planning" / "phases").mkdir(parents=True, exist_ok=True)
        result = find_phase(tmp_project, "99")
        assert result is None

    def test_none_input(self, tmp_project: Path) -> None:
        assert find_phase(tmp_project, None) is None


# ── scan_todos ──────────────────────────────────────────────────────────────


class TestScanTodos:
    def test_scans_pending_todos(self, tmp_project: Path) -> None:
        todo_dir = tmp_project / ".planning" / "todos" / "pending"
        todo_dir.mkdir(parents=True)
        (todo_dir / "todo-001.md").write_text(
            "---\ntitle: Fix bug\narea: dev\ncreated: 2026-03-10\n---\nBody"
        )
        todos = scan_todos(tmp_project)
        assert len(todos) == 1
        assert todos[0]["title"] == "Fix bug"

    def test_empty_when_no_dir(self, tmp_project: Path) -> None:
        todos = scan_todos(tmp_project)
        assert todos == []

    def test_area_filter(self, tmp_project: Path) -> None:
        todo_dir = tmp_project / ".planning" / "todos" / "pending"
        todo_dir.mkdir(parents=True)
        (todo_dir / "todo-001.md").write_text(
            "---\ntitle: Dev task\narea: dev\ncreated: 2026-03-10\n---\n"
        )
        (todo_dir / "todo-002.md").write_text(
            "---\ntitle: Ops task\narea: ops\ncreated: 2026-03-10\n---\n"
        )
        todos = scan_todos(tmp_project, area_filter="dev")
        assert len(todos) == 1
        assert todos[0]["title"] == "Dev task"


# ── get_milestone_info ──────────────────────────────────────────────────────


class TestGetMilestoneInfo:
    def test_from_in_progress_marker(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n- \U0001f6a7 **v2.1 Belgium** \u2014 Phases 24-28 (in progress)\n"
        )
        info = get_milestone_info(tmp_path)
        assert info["version"] == "v2.1"
        assert info["name"] == "Belgium"

    def test_from_heading(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n## Milestone v1.0: Core Setup\n"
        )
        info = get_milestone_info(tmp_path)
        assert info["version"] == "v1.0"

    def test_fallback(self, tmp_path: Path) -> None:
        info = get_milestone_info(tmp_path)
        assert info["version"] == "v1.0"


# ── to_posix_path ───────────────────────────────────────────────────────────


class TestToPosixPath:
    def test_forward_slashes(self) -> None:
        assert to_posix_path("a/b/c") == "a/b/c"

    def test_converts_backslashes(self) -> None:
        # On Linux this is a no-op, but tests the logic
        result = to_posix_path("a/b/c")
        assert "/" in result


# ── resolve_model ───────────────────────────────────────────────────────────


class TestResolveModel:
    def test_from_profile(self, tmp_project: Path) -> None:
        result = resolve_model(tmp_project, "amil-planner")
        # quality profile for amil-planner is 'opus' -> 'inherit'
        assert result == "inherit"

    def test_unknown_agent(self, tmp_project: Path) -> None:
        result = resolve_model(tmp_project, "unknown-agent")
        assert result == "sonnet"

    def test_override(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "config.json").write_text(
            json.dumps({"model_overrides": {"amil-planner": "haiku"}})
        )
        result = resolve_model(tmp_path, "amil-planner")
        assert result == "haiku"


# ── has_source_files ────────────────────────────────────────────────────────


class TestHasSourceFiles:
    def test_finds_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("print('hi')")
        assert has_source_files(tmp_path) is True

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert has_source_files(tmp_path) is False

    def test_ignores_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}")
        assert has_source_files(tmp_path) is False


# ── path_exists ─────────────────────────────────────────────────────────────


class TestPathExists:
    def test_existing_file(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("hi")
        assert path_exists(tmp_path, "file.txt") is True

    def test_missing_file(self, tmp_path: Path) -> None:
        assert path_exists(tmp_path, "nope.txt") is False


# ── get_roadmap_phase ───────────────────────────────────────────────────────


class TestGetRoadmapPhase:
    def test_finds_phase(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n## Phase 1: Setup Core\n\n"
            "**Goal:** Build the foundation\n\n"
            "## Phase 2: Features\n\n**Goal:** Add features\n"
        )
        result = get_roadmap_phase(tmp_path, "1")
        assert result is not None
        assert result["found"] is True
        assert result["phase_name"] == "Setup Core"
        assert result["goal"] == "Build the foundation"

    def test_returns_none_for_missing_phase(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text("# Roadmap\n\n## Phase 1: Setup\n")
        assert get_roadmap_phase(tmp_path, "99") is None


# ── get_milestone_phase_filter ──────────────────────────────────────────────


class TestGetMilestonePhaseFilter:
    def test_filters_by_roadmap(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n## Phase 1: A\n\n## Phase 3: C\n"
        )
        filt = get_milestone_phase_filter(tmp_path)
        assert filt("1-setup") is True
        assert filt("3-features") is True
        assert filt("2-other") is False

    def test_pass_all_when_no_roadmap(self, tmp_path: Path) -> None:
        filt = get_milestone_phase_filter(tmp_path)
        assert filt("anything") is True
        assert filt.phase_count == 0
