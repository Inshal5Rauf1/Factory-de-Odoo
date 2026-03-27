"""Tests for E24/E25/W8 bulk operation semantic validation.

Phase 63: Validates source_model existence (E24), create_model existence (E25),
and create_fields reference validity (W8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from amil_utils.validation.semantic import (
    ValidationIssue,
    _check_e24,
    _check_e25,
    _check_w8,
)


@pytest.fixture()
def base_spec() -> dict[str, Any]:
    """A base spec with two models and two bulk operations."""
    return {
        "module_name": "test_bulk_validation",
        "models": [
            {
                "name": "admission.application",
                "fields": [
                    {"name": "name", "type": "Char"},
                    {"name": "program_id", "type": "Many2one", "comodel_name": "academic.program"},
                    {"name": "state", "type": "Selection"},
                ],
            },
            {
                "name": "uni.student",
                "fields": [
                    {"name": "name", "type": "Char"},
                    {"name": "program_id", "type": "Many2one", "comodel_name": "academic.program"},
                    {"name": "department_id", "type": "Many2one", "comodel_name": "hr.department"},
                ],
            },
        ],
        "bulk_operations": [
            {
                "id": "bulk_admit",
                "name": "Bulk Admission",
                "source_model": "admission.application",
                "wizard_model": "admission.bulk.admit.wizard",
                "operation": "state_transition",
                "target_state": "admitted",
            },
            {
                "id": "bulk_challan",
                "name": "Generate Fee Challans",
                "source_model": "uni.student",
                "wizard_model": "fee.bulk.challan.wizard",
                "operation": "create_related",
                "create_model": "fee.invoice",
                "create_fields": {
                    "student_id": "source.id",
                    "fee_structure_id": "wizard.fee_structure_id",
                },
            },
        ],
    }


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    """A temporary output directory."""
    return tmp_path


# ---------------------------------------------------------------------------
# E24: Bulk operation source_model validation
# ---------------------------------------------------------------------------


class TestE24SourceModelValidation:
    """E24: source_model must exist in spec models or registry."""

    def test_source_model_in_spec_no_error(self, output_dir, base_spec):
        """Source models present in spec -> no E24 errors."""
        issues = _check_e24(output_dir, base_spec, None)
        errors = [i for i in issues if i.code == "E24"]
        assert len(errors) == 0

    def test_source_model_not_in_spec_and_no_registry_error(self, output_dir, base_spec):
        """Source model not in spec models AND no registry -> E24 error."""
        base_spec["bulk_operations"][0]["source_model"] = "nonexistent.model"
        issues = _check_e24(output_dir, base_spec, None)
        errors = [i for i in issues if i.code == "E24"]
        assert len(errors) == 1
        assert "nonexistent.model" in errors[0].message

    def test_source_model_not_in_spec_but_in_registry_no_error(self, output_dir, base_spec):
        """Source model not in spec but found in registry -> no E24 error."""
        base_spec["bulk_operations"][0]["source_model"] = "external.model"
        # Mock registry that knows about external.model
        registry = MagicMock()
        registry.show_model.return_value = MagicMock()  # non-None = found
        issues = _check_e24(output_dir, base_spec, registry)
        errors = [i for i in issues if i.code == "E24"]
        assert len(errors) == 0

    def test_no_bulk_operations_no_issues(self, output_dir):
        """Spec without bulk_operations -> no E24 issues."""
        spec: dict[str, Any] = {"module_name": "test", "models": []}
        issues = _check_e24(output_dir, spec, None)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# E25: create_related create_model validation
# ---------------------------------------------------------------------------


class TestE25CreateModelValidation:
    """E25: create_model must exist for create_related operations."""

    def test_create_model_in_spec_no_error(self, output_dir, base_spec):
        """create_model in spec models -> no E25 error."""
        # Add fee.invoice to models so create_model is valid
        base_spec["models"].append({
            "name": "fee.invoice",
            "fields": [{"name": "name", "type": "Char"}],
        })
        issues = _check_e25(output_dir, base_spec, None)
        errors = [i for i in issues if i.code == "E25"]
        assert len(errors) == 0

    def test_create_model_not_in_spec_and_no_registry_error(self, output_dir, base_spec):
        """create_model not in spec models AND no registry -> E25 error."""
        issues = _check_e25(output_dir, base_spec, None)
        errors = [i for i in issues if i.code == "E25"]
        assert len(errors) == 1
        assert "fee.invoice" in errors[0].message

    def test_create_model_not_in_spec_but_in_registry_no_error(self, output_dir, base_spec):
        """create_model not in spec but found in registry -> no E25 error."""
        registry = MagicMock()
        registry.show_model.return_value = MagicMock()  # non-None = found
        issues = _check_e25(output_dir, base_spec, registry)
        errors = [i for i in issues if i.code == "E25"]
        assert len(errors) == 0

    def test_state_transition_no_create_model_check(self, output_dir, base_spec):
        """state_transition operations -> E25 is skipped (no create_model)."""
        # Remove the create_related op, keep only state_transition
        base_spec["bulk_operations"] = [base_spec["bulk_operations"][0]]
        issues = _check_e25(output_dir, base_spec, None)
        errors = [i for i in issues if i.code == "E25"]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# W8: create_fields reference validation
# ---------------------------------------------------------------------------


class TestW8CreateFieldsValidation:
    """W8: create_fields source.X references should point to existing fields."""

    def test_valid_create_fields_no_warning(self, output_dir, base_spec):
        """create_fields referencing existing source fields -> no W8 warning."""
        # student_id -> source.id is always valid (id is always present)
        issues = _check_w8(output_dir, base_spec, None)
        warnings = [i for i in issues if i.code == "W8"]
        assert len(warnings) == 0

    def test_invalid_source_field_reference_warning(self, output_dir, base_spec):
        """create_fields referencing non-existent source field -> W8 warning."""
        base_spec["bulk_operations"][1]["create_fields"]["student_id"] = "source.nonexistent_field"
        issues = _check_w8(output_dir, base_spec, None)
        warnings = [i for i in issues if i.code == "W8"]
        assert len(warnings) == 1
        assert "nonexistent_field" in warnings[0].message

    def test_wizard_prefix_not_checked(self, output_dir, base_spec):
        """create_fields with wizard.X prefix are not checked as source fields."""
        # wizard.fee_structure_id is a wizard field, not a source field
        issues = _check_w8(output_dir, base_spec, None)
        warnings = [i for i in issues if i.code == "W8" and "wizard" in i.message]
        assert len(warnings) == 0

    def test_state_transition_skips_w8(self, output_dir, base_spec):
        """state_transition ops (no create_fields) do not produce W8 warnings."""
        base_spec["bulk_operations"] = [base_spec["bulk_operations"][0]]
        issues = _check_w8(output_dir, base_spec, None)
        warnings = [i for i in issues if i.code == "W8"]
        assert len(warnings) == 0
