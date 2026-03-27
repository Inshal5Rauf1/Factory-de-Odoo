"""Tests for E18-E22 chain validation checks.

Covers type compatibility (E18), dot-path traversal (E19),
store propagation (E20), cross-chain cycles (E21),
and comodel field existence (E22).
"""

from __future__ import annotations

from typing import Any

import pytest

from amil_utils.preprocessors.computation_chains import (
    _validate_chain_types,
    _validate_chain_traversal,
    _validate_chain_store_propagation,
    _validate_chain_cycles,
    _validate_chain_field_existence,
)
from amil_utils.spec_schema import ChainSpec, ChainStepSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _step(
    model: str = "a.model",
    field: str = "x",
    type_: str = "Float",
    source: str = "computation",
    depends: list[str] | None = None,
    aggregation: str | None = None,
    **kwargs: Any,
) -> ChainStepSpec:
    return ChainStepSpec(
        model=model,
        field=field,
        type=type_,
        source=source,
        depends=depends or [],
        aggregation=aggregation,
        **kwargs,
    )


def _chain(
    chain_id: str = "test_chain",
    steps: list[ChainStepSpec] | None = None,
) -> ChainSpec:
    return ChainSpec(chain_id=chain_id, steps=steps or [])


# ---------------------------------------------------------------------------
# E18: Chain type incompatibility
# ---------------------------------------------------------------------------


class TestE18ChainTypes:
    """E18: Type compatibility checks for aggregation/source types."""

    def test_sum_on_char_error(self):
        """sum aggregation on Char field -> error."""
        steps = [
            _step(field="name", type_="Char", source="aggregation", aggregation="sum",
                  depends=["rel_ids.name"]),
        ]
        spec = _make_spec(models=[{"name": "a.model", "fields": []}])
        issues = _validate_chain_types(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) >= 1
        assert "E18" in errors[0][1]

    def test_sum_on_float_no_error(self):
        """sum aggregation on Float field -> no error."""
        steps = [
            _step(field="amount", type_="Float", source="aggregation", aggregation="sum",
                  depends=["rel_ids.amount"]),
        ]
        spec = _make_spec(models=[{"name": "a.model", "fields": []}])
        issues = _validate_chain_types(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0

    def test_weighted_average_non_numeric_numerator_error(self):
        """weighted_average with non-numeric numerator -> error."""
        steps = [
            _step(
                field="avg",
                type_="Char",
                source="aggregation",
                aggregation="weighted_average",
                depends=["rel_ids.name", "rel_ids.weight"],
            ),
        ]
        spec = _make_spec(models=[{"name": "a.model", "fields": []}])
        issues = _validate_chain_types(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) >= 1

    def test_weighted_average_two_floats_no_error(self):
        """weighted_average with two Float fields -> no error."""
        steps = [
            _step(
                field="avg",
                type_="Float",
                source="aggregation",
                aggregation="weighted_average",
                depends=["rel_ids.amount", "rel_ids.weight"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "a.model",
                    "fields": [
                        {"name": "rel_ids", "type": "One2many",
                         "comodel_name": "b.model", "inverse_name": "a_id"},
                    ],
                },
                {
                    "name": "b.model",
                    "fields": [
                        {"name": "a_id", "type": "Many2one", "comodel_name": "a.model"},
                        {"name": "amount", "type": "Float"},
                        {"name": "weight", "type": "Float"},
                    ],
                },
            ],
        )
        issues = _validate_chain_types(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0

    def test_lookup_on_integer_warning(self):
        """lookup source on Integer field -> warning (not error)."""
        steps = [
            _step(field="mapped_val", type_="Integer", source="lookup",
                  depends=["code"]),
        ]
        spec = _make_spec(models=[{"name": "a.model", "fields": []}])
        issues = _validate_chain_types(steps, spec)
        warnings = [i for i in issues if i[0] == "warning"]
        errors = [i for i in issues if i[0] == "error"]
        assert len(warnings) >= 1
        assert len(errors) == 0

    def test_lookup_on_selection_no_issue(self):
        """lookup source on Selection field -> no error/warning."""
        steps = [
            _step(field="mapped_val", type_="Float", source="lookup",
                  depends=["grade"]),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "a.model",
                    "fields": [{"name": "grade", "type": "Selection"}],
                },
            ],
        )
        issues = _validate_chain_types(steps, spec)
        assert len(issues) == 0

    def test_count_on_any_type_no_error(self):
        """count aggregation on any type -> no error."""
        steps = [
            _step(field="cnt", type_="Integer", source="aggregation",
                  aggregation="count", depends=["rel_ids.id"]),
        ]
        spec = _make_spec(models=[{"name": "a.model", "fields": []}])
        issues = _validate_chain_types(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# E19: Chain depends traversal correctness
# ---------------------------------------------------------------------------


class TestE19ChainTraversal:
    """E19: Dot-path traversal validation."""

    def test_valid_dot_path_no_error(self):
        """dot-path where relational field + comodel field exist -> no error."""
        steps = [
            _step(
                model="uni.student",
                field="cgpa",
                depends=["enrollment_ids.grade_points"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [
                        {"name": "enrollment_ids", "type": "One2many",
                         "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
                    ],
                },
                {
                    "name": "uni.enrollment",
                    "fields": [
                        {"name": "student_id", "type": "Many2one",
                         "comodel_name": "uni.student"},
                        {"name": "grade_points", "type": "Float"},
                    ],
                },
            ],
        )
        issues = _validate_chain_traversal(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0

    def test_non_relational_first_segment_error(self):
        """dot-path where first segment is NOT relational -> error."""
        steps = [
            _step(
                model="uni.student",
                field="cgpa",
                depends=["name.something"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [{"name": "name", "type": "Char"}],
                },
            ],
        )
        issues = _validate_chain_traversal(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) >= 1
        assert "E19" in errors[0][1]

    def test_comodel_field_not_exist_error(self):
        """dot-path where comodel exists but field does not -> error."""
        steps = [
            _step(
                model="uni.student",
                field="cgpa",
                depends=["enrollment_ids.nonexistent"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [
                        {"name": "enrollment_ids", "type": "One2many",
                         "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
                    ],
                },
                {
                    "name": "uni.enrollment",
                    "fields": [
                        {"name": "student_id", "type": "Many2one",
                         "comodel_name": "uni.student"},
                        {"name": "grade_points", "type": "Float"},
                    ],
                },
            ],
        )
        issues = _validate_chain_traversal(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) >= 1

    def test_comodel_not_in_spec_warning(self):
        """dot-path where comodel not in spec -> warning (cannot validate)."""
        steps = [
            _step(
                model="uni.student",
                field="cgpa",
                depends=["enrollment_ids.grade_points"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [
                        {"name": "enrollment_ids", "type": "One2many",
                         "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
                    ],
                },
                # uni.enrollment NOT in models
            ],
        )
        issues = _validate_chain_traversal(steps, spec)
        warnings = [i for i in issues if i[0] == "warning"]
        assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# E20: Chain store=True propagation
# ---------------------------------------------------------------------------


class TestE20StoreProps:
    """E20: Stored computed field depending on non-stored upstream."""

    def test_stored_depends_on_nonstored_error(self):
        """stored computed step depending on non-stored upstream computed step -> error."""
        steps = [
            _step(field="x", source="computation"),
            _step(field="y", source="computation", depends=["x"]),
        ]
        # Mark x as NOT stored (computed but not stored)
        # We simulate this by setting store info on steps
        # The validator checks chain steps, not field dicts
        # So we need a chain where upstream step is computed but we tell
        # the validator the upstream is not stored
        chain = _chain(steps=steps)
        issues = _validate_chain_store_propagation(
            chain.steps,
            stored_overrides={"a.model.x": False, "a.model.y": True},
        )
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) >= 1
        assert "E20" in errors[0][1]

    def test_stored_depends_on_stored_no_error(self):
        """stored computed step depending on stored upstream computed step -> no error."""
        steps = [
            _step(field="x", source="computation"),
            _step(field="y", source="computation", depends=["x"]),
        ]
        chain = _chain(steps=steps)
        issues = _validate_chain_store_propagation(
            chain.steps,
            stored_overrides={"a.model.x": True, "a.model.y": True},
        )
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0

    def test_stored_depends_on_direct_input_no_error(self):
        """stored computed step depending on direct_input upstream -> no error."""
        steps = [
            _step(field="x", source="direct_input"),
            _step(field="y", source="computation", depends=["x"]),
        ]
        chain = _chain(steps=steps)
        issues = _validate_chain_store_propagation(chain.steps)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# E21: Cross-chain circular dependencies
# ---------------------------------------------------------------------------


class TestE21ChainCycles:
    """E21: Cross-chain cycle detection."""

    def test_circular_cross_dependency_error(self):
        """two chains with circular cross-dependency -> error with cycle path."""
        chain1 = _chain(
            chain_id="c1",
            steps=[
                _step(model="a.model", field="x", source="computation",
                      depends=["b_id.y"]),
            ],
        )
        chain2 = _chain(
            chain_id="c2",
            steps=[
                _step(model="b.model", field="y", source="computation",
                      depends=["a_id.x"]),
            ],
        )
        spec = _make_spec(
            models=[
                {
                    "name": "a.model",
                    "fields": [
                        {"name": "b_id", "type": "Many2one", "comodel_name": "b.model"},
                    ],
                },
                {
                    "name": "b.model",
                    "fields": [
                        {"name": "a_id", "type": "Many2one", "comodel_name": "a.model"},
                    ],
                },
            ],
        )
        issues = _validate_chain_cycles([chain1, chain2], spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) >= 1
        assert "E21" in errors[0][1]

    def test_no_circular_no_error(self):
        """two chains with no circular dependency -> no error."""
        chain1 = _chain(
            chain_id="c1",
            steps=[
                _step(model="a.model", field="x", source="direct_input"),
                _step(model="a.model", field="y", source="computation",
                      depends=["x"]),
            ],
        )
        chain2 = _chain(
            chain_id="c2",
            steps=[
                _step(model="b.model", field="z", source="direct_input"),
            ],
        )
        spec = _make_spec(
            models=[
                {"name": "a.model", "fields": []},
                {"name": "b.model", "fields": []},
            ],
        )
        issues = _validate_chain_cycles([chain1, chain2], spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0

    def test_single_chain_linear_no_error(self):
        """single chain with linear dependency -> no error."""
        chain1 = _chain(
            chain_id="c1",
            steps=[
                _step(model="a.model", field="x", source="direct_input"),
                _step(model="a.model", field="y", source="computation",
                      depends=["x"]),
                _step(model="a.model", field="z", source="computation",
                      depends=["y"]),
            ],
        )
        spec = _make_spec(models=[{"name": "a.model", "fields": []}])
        issues = _validate_chain_cycles([chain1], spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# E22: Chain comodel field existence
# ---------------------------------------------------------------------------


class TestE22FieldExistence:
    """E22: Comodel field existence checks."""

    def test_field_exists_on_comodel_no_error(self):
        """chain step depends on field that exists on comodel -> no error."""
        steps = [
            _step(
                model="uni.student",
                field="cgpa",
                depends=["enrollment_ids.grade_points"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [
                        {"name": "enrollment_ids", "type": "One2many",
                         "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
                    ],
                },
                {
                    "name": "uni.enrollment",
                    "fields": [
                        {"name": "grade_points", "type": "Float"},
                    ],
                },
            ],
        )
        issues = _validate_chain_field_existence(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) == 0

    def test_field_not_exist_on_comodel_error(self):
        """chain step depends on field that does NOT exist on comodel -> error."""
        steps = [
            _step(
                model="uni.student",
                field="cgpa",
                depends=["enrollment_ids.nonexistent_field"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [
                        {"name": "enrollment_ids", "type": "One2many",
                         "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
                    ],
                },
                {
                    "name": "uni.enrollment",
                    "fields": [
                        {"name": "grade_points", "type": "Float"},
                    ],
                },
            ],
        )
        issues = _validate_chain_field_existence(steps, spec)
        errors = [i for i in issues if i[0] == "error"]
        assert len(errors) >= 1
        assert "E22" in errors[0][1]

    def test_model_not_in_spec_warning(self):
        """chain step depends on field on model not in spec -> warning."""
        steps = [
            _step(
                model="uni.student",
                field="cgpa",
                depends=["enrollment_ids.grade_points"],
            ),
        ]
        spec = _make_spec(
            models=[
                {
                    "name": "uni.student",
                    "fields": [
                        {"name": "enrollment_ids", "type": "One2many",
                         "comodel_name": "uni.enrollment", "inverse_name": "student_id"},
                    ],
                },
                # uni.enrollment NOT in spec
            ],
        )
        issues = _validate_chain_field_existence(steps, spec)
        warnings = [i for i in issues if i[0] == "warning"]
        assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Integration: validators wired into preprocessor
# ---------------------------------------------------------------------------


class TestValidatorIntegration:
    """Validators integrated into preprocessor, running before enrichment."""

    def test_preprocessor_raises_on_cycle(self):
        """Preprocessor raises ValueError when chains have cycles."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {
                    "name": "a.model",
                    "fields": [
                        {"name": "b_id", "type": "Many2one", "comodel_name": "b.model"},
                    ],
                },
                {
                    "name": "b.model",
                    "fields": [
                        {"name": "a_id", "type": "Many2one", "comodel_name": "a.model"},
                    ],
                },
            ],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {"model": "a.model", "field": "x", "type": "Float",
                         "source": "computation", "depends": ["b_id.y"]},
                    ],
                },
                {
                    "chain_id": "c2",
                    "steps": [
                        {"model": "b.model", "field": "y", "type": "Float",
                         "source": "computation", "depends": ["a_id.x"]},
                    ],
                },
            ],
        )
        with pytest.raises(ValueError, match="E21"):
            _process_computation_chains(spec)

    def test_preprocessor_raises_on_type_error(self):
        """Preprocessor raises ValueError when aggregation type is incompatible."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {"name": "a.model", "fields": []},
            ],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {"model": "a.model", "field": "name_sum", "type": "Char",
                         "source": "aggregation", "aggregation": "sum",
                         "depends": ["rel_ids.name"]},
                    ],
                },
            ],
        )
        with pytest.raises(ValueError, match="E18"):
            _process_computation_chains(spec)

    def test_preprocessor_passes_valid_chain(self):
        """Preprocessor completes without error on valid chain."""
        from amil_utils.preprocessors.computation_chains import (
            _process_computation_chains,
        )

        spec = _make_spec(
            models=[
                {
                    "name": "a.model",
                    "fields": [
                        {"name": "rel_ids", "type": "One2many",
                         "comodel_name": "b.model", "inverse_name": "a_id"},
                    ],
                },
                {
                    "name": "b.model",
                    "fields": [
                        {"name": "a_id", "type": "Many2one", "comodel_name": "a.model"},
                        {"name": "amount", "type": "Float"},
                    ],
                },
            ],
            computation_chains=[
                {
                    "chain_id": "c1",
                    "steps": [
                        {"model": "b.model", "field": "amount", "type": "Float",
                         "source": "direct_input"},
                        {"model": "a.model", "field": "total", "type": "Float",
                         "source": "aggregation", "aggregation": "sum",
                         "depends": ["rel_ids.amount"]},
                    ],
                },
            ],
        )
        result = _process_computation_chains(spec)
        assert "_computation_chains" in result
