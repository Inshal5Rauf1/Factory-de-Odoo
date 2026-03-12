"""Tests for sequence-based computation chain preprocessor.

Covers ChainStepSpec/ChainSpec Pydantic models and the order=22
preprocessor that auto-adds fields, sets @api.depends, and enriches
field dicts with chain metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amil_utils.spec_schema import ChainStepSpec, ChainSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def _make_spec(
    models: list[dict] | None = None,
    computation_chains: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "module_name": "test_module",
        "depends": ["base"],
        "models": models or [],
        "wizards": [],
        "computation_chains": computation_chains or [],
    }


def _find_field(spec: dict, model_name: str, field_name: str) -> dict | None:
    for model in spec.get("models", []):
        if model["name"] == model_name:
            for field in model.get("fields", []):
                if field.get("name") == field_name:
                    return field
    return None


# ---------------------------------------------------------------------------
# Pydantic schema tests
# ---------------------------------------------------------------------------


class TestChainStepSpec:
    """Pydantic validation for chain step entries."""

    def test_valid_step(self):
        """ChainStepSpec validates valid step with all required fields."""
        step = ChainStepSpec(
            model="exam.result",
            field="grade_point",
            type="Float",
            source="lookup",
            depends=["grade"],
            description="Map grade to numeric",
        )
        assert step.model == "exam.result"
        assert step.field == "grade_point"
        assert step.type == "Float"
        assert step.source == "lookup"

    def test_rejects_missing_model(self):
        """ChainStepSpec rejects step without model."""
        with pytest.raises(ValidationError):
            ChainStepSpec(field="x", type="Float", source="computation")

    def test_rejects_missing_field(self):
        """ChainStepSpec rejects step without field."""
        with pytest.raises(ValidationError):
            ChainStepSpec(model="a.model", type="Float", source="computation")

    def test_rejects_missing_type(self):
        """ChainStepSpec rejects step without type."""
        with pytest.raises(ValidationError):
            ChainStepSpec(model="a.model", field="x", source="computation")

    def test_rejects_missing_source(self):
        """ChainStepSpec rejects step without source."""
        with pytest.raises(ValidationError):
            ChainStepSpec(model="a.model", field="x", type="Float")

    def test_defaults(self):
        """ChainStepSpec defaults: depends=[], description='', aggregation=None."""
        step = ChainStepSpec(
            model="a.model", field="x", type="Float", source="computation"
        )
        assert step.depends == []
        assert step.description == ""
        assert step.aggregation is None
        assert step.lookup_table is None
        assert step.digits is None

    def test_extra_fields_allowed(self):
        """Extra fields are allowed via ConfigDict(extra='allow')."""
        step = ChainStepSpec(
            model="a.model",
            field="x",
            type="Float",
            source="computation",
            custom_key="hello",
        )
        assert step.custom_key == "hello"


class TestChainSpec:
    """Pydantic validation for chain-level entries."""

    def test_valid_chain(self):
        """ChainSpec validates chain with chain_id and steps list."""
        chain = ChainSpec(
            chain_id="cgpa_chain",
            steps=[
                ChainStepSpec(
                    model="a.model", field="x", type="Float", source="direct_input"
                ),
            ],
        )
        assert chain.chain_id == "cgpa_chain"
        assert len(chain.steps) == 1

    def test_rejects_missing_chain_id(self):
        """ChainSpec rejects chain without chain_id."""
        with pytest.raises(ValidationError):
            ChainSpec(
                steps=[
                    ChainStepSpec(
                        model="a.model",
                        field="x",
                        type="Float",
                        source="direct_input",
                    ),
                ],
            )

    def test_defaults(self):
        """ChainSpec defaults: description='', steps=[]."""
        chain = ChainSpec(chain_id="test")
        assert chain.description == ""
        assert chain.steps == []


# ---------------------------------------------------------------------------
# Preprocessor tests
# ---------------------------------------------------------------------------


class TestPreprocessorBasic:
    """Basic preprocessor behavior."""

    def test_empty_chains_returns_unchanged(self):
        """Preprocessor with empty computation_chains returns spec unchanged."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[{"name": "test.model", "fields": [{"name": "x", "type": "Float"}]}]
        )
        result = _process_computation_chains(spec)
        assert result["models"] == spec["models"]

    def test_auto_adds_missing_field(self):
        """Preprocessor auto-adds field from chain step when not in model fields."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {
                    "name": "exam.result",
                    "fields": [
                        {"name": "enrollment_id", "type": "Many2one", "comodel_name": "uni.enrollment"},
                    ],
                },
            ],
            computation_chains=[
                {
                    "chain_id": "test_chain",
                    "steps": [
                        {
                            "model": "exam.result",
                            "field": "grade_point",
                            "type": "Float",
                            "source": "computation",
                            "depends": ["grade"],
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        gp = _find_field(result, "exam.result", "grade_point")
        assert gp is not None
        assert gp["type"] == "Float"

    def test_does_not_duplicate_existing_field(self):
        """Preprocessor does NOT duplicate field when it already exists."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {
                    "name": "exam.result",
                    "fields": [
                        {"name": "grade_point", "type": "Float", "string": "GP"},
                    ],
                },
            ],
            computation_chains=[
                {
                    "chain_id": "test_chain",
                    "steps": [
                        {
                            "model": "exam.result",
                            "field": "grade_point",
                            "type": "Float",
                            "source": "computation",
                            "depends": ["grade"],
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        gp_fields = [
            f for f in result["models"][0]["fields"] if f.get("name") == "grade_point"
        ]
        assert len(gp_fields) == 1

    def test_merges_chain_attrs_into_existing_field(self):
        """Preprocessor merges chain attributes (store, compute, depends) into existing field without replacing type."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {
                    "name": "exam.result",
                    "fields": [
                        {"name": "grade_point", "type": "Float", "string": "Grade Point"},
                    ],
                },
            ],
            computation_chains=[
                {
                    "chain_id": "test_chain",
                    "steps": [
                        {
                            "model": "exam.result",
                            "field": "grade_point",
                            "type": "Float",
                            "source": "computation",
                            "depends": ["grade"],
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        gp = _find_field(result, "exam.result", "grade_point")
        assert gp["string"] == "Grade Point"  # Preserved
        assert gp["store"] is True
        assert gp["compute"] == "_compute_grade_point"
        assert gp["depends"] == ["grade"]

    def test_sets_store_true_on_computed(self):
        """Preprocessor sets store=True on computed chain fields (source != direct_input)."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {
                    "name": "exam.result",
                    "fields": [],
                },
            ],
            computation_chains=[
                {
                    "chain_id": "test_chain",
                    "steps": [
                        {
                            "model": "exam.result",
                            "field": "grade_point",
                            "type": "Float",
                            "source": "lookup",
                            "depends": ["grade"],
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        gp = _find_field(result, "exam.result", "grade_point")
        assert gp["store"] is True

    def test_sets_depends_with_dot_notation(self):
        """Preprocessor sets @api.depends from chain step depends array with dot notation preserved."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [
                        {"name": "enrollment_ids", "type": "One2many",
                         "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
                    ],
                },
            ],
            computation_chains=[
                {
                    "chain_id": "test_chain",
                    "steps": [
                        {
                            "model": "uni.student",
                            "field": "cgpa",
                            "type": "Float",
                            "source": "aggregation",
                            "aggregation": "weighted_average",
                            "depends": ["enrollment_ids.weighted_grade_points"],
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        cgpa = _find_field(result, "uni.student", "cgpa")
        assert "enrollment_ids.weighted_grade_points" in cgpa["depends"]

    def test_sets_compute_method_name(self):
        """Preprocessor sets compute method name to _compute_{field_name} convention."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[{"name": "a.model", "fields": []}],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {
                            "model": "a.model",
                            "field": "total_amount",
                            "type": "Float",
                            "source": "computation",
                            "depends": ["qty", "price"],
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        f = _find_field(result, "a.model", "total_amount")
        assert f["compute"] == "_compute_total_amount"

    def test_enriches_field_with_chain_meta(self):
        """Preprocessor enriches field dict with _chain_meta key."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[{"name": "a.model", "fields": []}],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "description": "Test chain",
                    "steps": [
                        {
                            "model": "a.model",
                            "field": "x",
                            "type": "Float",
                            "source": "direct_input",
                        },
                        {
                            "model": "a.model",
                            "field": "y",
                            "type": "Float",
                            "source": "computation",
                            "depends": ["x"],
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        y = _find_field(result, "a.model", "y")
        assert "_chain_meta" in y
        meta = y["_chain_meta"]
        assert meta["chain_id"] == "c1"
        assert meta["position_in_chain"] == 1
        assert meta["total_steps"] == 2
        assert meta["source"] == "computation"
        assert len(meta["upstream_steps"]) == 1
        assert len(meta["downstream_steps"]) == 0

    def test_stores_validated_chains_in_spec(self):
        """Preprocessor stores validated chains in spec['_computation_chains']."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[{"name": "a.model", "fields": []}],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {
                            "model": "a.model",
                            "field": "x",
                            "type": "Float",
                            "source": "direct_input",
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        assert "_computation_chains" in result
        assert len(result["_computation_chains"]) == 1
        assert result["_computation_chains"][0]["chain_id"] == "c1"

    def test_skips_direct_input_no_compute(self):
        """Preprocessor skips direct_input steps -- no compute, no depends."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[{"name": "a.model", "fields": []}],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {
                            "model": "a.model",
                            "field": "grade",
                            "type": "Selection",
                            "source": "direct_input",
                        },
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        grade = _find_field(result, "a.model", "grade")
        assert grade.get("compute") is None
        assert grade.get("store") is not True or grade.get("store") is None

    def test_missing_model_logs_warning(self):
        """Preprocessor with chain step referencing model not in spec logs warning and continues."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[{"name": "a.model", "fields": []}],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {
                            "model": "nonexistent.model",
                            "field": "x",
                            "type": "Float",
                            "source": "computation",
                            "depends": ["y"],
                        },
                    ],
                },
            ],
        )
        # Should not raise -- just warn
        result = _process_computation_chains(spec)
        assert "_computation_chains" in result

    def test_does_not_mutate_input(self):
        """Original spec dict is not mutated."""
        import copy
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[{"name": "a.model", "fields": [{"name": "x", "type": "Float"}]}],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {
                            "model": "a.model",
                            "field": "y",
                            "type": "Float",
                            "source": "computation",
                            "depends": ["x"],
                        },
                    ],
                },
            ],
        )
        original = copy.deepcopy(spec)
        _process_computation_chains(spec)
        assert spec == original


# ---------------------------------------------------------------------------
# Fixture-based integration tests
# ---------------------------------------------------------------------------


class TestCGPAChainFixture:
    """Full CGPA chain fixture (4 steps across 3 models) produces correct enriched fields."""

    def test_cgpa_chain_produces_correct_fields(self):
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _load_fixture("cgpa_chain_spec.json")
        result = _process_computation_chains(spec)

        # Step 1: exam.result.grade -- direct_input, no compute
        grade = _find_field(result, "exam.result", "grade")
        assert grade is not None
        assert grade.get("compute") is None

        # Step 2: exam.result.grade_point -- lookup, has compute
        gp = _find_field(result, "exam.result", "grade_point")
        assert gp is not None
        assert gp["store"] is True
        assert gp["compute"] == "_compute_grade_point"
        assert gp["depends"] == ["grade"]

        # Step 3: uni.enrollment.weighted_grade_points -- computation
        wgp = _find_field(result, "uni.enrollment", "weighted_grade_points")
        assert wgp is not None
        assert wgp["store"] is True
        assert wgp["compute"] == "_compute_weighted_grade_points"
        assert "result_ids.grade_point" in wgp["depends"]

        # Step 4: uni.student.cgpa -- aggregation
        cgpa = _find_field(result, "uni.student", "cgpa")
        assert cgpa is not None
        assert cgpa["store"] is True
        assert cgpa["compute"] == "_compute_cgpa"
        assert "enrollment_ids.weighted_grade_points" in cgpa["depends"]

    def test_cgpa_chain_meta_on_last_step(self):
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _load_fixture("cgpa_chain_spec.json")
        result = _process_computation_chains(spec)

        cgpa = _find_field(result, "uni.student", "cgpa")
        meta = cgpa["_chain_meta"]
        assert meta["chain_id"] == "cgpa_chain"
        assert meta["position_in_chain"] == 3
        assert meta["total_steps"] == 4
        assert meta["source"] == "aggregation"
        assert meta["aggregation"] == "weighted_average"
        assert len(meta["upstream_steps"]) == 3
        assert len(meta["downstream_steps"]) == 0


class TestFeePenaltyChainFixture:
    """Fee penalty chain fixture (3 steps across 2 models)."""

    def test_fee_penalty_produces_correct_fields(self):
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _load_fixture("fee_penalty_chain_spec.json")
        result = _process_computation_chains(spec)

        # Step 1: fee.invoice.is_overdue -- direct_input
        overdue = _find_field(result, "fee.invoice", "is_overdue")
        assert overdue is not None
        assert overdue.get("compute") is None

        # Step 2: fee.invoice.penalty_amount -- computation
        penalty = _find_field(result, "fee.invoice", "penalty_amount")
        assert penalty is not None
        assert penalty["store"] is True
        assert penalty["compute"] == "_compute_penalty_amount"

        # Step 3: uni.student.total_balance -- aggregation sum
        total = _find_field(result, "uni.student", "total_balance")
        assert total is not None
        assert total["store"] is True
        assert total["compute"] == "_compute_total_balance"
        assert "invoice_ids.penalty_amount" in total["depends"]
