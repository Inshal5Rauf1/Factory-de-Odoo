"""Shared fixtures for orchestrator tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal Amil project structure for testing."""
    planning = tmp_path / ".planning"
    planning.mkdir()
    (planning / "config.json").write_text(
        json.dumps(
            {
                "profile": "quality",
                "branching": {"strategy": "phase-branch"},
            }
        )
    )
    (planning / "STATE.md").write_text(
        "# State\n\n**Current Phase:** 1.0\n**Status:** executing\n"
    )
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## Phase 1.0 \u2014 Setup\n\n**Goal:** Initial setup\n"
    )
    return tmp_path


@pytest.fixture
def sample_registry(tmp_path: Path) -> Path:
    """Create a sample model_registry.json."""
    reg_path = tmp_path / ".planning" / "model_registry.json"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(
        json.dumps(
            {
                "version": 2,
                "modules": {},
                "models": {},
            }
        )
    )
    return reg_path
