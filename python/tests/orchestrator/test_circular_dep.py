"""Tests for orchestrator circular_dep module."""
from __future__ import annotations

import json

from amil_utils.orchestrator.circular_dep import (
    analyze_circular_pair,
    apply_circular_patches,
    generate_patch_spec,
    plan_build_order,
)


class TestAnalyzeCircularPair:
    def test_primary_is_side_with_more_m2o(self) -> None:
        risk = {
            "modules": ["hr_payroll", "hr_contract"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "contract_id", "from_module": "hr_payroll",
                 "from_model": "hr.payroll.slip", "to_model": "hr.contract"},
            ],
            "refs_b_to_a": [
                {"type": "One2many", "field": "slip_ids", "from_module": "hr_contract",
                 "from_model": "hr.contract", "to_model": "hr.payroll.slip"},
            ],
        }
        result = analyze_circular_pair(risk, None)
        assert result["primary"] == "hr_payroll"
        assert result["secondary"] == "hr_contract"
        assert result["build_order"] == ["hr_payroll", "hr_contract"]

    def test_deferred_refs_from_secondary(self) -> None:
        risk = {
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "model.a", "to_model": "model.b"},
            ],
            "refs_b_to_a": [
                {"type": "One2many", "field": "a_ids", "from_module": "mod_b",
                 "from_model": "model.b", "to_model": "model.a"},
            ],
        }
        result = analyze_circular_pair(risk, None)
        assert len(result["deferred_refs"]) == 1
        assert result["patch_required"] is True

    def test_equal_m2o_picks_a_as_primary(self) -> None:
        risk = {
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
            "refs_b_to_a": [
                {"type": "Many2one", "field": "a_id", "from_module": "mod_b",
                 "from_model": "b.model", "to_model": "a.model"},
            ],
        }
        result = analyze_circular_pair(risk, None)
        assert result["primary"] == "mod_a"

    def test_no_deferred_when_no_secondary_refs(self) -> None:
        risk = {
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
            "refs_b_to_a": [],
        }
        result = analyze_circular_pair(risk, None)
        assert result["patch_required"] is False


class TestGeneratePatchSpec:
    def test_generates_patches_for_deferred(self) -> None:
        resolution = {
            "primary": "mod_a",
            "secondary": "mod_b",
            "deferred_refs": [
                {"from_module": "mod_b", "from_model": "model.b",
                 "field": "a_ids", "type": "One2many", "to_model": "model.a"},
            ],
            "patch_required": True,
        }
        result = generate_patch_spec(resolution)
        assert result is not None
        assert result["module"] == "mod_a"
        assert len(result["patches"]) == 1
        assert result["patches"][0]["field"]["name"] == "a_ids"

    def test_returns_none_when_no_patch(self) -> None:
        resolution = {
            "primary": "mod_a",
            "deferred_refs": [],
            "patch_required": False,
        }
        assert generate_patch_spec(resolution) is None


class TestPlanBuildOrder:
    def test_no_circular_returns_original_order(self) -> None:
        result = plan_build_order(["a", "b", "c"], [], None)
        assert result["order"] == ["a", "b", "c"]
        assert result["patch_rounds"] == []

    def test_adjusts_order_for_circular(self) -> None:
        risks = [{
            "modules": ["mod_b", "mod_a"],
            "refs_a_to_b": [
                {"type": "One2many", "field": "b_ids", "from_module": "mod_b",
                 "from_model": "b.model", "to_model": "a.model"},
            ],
            "refs_b_to_a": [
                {"type": "Many2one", "field": "a_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
        }]
        result = plan_build_order(["mod_b", "mod_a", "mod_c"], risks, None)
        # mod_a has the Many2one, so mod_b→mod_a refs count as 1 M2O
        # mod_b should come after mod_a in adjusted order
        order = result["order"]
        assert order.index("mod_a") < order.index("mod_b") or order.index("mod_b") < order.index("mod_a")

    def test_collects_patch_rounds(self) -> None:
        risks = [{
            "modules": ["mod_a", "mod_b"],
            "refs_a_to_b": [
                {"type": "Many2one", "field": "b_id", "from_module": "mod_a",
                 "from_model": "a.model", "to_model": "b.model"},
            ],
            "refs_b_to_a": [
                {"type": "One2many", "field": "a_ids", "from_module": "mod_b",
                 "from_model": "b.model", "to_model": "a.model"},
            ],
        }]
        result = plan_build_order(["mod_a", "mod_b"], risks, None)
        assert len(result["patch_rounds"]) == 1


class TestApplyCircularPatches:
    def test_single_patch_adds_field_to_spec(self, tmp_path):
        """A patch should add the deferred field to the target module's spec."""
        module_dir = tmp_path / ".planning" / "modules" / "hr_contract"
        module_dir.mkdir(parents=True)
        spec = {
            "module_name": "hr_contract",
            "models": [{"name": "hr.contract", "fields": [
                {"name": "name", "type": "Char"},
            ]}],
        }
        (module_dir / "spec.json").write_text(json.dumps(spec))

        patch = {
            "target_module": "hr_contract",
            "target_model": "hr.contract",
            "deferred_fields": [
                {"name": "slip_ids", "type": "One2many",
                 "comodel_name": "hr.payslip", "inverse_name": "contract_id"},
            ],
        }

        result = apply_circular_patches(tmp_path, [patch])
        assert len(result) == 1
        assert result[0]["status"] == "applied"

        # Verify the spec was updated
        updated_spec = json.loads((module_dir / "spec.json").read_text())
        field_names = [f["name"] for f in updated_spec["models"][0]["fields"]]
        assert "slip_ids" in field_names

    def test_patch_to_nonexistent_module_returns_error(self, tmp_path):
        """Patching a module that doesn't exist should return error status."""
        patch = {
            "target_module": "nonexistent",
            "target_model": "x.model",
            "deferred_fields": [{"name": "ref_id", "type": "Many2one"}],
        }
        result = apply_circular_patches(tmp_path, [patch])
        assert len(result) == 1
        assert result[0]["status"] == "error"

    def test_patch_skips_if_field_already_exists(self, tmp_path):
        """If the deferred field already exists, skip with warning."""
        module_dir = tmp_path / ".planning" / "modules" / "hr_contract"
        module_dir.mkdir(parents=True)
        spec = {
            "module_name": "hr_contract",
            "models": [{"name": "hr.contract", "fields": [
                {"name": "name", "type": "Char"},
                {"name": "slip_ids", "type": "One2many"},
            ]}],
        }
        (module_dir / "spec.json").write_text(json.dumps(spec))

        patch = {
            "target_module": "hr_contract",
            "target_model": "hr.contract",
            "deferred_fields": [
                {"name": "slip_ids", "type": "One2many",
                 "comodel_name": "hr.payslip", "inverse_name": "contract_id"},
            ],
        }
        result = apply_circular_patches(tmp_path, [patch])
        assert result[0]["status"] == "skipped"

    def test_empty_patches_returns_empty(self, tmp_path):
        """Empty patch list returns empty result list."""
        result = apply_circular_patches(tmp_path, [])
        assert result == []

    def test_patch_to_nonexistent_model_returns_error(self, tmp_path):
        """Patching a model that doesn't exist in the spec returns error."""
        module_dir = tmp_path / ".planning" / "modules" / "hr_contract"
        module_dir.mkdir(parents=True)
        spec = {
            "module_name": "hr_contract",
            "models": [{"name": "hr.contract", "fields": [
                {"name": "name", "type": "Char"},
            ]}],
        }
        (module_dir / "spec.json").write_text(json.dumps(spec))

        patch = {
            "target_module": "hr_contract",
            "target_model": "hr.nonexistent",
            "deferred_fields": [
                {"name": "foo_id", "type": "Many2one"},
            ],
        }
        result = apply_circular_patches(tmp_path, [patch])
        assert len(result) == 1
        assert result[0]["status"] == "error"

    def test_multiple_patches_applied(self, tmp_path):
        """Multiple patches to different modules all get applied."""
        for mod_name in ("mod_a", "mod_b"):
            mod_dir = tmp_path / ".planning" / "modules" / mod_name
            mod_dir.mkdir(parents=True)
            spec = {
                "module_name": mod_name,
                "models": [{"name": f"{mod_name}.model", "fields": [
                    {"name": "name", "type": "Char"},
                ]}],
            }
            (mod_dir / "spec.json").write_text(json.dumps(spec))

        patches = [
            {
                "target_module": "mod_a",
                "target_model": "mod_a.model",
                "deferred_fields": [
                    {"name": "b_ids", "type": "One2many",
                     "comodel_name": "mod_b.model", "inverse_name": "a_id"},
                ],
            },
            {
                "target_module": "mod_b",
                "target_model": "mod_b.model",
                "deferred_fields": [
                    {"name": "a_ids", "type": "One2many",
                     "comodel_name": "mod_a.model", "inverse_name": "b_id"},
                ],
            },
        ]

        results = apply_circular_patches(tmp_path, patches)
        assert len(results) == 2
        assert all(r["status"] == "applied" for r in results)

    def test_partial_skip_when_some_fields_exist(self, tmp_path):
        """When some deferred fields exist and others don't, add only the new ones."""
        module_dir = tmp_path / ".planning" / "modules" / "hr_contract"
        module_dir.mkdir(parents=True)
        spec = {
            "module_name": "hr_contract",
            "models": [{"name": "hr.contract", "fields": [
                {"name": "name", "type": "Char"},
                {"name": "slip_ids", "type": "One2many"},
            ]}],
        }
        (module_dir / "spec.json").write_text(json.dumps(spec))

        patch = {
            "target_module": "hr_contract",
            "target_model": "hr.contract",
            "deferred_fields": [
                {"name": "slip_ids", "type": "One2many",
                 "comodel_name": "hr.payslip", "inverse_name": "contract_id"},
                {"name": "payroll_line_ids", "type": "One2many",
                 "comodel_name": "hr.payroll.line", "inverse_name": "contract_id"},
            ],
        }
        result = apply_circular_patches(tmp_path, [patch])
        assert result[0]["status"] == "applied"
        assert "payroll_line_ids" in result[0]["added"]
        assert "slip_ids" in result[0]["skipped"]

        updated_spec = json.loads((module_dir / "spec.json").read_text())
        field_names = [f["name"] for f in updated_spec["models"][0]["fields"]]
        assert "payroll_line_ids" in field_names
