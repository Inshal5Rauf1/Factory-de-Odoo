"""Tests for orchestrator roadmap module."""
from __future__ import annotations

from pathlib import Path

from amil_utils.orchestrator.roadmap import (
    roadmap_analyze,
    roadmap_get_phase,
    roadmap_update_plan_progress,
)

SAMPLE_ROADMAP = """\
# Roadmap

## Milestone v1.0: Core Setup

### Phase 1: Foundation

**Goal:** Build the core infrastructure

**Success Criteria**:
1. All base models created
2. Security rules in place

### Phase 2: Features

**Goal:** Add user-facing features

- [ ] **Phase 1: Foundation** — Core setup
- [x] **Phase 2: Features** — Feature work (completed 2026-03-10)
"""


class TestRoadmapGetPhase:
    def test_finds_phase(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        result = roadmap_get_phase(tmp_path, "1")
        assert result["found"] is True
        assert result["phase_name"] == "Foundation"
        assert result["goal"] == "Build the core infrastructure"

    def test_extracts_success_criteria(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        result = roadmap_get_phase(tmp_path, "1")
        assert len(result["success_criteria"]) == 2

    def test_not_found(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        result = roadmap_get_phase(tmp_path, "99")
        assert result["found"] is False

    def test_no_roadmap_file(self, tmp_path: Path) -> None:
        result = roadmap_get_phase(tmp_path, "1")
        assert result["found"] is False


class TestRoadmapAnalyze:
    def test_counts_phases(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        result = roadmap_analyze(tmp_path)
        assert result["phase_count"] == 2

    def test_finds_milestones(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        result = roadmap_analyze(tmp_path)
        assert len(result["milestones"]) >= 1

    def test_no_roadmap_returns_empty(self, tmp_path: Path) -> None:
        result = roadmap_analyze(tmp_path)
        assert result["phases"] == []
        assert result["phase_count"] == 0

    def test_disk_status_detection(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-foundation"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan")
        result = roadmap_analyze(tmp_path)
        p1 = next((p for p in result["phases"] if p["number"] == "1"), None)
        assert p1 is not None
        assert p1["disk_status"] == "planned"


class TestRoadmapUpdatePlanProgress:
    def test_updates_progress(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        phases_dir = planning / "phases" / "01-foundation"
        phases_dir.mkdir(parents=True)
        (phases_dir / "PLAN.md").write_text("# Plan")
        (phases_dir / "01-SUMMARY.md").write_text("# Summary")
        result = roadmap_update_plan_progress(tmp_path, "1")
        assert result["updated"] is True
        assert result["plan_count"] == 1
        assert result["summary_count"] == 1

    def test_phase_not_found(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text(SAMPLE_ROADMAP)
        result = roadmap_update_plan_progress(tmp_path, "99")
        assert result.get("updated") is False
