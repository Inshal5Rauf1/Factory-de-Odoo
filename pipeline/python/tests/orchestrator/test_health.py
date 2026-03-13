"""Tests for orchestrator health module."""
from __future__ import annotations

import json
from pathlib import Path

from amil_utils.orchestrator.health import validate_health


class TestValidateHealth:
    def test_healthy_project(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "PROJECT.md").write_text(
            "# Project\n## What This Is\nTest\n## Core Value\nTest\n## Requirements\nTest"
        )
        (planning / "ROADMAP.md").write_text("# Roadmap\n## Phase 1: Setup\n")
        (planning / "STATE.md").write_text("# State\n**Status:** Working")
        (planning / "config.json").write_text(json.dumps({"model_profile": "balanced"}))
        result = validate_health(tmp_path)
        assert result["status"] == "healthy"

    def test_missing_planning_dir(self, tmp_path: Path) -> None:
        result = validate_health(tmp_path)
        assert result["status"] == "broken"
        assert any(e["code"] == "E001" for e in result["errors"])

    def test_missing_project_md(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text("# Roadmap")
        (planning / "STATE.md").write_text("# State")
        (planning / "config.json").write_text("{}")
        result = validate_health(tmp_path)
        assert any(e["code"] == "E002" for e in result["errors"])

    def test_missing_state_md_repairable(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "PROJECT.md").write_text("# Project\n## What This Is\n## Core Value\n## Requirements")
        (planning / "ROADMAP.md").write_text("# Roadmap")
        (planning / "config.json").write_text("{}")
        result = validate_health(tmp_path)
        assert result["repairable_count"] >= 1

    def test_invalid_config_json(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "PROJECT.md").write_text("# Project\n## What This Is\n## Core Value\n## Requirements")
        (planning / "ROADMAP.md").write_text("# Roadmap")
        (planning / "STATE.md").write_text("# State")
        (planning / "config.json").write_text("{invalid json")
        result = validate_health(tmp_path)
        assert any(e["code"] == "E005" for e in result["errors"])

    def test_repair_creates_config(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "PROJECT.md").write_text("# Project\n## What This Is\n## Core Value\n## Requirements")
        (planning / "ROADMAP.md").write_text("# Roadmap")
        (planning / "STATE.md").write_text("# State\n**Status:** Working")
        result = validate_health(tmp_path, repair=True)
        assert (planning / "config.json").exists()
        assert any(r["action"] == "createConfig" for r in result.get("repairs_performed", []))

    def test_orphaned_plans_info(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "PROJECT.md").write_text("# Project\n## What This Is\n## Core Value\n## Requirements")
        (planning / "ROADMAP.md").write_text("# Roadmap\n## Phase 1: Setup")
        (planning / "STATE.md").write_text("# State")
        (planning / "config.json").write_text("{}")
        phases = planning / "phases" / "01-setup"
        phases.mkdir(parents=True)
        (phases / "01-PLAN.md").write_text("# Plan")
        result = validate_health(tmp_path)
        assert any(i["code"] == "I001" for i in result["info"])
