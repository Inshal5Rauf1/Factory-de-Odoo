"""Tests for orchestrator init_commands module."""
from __future__ import annotations

from pathlib import Path

import pytest

from amil_utils.orchestrator.init_commands import (
    discover_phase_artifacts,
    init_execute_phase,
    init_map_codebase,
    init_milestone_op,
    init_new_milestone,
    init_new_project,
    init_phase_op,
    init_plan_phase,
    init_progress,
    init_quick,
    init_resume,
    init_todos,
    init_verify_work,
)


def _make_project(tmp_path: Path, *, with_git: bool = False) -> Path:
    """Create a .planning directory for init command tests."""
    planning = tmp_path / ".planning"
    planning.mkdir()
    phases = planning / "phases"
    phases.mkdir()

    # config.json
    (planning / "config.json").write_text(
        '{"model_profile": "balanced", "commit_docs": true,'
        ' "parallelization": true, "branching_strategy": "phase",'
        ' "phase_branch_template": "phase-{phase}-{slug}",'
        ' "milestone_branch_template": "milestone-{milestone}-{slug}",'
        ' "verifier": true, "research": true, "plan_checker": true,'
        ' "nyquist_validation": true, "brave_search": false,'
        ' "search_gitignored": false}'
    )

    # Phase 1 with plan + summary + context + research
    phase1 = phases / "01-setup"
    phase1.mkdir()
    (phase1 / "01-01-PLAN.md").write_text(
        "---\nphase: 1\nplan: 01\n---\n# Plan\n## Task 1\nSetup\n"
    )
    (phase1 / "01-01-SUMMARY.md").write_text(
        "---\none-liner: Setup done\nphase: 1\n---\n# Summary\n## Task 1\nDone\n"
    )
    (phase1 / "01-CONTEXT.md").write_text("# Context\n")
    (phase1 / "01-RESEARCH.md").write_text("# Research\n")

    # Phase 2 with plan only
    phase2 = phases / "02-core"
    phase2.mkdir()
    (phase2 / "02-01-PLAN.md").write_text(
        "---\nphase: 2\nplan: 01\n---\n# Plan\n## Task 1\n"
    )

    # Phase 3 pending (no plans)
    phase3 = phases / "03-advanced"
    phase3.mkdir()

    # ROADMAP.md
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## v1.0: First Release\n\n"
        "### Phase 1: Setup\n\n**Goal:** Project setup\n"
        "**Requirements**: REQ-01\n"
        "**Plans:** 1 plans\n\n"
        "### Phase 2: Core\n\n**Goal:** Core module\n"
        "**Requirements**: REQ-02, REQ-03\n"
        "**Plans:** 1 plans\n\n"
        "### Phase 3: Advanced\n\n**Goal:** Advanced features\n"
        "**Requirements**: TBD\n"
        "**Plans:** TBD\n"
    )

    # STATE.md
    (planning / "STATE.md").write_text(
        "# Session State\n\n"
        "**Milestone:** v1.0\n"
        "**Status:** Executing\n"
        "**Last Activity:** 2026-03-13\n"
    )

    # PROJECT.md
    (planning / "PROJECT.md").write_text("# Project\n\nTest project.\n")

    # REQUIREMENTS.md
    (planning / "REQUIREMENTS.md").write_text(
        "# Requirements\n\n"
        "- [ ] **REQ-01** Setup requirement\n"
        "- [ ] **REQ-02** Core requirement A\n"
    )

    if with_git:
        (tmp_path / ".git").mkdir()

    return planning


class TestDiscoverPhaseArtifacts:
    def test_finds_artifacts(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        artifacts = discover_phase_artifacts(
            tmp_path, ".planning/phases/01-setup"
        )
        assert "context_path" in artifacts
        assert "research_path" in artifacts

    def test_no_artifacts(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        artifacts = discover_phase_artifacts(
            tmp_path, ".planning/phases/03-advanced"
        )
        assert artifacts == {}


class TestInitExecutePhase:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_execute_phase(tmp_path, "2")
        assert result["phase_found"] is True
        assert result["phase_number"] is not None
        assert "executor_model" in result
        assert "verifier_model" in result
        assert result["plan_count"] >= 1

    def test_missing_phase(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_execute_phase(tmp_path, "99")
        assert result["phase_found"] is False

    def test_no_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="phase required"):
            init_execute_phase(tmp_path, "")

    def test_includes_branch_name(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_execute_phase(tmp_path, "2")
        assert result["branch_name"] is not None
        assert "phase" in result["branch_name"]

    def test_extracts_requirements(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_execute_phase(tmp_path, "2")
        assert result["phase_req_ids"] is not None
        assert "REQ-02" in result["phase_req_ids"]


class TestInitPlanPhase:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_plan_phase(tmp_path, "2")
        assert result["phase_found"] is True
        assert "researcher_model" in result
        assert "planner_model" in result

    def test_discovers_artifacts(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_plan_phase(tmp_path, "1")
        assert "context_path" in result or result["has_context"] is True

    def test_no_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="phase required"):
            init_plan_phase(tmp_path, "")


class TestInitNewProject:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path, with_git=True)
        result = init_new_project(tmp_path)
        assert "researcher_model" in result
        assert "project_exists" in result
        assert result["has_git"] is True

    def test_detects_brownfield(self, tmp_path: Path) -> None:
        planning = _make_project(tmp_path)
        (tmp_path / "requirements.txt").write_text("flask\n")
        result = init_new_project(tmp_path)
        assert result["has_package_file"] is True
        assert result["is_brownfield"] is True


class TestInitNewMilestone:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_new_milestone(tmp_path)
        assert "researcher_model" in result
        assert result["current_milestone"] is not None

    def test_file_existence(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_new_milestone(tmp_path)
        assert result["project_exists"] is True
        assert result["roadmap_exists"] is True
        assert result["state_exists"] is True


class TestInitQuick:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_quick(tmp_path, "fix login bug")
        assert result["slug"] is not None
        assert result["next_num"] == 1

    def test_increments_num(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        quick_dir = tmp_path / ".planning" / "quick"
        quick_dir.mkdir(parents=True)
        (quick_dir / "1-first-task").mkdir()
        result = init_quick(tmp_path, "second task")
        assert result["next_num"] == 2


class TestInitResume:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_resume(tmp_path)
        assert result["state_exists"] is True
        assert result["has_interrupted_agent"] is False

    def test_detects_interrupted_agent(self, tmp_path: Path) -> None:
        planning = _make_project(tmp_path)
        (planning / "current-agent-id.txt").write_text("agent-123\n")
        result = init_resume(tmp_path)
        assert result["has_interrupted_agent"] is True
        assert result["interrupted_agent_id"] == "agent-123"


class TestInitVerifyWork:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_verify_work(tmp_path, "1")
        assert result["phase_found"] is True
        assert "planner_model" in result

    def test_no_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="phase required"):
            init_verify_work(tmp_path, "")


class TestInitPhaseOp:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_phase_op(tmp_path, "2")
        assert result["phase_found"] is True
        assert "phase_dir" in result

    def test_falls_back_to_roadmap(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_phase_op(tmp_path, "3")
        assert result["phase_found"] is True
        assert result["phase_name"] is not None


class TestInitTodos:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_todos(tmp_path)
        assert "todo_count" in result
        assert "date" in result

    def test_with_area_filter(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_todos(tmp_path, area="bugs")
        assert result["area_filter"] == "bugs"


class TestInitMilestoneOp:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_milestone_op(tmp_path)
        assert result["milestone_version"] is not None
        assert "phase_count" in result
        assert "completed_phases" in result

    def test_counts_completed(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_milestone_op(tmp_path)
        assert result["completed_phases"] >= 1
        assert result["phase_count"] == 3


class TestInitMapCodebase:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_map_codebase(tmp_path)
        assert "mapper_model" in result
        assert "existing_maps" in result

    def test_detects_existing_maps(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        codebase_dir = tmp_path / ".planning" / "codebase"
        codebase_dir.mkdir()
        (codebase_dir / "tech-map.md").write_text("# Tech\n")
        result = init_map_codebase(tmp_path)
        assert result["has_maps"] is True
        assert len(result["existing_maps"]) == 1


class TestInitProgress:
    def test_loads_context(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_progress(tmp_path)
        assert "phases" in result
        assert result["phase_count"] == 3
        assert result["completed_count"] >= 1

    def test_finds_current_phase(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        result = init_progress(tmp_path)
        assert result["current_phase"] is not None

    def test_detects_paused(self, tmp_path: Path) -> None:
        planning = _make_project(tmp_path)
        state = (planning / "STATE.md").read_text()
        state += "\n**Paused At:** Phase 2, Task 3\n"
        (planning / "STATE.md").write_text(state)
        result = init_progress(tmp_path)
        assert result["paused_at"] is not None
