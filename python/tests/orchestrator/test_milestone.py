"""Tests for orchestrator milestone module."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from amil_utils.orchestrator.milestone import (
    milestone_complete,
    requirements_mark_complete,
)


def _make_milestone_project(tmp_path: Path) -> Path:
    """Create a .planning directory for milestone tests."""
    planning = tmp_path / ".planning"
    planning.mkdir()
    phases = planning / "phases"
    phases.mkdir()

    # Phase 1 with plan + summary
    phase1 = phases / "01-setup"
    phase1.mkdir()
    (phase1 / "01-01-PLAN.md").write_text(
        "---\nphase: 1\nplan: 01\n---\n# Plan\n## Task 1\nSetup\n"
    )
    (phase1 / "01-01-SUMMARY.md").write_text(
        "---\none-liner: Set up project structure\nphase: 1\nplan: 01\n---\n"
        "# Summary\n## Task 1\nDone\n"
    )

    # Phase 2 with plan + summary
    phase2 = phases / "02-core"
    phase2.mkdir()
    (phase2 / "02-01-PLAN.md").write_text(
        "---\nphase: 2\nplan: 01\n---\n# Plan\n## Task 1\n## Task 2\n"
    )
    (phase2 / "02-01-SUMMARY.md").write_text(
        "---\none-liner: Built core module\nphase: 2\nplan: 01\n---\n"
        "# Summary\n## Task 1\n## Task 2\n"
    )

    # ROADMAP.md
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n"
        "### Phase 1: Setup\n\n"
        "**Goal:** Project setup\n"
        "**Requirements**: REQ-01\n"
        "**Plans:** 1 plans\n\n"
        "### Phase 2: Core\n\n"
        "**Goal:** Core module\n"
        "**Requirements**: REQ-02, REQ-03\n"
        "**Plans:** 1 plans\n"
    )

    # REQUIREMENTS.md
    (planning / "REQUIREMENTS.md").write_text(
        "# Requirements\n\n"
        "- [ ] **REQ-01** Setup requirement\n"
        "- [ ] **REQ-02** Core requirement A\n"
        "- [ ] **REQ-03** Core requirement B\n\n"
        "## Traceability\n\n"
        "| Requirement | Phase | Status |\n"
        "|-------------|-------|--------|\n"
        "| REQ-01 | Phase 1 | Pending |\n"
        "| REQ-02 | Phase 2 | Pending |\n"
        "| REQ-03 | Phase 2 | Pending |\n"
    )

    # STATE.md
    (planning / "STATE.md").write_text(
        "# Session State\n\n"
        "**Milestone:** v1.0\n"
        "**Status:** Executing\n"
        "**Last Activity:** 2026-03-13\n"
        "**Last Activity Description:** Working\n"
    )

    return planning


class TestRequirementsMarkComplete:
    def test_marks_checkbox_complete(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = requirements_mark_complete(tmp_path, ["REQ-01"])
        assert result["updated"] is True
        assert "REQ-01" in result["marked_complete"]
        content = (tmp_path / ".planning" / "REQUIREMENTS.md").read_text()
        assert "[x] **REQ-01**" in content

    def test_marks_table_complete(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        requirements_mark_complete(tmp_path, ["REQ-02"])
        content = (tmp_path / ".planning" / "REQUIREMENTS.md").read_text()
        assert re.search(r"REQ-02.*Complete", content)

    def test_multiple_ids(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = requirements_mark_complete(tmp_path, ["REQ-01", "REQ-02"])
        assert len(result["marked_complete"]) == 2

    def test_not_found(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = requirements_mark_complete(tmp_path, ["REQ-99"])
        assert "REQ-99" in result["not_found"]

    def test_missing_file(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        result = requirements_mark_complete(tmp_path, ["REQ-01"])
        assert result["updated"] is False
        assert "not found" in result.get("reason", "").lower()

    def test_comma_separated_input(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = requirements_mark_complete(tmp_path, ["REQ-01,REQ-02"])
        assert len(result["marked_complete"]) == 2


class TestMilestoneComplete:
    def test_archives_roadmap(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = milestone_complete(tmp_path, "v1.0")
        assert result["archived"]["roadmap"] is True
        assert (tmp_path / ".planning" / "milestones" / "v1.0-ROADMAP.md").exists()

    def test_archives_requirements(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = milestone_complete(tmp_path, "v1.0")
        assert result["archived"]["requirements"] is True
        archived = (tmp_path / ".planning" / "milestones" / "v1.0-REQUIREMENTS.md").read_text()
        assert "SHIPPED" in archived

    def test_creates_milestones_md(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        milestone_complete(tmp_path, "v1.0", name="First Release")
        content = (tmp_path / ".planning" / "MILESTONES.md").read_text()
        assert "v1.0 First Release" in content
        assert "Set up project structure" in content

    def test_updates_state(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        milestone_complete(tmp_path, "v1.0")
        state = (tmp_path / ".planning" / "STATE.md").read_text()
        assert "milestone complete" in state

    def test_archives_phases(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = milestone_complete(tmp_path, "v1.0", archive_phases=True)
        assert result["archived"]["phases"] is True
        archive_dir = tmp_path / ".planning" / "milestones" / "v1.0-phases"
        assert archive_dir.exists()

    def test_gathers_stats(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        result = milestone_complete(tmp_path, "v1.0")
        assert result["phases"] == 2
        assert result["plans"] == 2
        assert len(result["accomplishments"]) == 2

    def test_appends_to_existing_milestones(self, tmp_path: Path) -> None:
        planning = _make_milestone_project(tmp_path)
        (planning / "MILESTONES.md").write_text(
            "# Milestones\n\n## v0.9 Beta (Shipped: 2026-01-01)\n\nOld stuff\n"
        )
        milestone_complete(tmp_path, "v1.0")
        content = (planning / "MILESTONES.md").read_text()
        # v1.0 should appear before v0.9 (reverse chronological)
        assert content.index("v1.0") < content.index("v0.9")

    def test_version_required(self, tmp_path: Path) -> None:
        _make_milestone_project(tmp_path)
        with pytest.raises(ValueError, match="version"):
            milestone_complete(tmp_path, "")
