"""Tests for the bulk operations preprocessor at order=85.

Phase 63: Validates spec enrichment, wizard model building, and bus dep injection.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from amil_utils.preprocessors.bulk_operations import _process_bulk_operations

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def bulk_spec_raw() -> dict[str, Any]:
    """Load the bulk test fixture as a raw dict."""
    return json.loads((FIXTURES / "bulk_spec.json").read_text())


@pytest.fixture()
def empty_spec() -> dict[str, Any]:
    """A minimal spec with no bulk_operations."""
    return {
        "module_name": "test_module",
        "depends": ["base"],
        "models": [],
    }


# ---------------------------------------------------------------------------
# Early return / no-op tests
# ---------------------------------------------------------------------------


class TestBulkPreprocessorNoOp:
    """Tests for specs without bulk operations."""

    def test_empty_bulk_operations_returns_unchanged(self, empty_spec):
        """Spec with empty bulk_operations list returns spec unchanged."""
        spec = {**empty_spec, "bulk_operations": []}
        result = _process_bulk_operations(spec)
        assert result.get("has_bulk_operations") is None or result.get("has_bulk_operations") is False

    def test_no_bulk_operations_key_returns_unchanged(self, empty_spec):
        """Spec without bulk_operations key returns spec unchanged."""
        result = _process_bulk_operations(empty_spec)
        assert "has_bulk_operations" not in result or result["has_bulk_operations"] is False


# ---------------------------------------------------------------------------
# Core enrichment tests
# ---------------------------------------------------------------------------


class TestBulkPreprocessorEnrichment:
    """Tests for preprocessor enrichment behavior."""

    def test_sets_has_bulk_operations_true(self, bulk_spec_raw):
        """Preprocessor sets has_bulk_operations=True."""
        result = _process_bulk_operations(bulk_spec_raw)
        assert result["has_bulk_operations"] is True

    def test_auto_adds_bus_to_depends(self, bulk_spec_raw):
        """Preprocessor auto-adds 'bus' to depends."""
        result = _process_bulk_operations(bulk_spec_raw)
        assert "bus" in result["depends"]

    def test_bus_not_duplicated_if_present(self, bulk_spec_raw):
        """If 'bus' is already in depends, it is not duplicated."""
        spec = deepcopy(bulk_spec_raw)
        spec["depends"].append("bus")
        result = _process_bulk_operations(spec)
        bus_count = result["depends"].count("bus")
        assert bus_count == 1

    def test_default_batch_size_state_transition(self, bulk_spec_raw):
        """state_transition gets default batch_size=50."""
        # Remove batch_size from first op to test default assignment
        spec = deepcopy(bulk_spec_raw)
        spec["bulk_operations"][0]["batch_size"] = None
        result = _process_bulk_operations(spec)
        admit_op = result["bulk_operations"][0]
        assert admit_op["batch_size"] == 50

    def test_default_batch_size_create_related(self, bulk_spec_raw):
        """create_related gets default batch_size=100."""
        spec = deepcopy(bulk_spec_raw)
        spec["bulk_operations"][1]["batch_size"] = None
        result = _process_bulk_operations(spec)
        challan_op = result["bulk_operations"][1]
        assert challan_op["batch_size"] == 100

    def test_spec_provided_batch_size_overrides_defaults(self, bulk_spec_raw):
        """Spec-provided batch_size is preserved, not overwritten."""
        spec = deepcopy(bulk_spec_raw)
        spec["bulk_operations"][0]["batch_size"] = 25
        result = _process_bulk_operations(spec)
        assert result["bulk_operations"][0]["batch_size"] == 25


# ---------------------------------------------------------------------------
# Wizard model dict tests
# ---------------------------------------------------------------------------


class TestBulkPreprocessorWizardModels:
    """Tests for wizard model dict generation."""

    def test_builds_wizard_model_dict(self, bulk_spec_raw):
        """Preprocessor builds wizard model dict with correct _name and fields."""
        result = _process_bulk_operations(bulk_spec_raw)
        wizards = result["bulk_wizards"]

        # First op -> wizard + line (has preview_fields)
        admit_wizard = next(
            w for w in wizards
            if w.get("_name") == "admission.bulk.admit.wizard"
        )
        assert admit_wizard["is_transient"] is True
        assert admit_wizard["is_bulk_wizard"] is True

        # Should have state, record_count, preview_line_ids, success_count, fail_count, error_log
        field_names = {f["name"] for f in admit_wizard.get("fields", [])}
        assert "state" in field_names
        assert "record_count" in field_names
        assert "preview_line_ids" in field_names
        assert "success_count" in field_names
        assert "fail_count" in field_names
        assert "error_log" in field_names

    def test_builds_wizard_line_model_dict(self, bulk_spec_raw):
        """Preprocessor builds wizard line model dict with wizard_id M2o and preview_fields as related."""
        result = _process_bulk_operations(bulk_spec_raw)
        wizards = result["bulk_wizards"]

        # Find the line model for first op
        admit_line = next(
            w for w in wizards
            if w.get("_name") == "admission.bulk.admit.wizard.line"
        )
        assert admit_line["is_transient"] is True
        assert admit_line["is_bulk_wizard_line"] is True

        field_names = {f["name"] for f in admit_line.get("fields", [])}
        assert "wizard_id" in field_names
        assert "selected" in field_names

    def test_wizard_has_wizard_fields_from_spec(self, bulk_spec_raw):
        """Wizard model for create_related includes wizard_fields from spec."""
        result = _process_bulk_operations(bulk_spec_raw)
        wizards = result["bulk_wizards"]

        challan_wizard = next(
            w for w in wizards
            if w.get("_name") == "fee.bulk.challan.wizard"
        )
        field_names = {f["name"] for f in challan_wizard.get("fields", [])}
        assert "fee_structure_id" in field_names
        assert "term_id" in field_names
        assert "due_date" in field_names

    def test_two_bulk_operations_produce_four_models(self, bulk_spec_raw):
        """Two bulk operations with preview_fields produce 2 wizard + 2 line = 4 models."""
        result = _process_bulk_operations(bulk_spec_raw)
        wizards = result["bulk_wizards"]
        # Both ops have preview_fields, so each gets wizard + line = 4 total
        assert len(wizards) == 4

    def test_state_field_has_correct_selection(self, bulk_spec_raw):
        """Wizard state field has select/preview/process/done selection."""
        result = _process_bulk_operations(bulk_spec_raw)
        wizards = result["bulk_wizards"]

        admit_wizard = next(
            w for w in wizards
            if w.get("_name") == "admission.bulk.admit.wizard"
        )
        state_field = next(
            f for f in admit_wizard["fields"]
            if f["name"] == "state"
        )
        assert state_field["type"] == "Selection"
        selection_values = [s[0] for s in state_field.get("selection", [])]
        assert selection_values == ["select", "preview", "process", "done"]


# ---------------------------------------------------------------------------
# Source model enrichment tests
# ---------------------------------------------------------------------------


class TestBulkPreprocessorSourceModelEnrichment:
    """Tests that preprocessor sets bulk_post_processing_batch_size on source models."""

    def test_source_model_gets_batch_size(self, bulk_spec_raw):
        """Source models referenced in bulk_operations get bulk_post_processing_batch_size."""
        result = _process_bulk_operations(bulk_spec_raw)
        models = result["models"]

        admission_model = next(
            m for m in models if m["name"] == "admission.application"
        )
        assert admission_model.get("bulk_post_processing_batch_size") == 50

    def test_non_source_model_unchanged(self, bulk_spec_raw):
        """Models not referenced as source_model do not get bulk_post_processing_batch_size
        unless they are source_model for another op."""
        result = _process_bulk_operations(bulk_spec_raw)
        models = result["models"]

        # uni.student IS a source model for bulk_challan, so it DOES get batch_size
        student_model = next(m for m in models if m["name"] == "uni.student")
        assert student_model.get("bulk_post_processing_batch_size") == 100
