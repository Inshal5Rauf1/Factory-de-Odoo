"""Tests for orchestrator template module."""
from __future__ import annotations

from pathlib import Path

import pytest

from amil_utils.orchestrator.template import (
    template_fill,
    template_select,
)


class TestTemplateSelect:
    def test_minimal_for_simple_plan(self, tmp_path: Path) -> None:
        plan = tmp_path / "plan.md"
        plan.write_text("# Plan\n\n### Task 1\nDo thing\n")
        result = template_select(tmp_path, str(plan))
        assert result["type"] == "minimal"

    def test_complex_for_many_tasks(self, tmp_path: Path) -> None:
        tasks = "\n".join(f"### Task {i}\nDo thing {i}\n" for i in range(1, 8))
        plan = tmp_path / "plan.md"
        plan.write_text(f"# Plan\n\n{tasks}")
        result = template_select(tmp_path, str(plan))
        assert result["type"] == "complex"

    def test_complex_for_decisions(self, tmp_path: Path) -> None:
        plan = tmp_path / "plan.md"
        plan.write_text("# Plan\n\n## Decision\nWe decided to use X\n")
        result = template_select(tmp_path, str(plan))
        assert result["type"] == "complex"

    def test_standard_for_medium(self, tmp_path: Path) -> None:
        plan = tmp_path / "plan.md"
        plan.write_text(
            "# Plan\n\n### Task 1\n`src/a.py`\n### Task 2\n`src/b.py`\n"
            "### Task 3\n`src/c.py`\n"
        )
        result = template_select(tmp_path, str(plan))
        assert result["type"] == "standard"

    def test_fallback_on_missing_file(self, tmp_path: Path) -> None:
        result = template_select(tmp_path, str(tmp_path / "nonexistent.md"))
        assert result["type"] == "standard"


class TestTemplateFill:
    def test_summary_template(self, tmp_project: Path) -> None:
        phase_dir = tmp_project / ".planning" / "phases" / "01.0-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan")
        result = template_fill(tmp_project, "summary", phase="1.0")
        assert result["created"] is True
        assert result["template"] == "summary"
        assert "SUMMARY" in result["path"]

    def test_plan_template(self, tmp_project: Path) -> None:
        phase_dir = tmp_project / ".planning" / "phases" / "01.0-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan")
        result = template_fill(tmp_project, "plan", phase="1.0")
        assert result["created"] is True
        assert "PLAN" in result["path"]

    def test_verification_template(self, tmp_project: Path) -> None:
        phase_dir = tmp_project / ".planning" / "phases" / "01.0-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan")
        result = template_fill(tmp_project, "verification", phase="1.0")
        assert result["created"] is True
        assert "VERIFICATION" in result["path"]

    def test_unknown_type_raises(self, tmp_project: Path) -> None:
        with pytest.raises(ValueError, match="Unknown template"):
            template_fill(tmp_project, "bogus", phase="1.0")

    def test_file_already_exists(self, tmp_project: Path) -> None:
        phase_dir = tmp_project / ".planning" / "phases" / "01.0-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan")
        template_fill(tmp_project, "summary", phase="1.0")
        # Second call should report error
        result = template_fill(tmp_project, "summary", phase="1.0")
        assert "error" in result
