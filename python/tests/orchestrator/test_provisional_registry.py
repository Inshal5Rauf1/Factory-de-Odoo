"""Tests for orchestrator provisional_registry module."""
from __future__ import annotations

import json
from pathlib import Path

from amil_utils.orchestrator.provisional_registry import (
    PROV_REGISTRY_FILE,
    analyze_forward_references,
    build_from_decomposition,
    find_critical_chains,
    get_prov_registry_path,
    load,
    mark_built,
    resolve_reference,
    save,
    update_from_spec,
)


SAMPLE_DECOMPOSITION = {
    "modules": [
        {
            "name": "hr_employee",
            "models": [
                {
                    "name": "hr.employee",
                    "fields": [
                        {"name": "name", "type": "Char"},
                        {"name": "department_id", "type": "Many2one", "comodel_name": "hr.department"},
                        {"name": "contract_id", "type": "Many2one", "comodel_name": "hr.contract"},
                    ],
                },
            ],
            "depends": ["base"],
        },
        {
            "name": "hr_department",
            "models": [
                {
                    "name": "hr.department",
                    "fields": [
                        {"name": "name", "type": "Char"},
                        {"name": "manager_id", "type": "Many2one", "comodel_name": "hr.employee"},
                    ],
                },
            ],
            "depends": ["base"],
        },
        {
            "name": "hr_contract",
            "models": [
                {
                    "name": "hr.contract",
                    "fields": [
                        {"name": "employee_id", "type": "Many2one", "comodel_name": "hr.employee"},
                        {"name": "wage", "type": "Float"},
                        {"name": "state", "type": "Selection"},
                    ],
                },
            ],
            "depends": ["hr_employee"],
        },
    ],
}


class TestBuildFromDecomposition:
    def test_builds_module_entries(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        assert "hr_employee" in reg["modules"]
        assert "hr_department" in reg["modules"]
        assert reg["modules"]["hr_employee"]["status"] == "provisional"

    def test_builds_model_entries(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        assert "hr.employee" in reg["models"]
        assert reg["models"]["hr.employee"]["module"] == "hr_employee"

    def test_tracks_references(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        refs = reg["references"]
        m2o_refs = [r for r in refs if r["from_module"] == "hr_employee"]
        assert len(m2o_refs) == 2  # department_id, contract_id

    def test_confidence_based_on_field_count(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        assert reg["models"]["hr.employee"]["confidence"] == "high"  # 3 fields

    def test_empty_decomposition(self) -> None:
        reg = build_from_decomposition({"modules": []})
        assert reg["modules"] == {}
        assert reg["models"] == {}


class TestUpdateFromSpec:
    def test_upgrades_status(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        spec = {
            "module_name": "hr_employee",
            "models": [{"name": "hr.employee", "fields": [
                {"name": "name", "type": "Char"},
                {"name": "department_id", "type": "Many2one", "comodel_name": "hr.department"},
            ]}],
            "depends": ["base", "mail"],
        }
        updated = update_from_spec(reg, spec)
        assert updated["modules"]["hr_employee"]["status"] == "spec_approved"
        assert updated["models"]["hr.employee"]["confidence"] == "high"
        assert updated["models"]["hr.employee"]["source"] == "spec"

    def test_immutable(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        updated = update_from_spec(reg, {
            "module_name": "hr_employee",
            "models": [],
            "depends": [],
        })
        assert reg["modules"]["hr_employee"]["status"] == "provisional"
        assert updated["modules"]["hr_employee"]["status"] == "spec_approved"


class TestMarkBuilt:
    def test_marks_module_built(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        updated = mark_built(reg, "hr_employee")
        assert updated["modules"]["hr_employee"]["status"] == "built"
        assert updated["models"]["hr.employee"]["source"] == "built"

    def test_immutable(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        mark_built(reg, "hr_employee")
        assert reg["modules"]["hr_employee"]["status"] == "provisional"


class TestResolveReference:
    def test_standard_odoo_model(self) -> None:
        result = resolve_reference("res.partner", None, None)
        assert result["found"] is True
        assert result["source"] == "odoo_base"

    def test_from_provisional(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        result = resolve_reference("hr.employee", None, reg)
        assert result["found"] is True
        assert result["source"] == "decomposition"

    def test_from_real_registry(self) -> None:
        real = {"models": {"hr.employee": {"module": "hr_employee"}}}
        result = resolve_reference("hr.employee", real, None)
        assert result["found"] is True
        assert result["source"] == "built"

    def test_not_found(self) -> None:
        result = resolve_reference("nonexistent.model", None, {"models": {}})
        assert result["found"] is False


class TestAnalyzeForwardReferences:
    def test_finds_forward_refs(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        result = analyze_forward_references(reg)
        assert len(result["forward_refs"]) > 0

    def test_finds_circular_risks(self) -> None:
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        result = analyze_forward_references(reg)
        # hr_employee→hr_department and hr_department→hr_employee
        circular_pairs = [c["pair"] for c in result["circular_risks"]]
        assert any("hr_employee" in p and "hr_department" in p for p in circular_pairs)

    def test_no_refs_returns_empty(self) -> None:
        reg = build_from_decomposition({"modules": [
            {"name": "mod_a", "models": [{"name": "a.model", "fields": []}]},
        ]})
        result = analyze_forward_references(reg)
        assert result["forward_refs"] == []
        assert result["circular_risks"] == []


class TestFindCriticalChains:
    def test_finds_long_chains(self) -> None:
        reg = {
            "modules": {
                "a": {"depends": []},
                "b": {"depends": ["a"]},
                "c": {"depends": ["b"]},
                "d": {"depends": ["c"]},
                "e": {"depends": ["d"]},
            },
        }
        chains = find_critical_chains(reg)
        assert len(chains) > 0
        assert len(chains[0]) >= 4

    def test_short_chains_excluded(self) -> None:
        reg = {
            "modules": {
                "a": {"depends": []},
                "b": {"depends": ["a"]},
            },
        }
        chains = find_critical_chains(reg)
        assert len(chains) == 0

    def test_limits_to_10(self) -> None:
        # Build a wide graph that produces many chains
        modules = {}
        for i in range(20):
            deps = [f"mod_{j}" for j in range(max(0, i - 1), i)]
            modules[f"mod_{i}"] = {"depends": deps}
        reg = {"modules": modules}
        chains = find_critical_chains(reg)
        assert len(chains) <= 10


class TestSaveAndLoad:
    def test_roundtrip(self, tmp_path: Path) -> None:
        (tmp_path / ".planning").mkdir()
        reg = build_from_decomposition(SAMPLE_DECOMPOSITION)
        save(tmp_path, reg)
        loaded = load(tmp_path)
        assert loaded["modules"]["hr_employee"]["status"] == "provisional"

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        assert load(tmp_path) is None

    def test_file_path(self) -> None:
        assert PROV_REGISTRY_FILE == "provisional_registry.json"
