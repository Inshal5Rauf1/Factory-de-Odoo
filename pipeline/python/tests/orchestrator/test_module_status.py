"""Tests for orchestrator module_status module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from amil_utils.orchestrator.module_status import (
    VALID_TRANSITIONS,
    module_status_get,
    module_status_init,
    module_status_read,
    module_status_transition,
    read_status_file,
    tier_status,
)


class TestValidTransitions:
    def test_planned_to_spec_approved(self) -> None:
        assert "spec_approved" in VALID_TRANSITIONS["planned"]

    def test_shipped_is_terminal(self) -> None:
        assert VALID_TRANSITIONS["shipped"] == []


class TestReadStatusFile:
    def test_returns_empty_when_missing(self, tmp_path: Path) -> None:
        data = read_status_file(tmp_path)
        assert data["modules"] == {}

    def test_reads_existing(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "module_status.json").write_text(json.dumps({
            "_meta": {"version": 1},
            "modules": {"hr_payroll": {"status": "planned"}},
            "tiers": {},
        }))
        data = read_status_file(tmp_path)
        assert "hr_payroll" in data["modules"]


class TestModuleStatusRead:
    def test_returns_full_data(self, tmp_path: Path) -> None:
        data = module_status_read(tmp_path)
        assert "modules" in data
        assert "_meta" in data


class TestModuleStatusGet:
    def test_returns_planned_default(self, tmp_path: Path) -> None:
        result = module_status_get(tmp_path, "new_module")
        assert result["status"] == "planned"
        assert result["name"] == "new_module"

    def test_returns_existing_status(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "module_status.json").write_text(json.dumps({
            "_meta": {"version": 1},
            "modules": {"hr_payroll": {"status": "generated", "tier": "core"}},
            "tiers": {},
        }))
        result = module_status_get(tmp_path, "hr_payroll")
        assert result["status"] == "generated"


class TestModuleStatusInit:
    def test_creates_module_entry(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        result = module_status_init(tmp_path, "hr_payroll", "core", ["base"])
        assert result["modules"]["hr_payroll"]["status"] == "planned"
        assert result["modules"]["hr_payroll"]["tier"] == "core"

    def test_creates_artifact_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        module_status_init(tmp_path, "hr_payroll", "core")
        assert (tmp_path / ".planning" / "modules" / "hr_payroll" / "CONTEXT.md").exists()

    def test_duplicate_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        module_status_init(tmp_path, "hr_payroll", "core")
        with pytest.raises(ValueError, match="already exists"):
            module_status_init(tmp_path, "hr_payroll", "core")


class TestModuleStatusTransition:
    def test_valid_transition(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        module_status_init(tmp_path, "hr_payroll", "core")
        result = module_status_transition(tmp_path, "hr_payroll", "spec_approved")
        assert result["modules"]["hr_payroll"]["status"] == "spec_approved"

    def test_invalid_transition_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        module_status_init(tmp_path, "hr_payroll", "core")
        with pytest.raises(ValueError, match="Invalid transition"):
            module_status_transition(tmp_path, "hr_payroll", "shipped")

    def test_transition_chain(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        module_status_init(tmp_path, "mod_a", "core")
        module_status_transition(tmp_path, "mod_a", "spec_approved")
        module_status_transition(tmp_path, "mod_a", "generated")
        module_status_transition(tmp_path, "mod_a", "checked")
        result = module_status_transition(tmp_path, "mod_a", "shipped")
        assert result["modules"]["mod_a"]["status"] == "shipped"


class TestTierStatus:
    def test_groups_by_tier(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        module_status_init(tmp_path, "mod_a", "core")
        module_status_init(tmp_path, "mod_b", "hr")
        result = tier_status(tmp_path)
        assert "core" in result["tiers"]
        assert "hr" in result["tiers"]

    def test_complete_tier(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        module_status_init(tmp_path, "mod_a", "core")
        module_status_transition(tmp_path, "mod_a", "spec_approved")
        module_status_transition(tmp_path, "mod_a", "generated")
        module_status_transition(tmp_path, "mod_a", "checked")
        module_status_transition(tmp_path, "mod_a", "shipped")
        result = tier_status(tmp_path)
        assert result["tiers"]["core"]["status"] == "complete"
