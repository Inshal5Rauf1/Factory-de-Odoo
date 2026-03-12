"""Tests for BulkOperationSpec and BulkWizardFieldSpec Pydantic models.

Phase 63: Validates bulk operation schema parsing and validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from amil_utils.spec_schema import (
    BulkOperationSpec,
    BulkWizardFieldSpec,
    ModuleSpec,
    validate_spec,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def bulk_spec_raw() -> dict:
    """Load the bulk test fixture as a raw dict."""
    return json.loads((FIXTURES / "bulk_spec.json").read_text())


# ---------------------------------------------------------------------------
# BulkWizardFieldSpec tests
# ---------------------------------------------------------------------------


class TestBulkWizardFieldSpec:
    """Validate BulkWizardFieldSpec Pydantic model."""

    def test_valid_field_with_comodel(self):
        """A wizard field with comodel parses successfully."""
        field = BulkWizardFieldSpec(
            name="fee_structure_id",
            type="Many2one",
            required=True,
            comodel="fee.structure",
        )
        assert field.name == "fee_structure_id"
        assert field.type == "Many2one"
        assert field.required is True
        assert field.comodel == "fee.structure"

    def test_valid_field_without_comodel(self):
        """A wizard field without comodel defaults to None."""
        field = BulkWizardFieldSpec(name="due_date", type="Date")
        assert field.comodel is None
        assert field.required is False

    def test_missing_name_raises(self):
        """Missing required 'name' field raises ValidationError."""
        with pytest.raises(ValidationError):
            BulkWizardFieldSpec(type="Char")

    def test_missing_type_raises(self):
        """Missing required 'type' field raises ValidationError."""
        with pytest.raises(ValidationError):
            BulkWizardFieldSpec(name="some_field")


# ---------------------------------------------------------------------------
# BulkOperationSpec tests
# ---------------------------------------------------------------------------


class TestBulkOperationSpec:
    """Validate BulkOperationSpec Pydantic model."""

    def test_valid_state_transition(self):
        """A state_transition spec parses with all fields."""
        op = BulkOperationSpec(
            id="bulk_admit",
            name="Bulk Admission",
            source_model="admission.application",
            wizard_model="admission.bulk.admit.wizard",
            operation="state_transition",
            source_domain=[["state", "=", "approved"]],
            target_state="admitted",
            action_method="action_admit",
            preview_fields=["name", "program_id", "cgpa"],
            side_effects=["Create uni.student"],
            batch_size=50,
            allow_partial=True,
        )
        assert op.id == "bulk_admit"
        assert op.operation == "state_transition"
        assert op.target_state == "admitted"
        assert op.batch_size == 50

    def test_valid_create_related(self):
        """A create_related spec parses with wizard_fields and create_fields."""
        op = BulkOperationSpec(
            id="bulk_challan",
            name="Generate Fee Challans",
            source_model="uni.student",
            wizard_model="fee.bulk.challan.wizard",
            operation="create_related",
            create_model="fee.invoice",
            create_fields={
                "student_id": "source.id",
                "fee_structure_id": "wizard.fee_structure_id",
            },
            wizard_fields=[
                BulkWizardFieldSpec(
                    name="fee_structure_id",
                    type="Many2one",
                    comodel="fee.structure",
                    required=True,
                ),
            ],
        )
        assert op.operation == "create_related"
        assert op.create_model == "fee.invoice"
        assert len(op.wizard_fields) == 1
        assert op.create_fields["student_id"] == "source.id"

    def test_invalid_operation_type_raises(self):
        """An invalid operation type ('delete_all') raises ValidationError."""
        with pytest.raises(ValidationError, match="operation"):
            BulkOperationSpec(
                id="bad",
                name="Bad Op",
                source_model="some.model",
                wizard_model="some.wizard",
                operation="delete_all",
            )

    def test_missing_required_id_raises(self):
        """Missing required 'id' raises ValidationError."""
        with pytest.raises(ValidationError):
            BulkOperationSpec(
                name="No ID",
                source_model="some.model",
                wizard_model="some.wizard",
                operation="state_transition",
            )

    def test_missing_required_name_raises(self):
        """Missing required 'name' raises ValidationError."""
        with pytest.raises(ValidationError):
            BulkOperationSpec(
                id="no_name",
                source_model="some.model",
                wizard_model="some.wizard",
                operation="state_transition",
            )

    def test_missing_required_source_model_raises(self):
        """Missing required 'source_model' raises ValidationError."""
        with pytest.raises(ValidationError):
            BulkOperationSpec(
                id="no_source",
                name="No Source",
                wizard_model="some.wizard",
                operation="state_transition",
            )

    def test_missing_required_wizard_model_raises(self):
        """Missing required 'wizard_model' raises ValidationError."""
        with pytest.raises(ValidationError):
            BulkOperationSpec(
                id="no_wizard",
                name="No Wizard",
                source_model="some.model",
                operation="state_transition",
            )

    def test_batch_size_defaults_to_none(self):
        """batch_size defaults to None (preprocessor assigns defaults)."""
        op = BulkOperationSpec(
            id="test",
            name="Test",
            source_model="some.model",
            wizard_model="some.wizard",
            operation="state_transition",
        )
        assert op.batch_size is None

    def test_allow_partial_defaults_to_true(self):
        """allow_partial defaults to True."""
        op = BulkOperationSpec(
            id="test",
            name="Test",
            source_model="some.model",
            wizard_model="some.wizard",
            operation="state_transition",
        )
        assert op.allow_partial is True

    def test_update_fields_operation_valid(self):
        """update_fields is a valid operation type."""
        op = BulkOperationSpec(
            id="test",
            name="Test",
            source_model="some.model",
            wizard_model="some.wizard",
            operation="update_fields",
        )
        assert op.operation == "update_fields"


# ---------------------------------------------------------------------------
# ModuleSpec with bulk_operations end-to-end
# ---------------------------------------------------------------------------


class TestModuleSpecBulkOperations:
    """Test that ModuleSpec accepts bulk_operations array."""

    def test_module_spec_with_bulk_operations(self, bulk_spec_raw):
        """ModuleSpec with bulk_operations array validates end-to-end."""
        spec = validate_spec(bulk_spec_raw)
        assert len(spec.bulk_operations) == 2
        assert spec.bulk_operations[0].id == "bulk_admit"
        assert spec.bulk_operations[1].id == "bulk_challan"

    def test_module_spec_without_bulk_operations(self):
        """ModuleSpec without bulk_operations defaults to empty list."""
        spec = ModuleSpec(module_name="test_module")
        assert spec.bulk_operations == []

    def test_fixture_state_transition_fields(self, bulk_spec_raw):
        """State_transition op in fixture has correct fields."""
        spec = validate_spec(bulk_spec_raw)
        admit = spec.bulk_operations[0]
        assert admit.operation == "state_transition"
        assert admit.target_state == "admitted"
        assert admit.action_method == "action_admit"
        assert admit.batch_size == 50
        assert admit.allow_partial is True
        assert len(admit.preview_fields) == 3
        assert len(admit.side_effects) == 3

    def test_fixture_create_related_fields(self, bulk_spec_raw):
        """Create_related op in fixture has correct fields."""
        spec = validate_spec(bulk_spec_raw)
        challan = spec.bulk_operations[1]
        assert challan.operation == "create_related"
        assert challan.create_model == "fee.invoice"
        assert len(challan.wizard_fields) == 3
        assert len(challan.create_fields) == 4
        assert challan.batch_size == 100
