"""Tests for chain_context on StubContext and report serialization.

Covers:
- StubContext backward compatibility (chain_context=None default)
- StubContext with chain_context populated
- _build_chain_context for various source/aggregation types
- build_stub_context integration with chain_context
- _stub_to_dict conditional inclusion/omission of chain_context
- End-to-end CGPA chain flow
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from amil_utils.logic_writer.context_builder import (
    StubContext,
    _build_chain_context,
    build_stub_context,
)
from amil_utils.logic_writer.report import _stub_to_dict
from amil_utils.logic_writer.stub_detector import StubInfo
from amil_utils.preprocessors.computation_chains import _process_computation_chains


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_stub(
    method_name: str = "_compute_cgpa",
    model_name: str = "uni.student",
    target_fields: list[str] | None = None,
    decorator: str = '@api.depends("enrollment_ids.weighted_grade_points")',
) -> StubInfo:
    return StubInfo(
        file="models/student.py",
        line=10,
        class_name="UniStudent",
        model_name=model_name,
        method_name=method_name,
        decorator=decorator,
        target_fields=target_fields or ["cgpa"],
    )


def _make_chain_meta(
    *,
    chain_id: str = "cgpa_chain",
    chain_description: str = "Grade -> Grade Points -> CGPA",
    position_in_chain: int = 3,
    total_steps: int = 4,
    source: str = "aggregation",
    aggregation: str | None = "weighted_average",
    lookup_table: dict | None = None,
    upstream_steps: list[dict] | None = None,
    downstream_steps: list[dict] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "chain_id": chain_id,
        "chain_description": chain_description,
        "position_in_chain": position_in_chain,
        "total_steps": total_steps,
        "source": source,
        "upstream_steps": upstream_steps or [],
        "downstream_steps": downstream_steps or [],
    }
    if aggregation is not None:
        meta["aggregation"] = aggregation
    if lookup_table is not None:
        meta["lookup_table"] = lookup_table
    return meta


# ---------------------------------------------------------------------------
# StubContext backward compatibility
# ---------------------------------------------------------------------------


class TestStubContextChainField:
    """chain_context field on StubContext."""

    def test_default_is_none(self):
        ctx = StubContext(
            model_fields={},
            related_fields={},
            business_rules=[],
            registry_source=None,
        )
        assert ctx.chain_context is None

    def test_accepts_dict(self):
        chain_ctx = {"chain_id": "test", "position_in_chain": 0}
        ctx = StubContext(
            model_fields={},
            related_fields={},
            business_rules=[],
            registry_source=None,
            chain_context=chain_ctx,
        )
        assert ctx.chain_context == chain_ctx

    def test_frozen_dataclass(self):
        ctx = StubContext(
            model_fields={},
            related_fields={},
            business_rules=[],
            registry_source=None,
            chain_context={"chain_id": "x"},
        )
        with pytest.raises(AttributeError):
            ctx.chain_context = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _build_chain_context unit tests
# ---------------------------------------------------------------------------


class TestBuildChainContext:
    """_build_chain_context returns correct dicts or None."""

    def test_returns_none_for_non_compute(self):
        stub = _make_stub(method_name="_check_something", decorator="@api.constrains('x')")
        result = _build_chain_context(stub, {}, {})
        assert result is None

    def test_returns_none_when_no_chain_meta(self):
        stub = _make_stub()
        model_fields = {"cgpa": {"type": "Float"}}
        result = _build_chain_context(stub, model_fields, {})
        assert result is None

    def test_weighted_average_aggregation(self):
        stub = _make_stub(
            decorator='@api.depends("enrollment_ids.weighted_grade_points", "enrollment_ids.course_id.credit_hours")',
        )
        chain_meta = _make_chain_meta(
            source="aggregation",
            aggregation="weighted_average",
            upstream_steps=[
                {"model": "exam.result", "field": "grade", "source": "direct_input", "type": "Selection"},
                {"model": "exam.result", "field": "grade_point", "source": "lookup", "type": "Float"},
                {"model": "uni.enrollment", "field": "weighted_grade_points", "source": "computation", "type": "Float"},
            ],
        )
        model_fields = {
            "cgpa": {"type": "Float", "_chain_meta": chain_meta},
            "enrollment_ids": {"type": "One2many", "comodel_name": "uni.enrollment"},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert result["chain_id"] == "cgpa_chain"
        assert result["position_in_chain"] == 3
        assert result["total_steps"] == 4
        assert result["this_step"]["source"] == "aggregation"
        assert result["this_step"]["aggregation"] == "weighted_average"
        assert len(result["upstream_steps"]) == 3
        assert result["downstream_steps"] == []
        assert "weighted_grade_points" in result["computation_pattern"]
        assert "credit_hours" in result["computation_pattern"]

    def test_sum_aggregation(self):
        stub = _make_stub(
            method_name="_compute_total",
            target_fields=["total"],
            decorator='@api.depends("line_ids.amount")',
        )
        chain_meta = _make_chain_meta(
            source="aggregation",
            aggregation="sum",
            position_in_chain=1,
            total_steps=2,
        )
        model_fields = {
            "total": {"type": "Float", "_chain_meta": chain_meta},
            "line_ids": {"type": "One2many", "comodel_name": "sale.order.line"},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert "sum(" in result["computation_pattern"]
        assert "mapped" in result["computation_pattern"]

    def test_lookup_source(self):
        stub = _make_stub(
            method_name="_compute_grade_point",
            model_name="exam.result",
            target_fields=["grade_point"],
            decorator='@api.depends("grade")',
        )
        chain_meta = _make_chain_meta(
            source="lookup",
            aggregation=None,
            position_in_chain=1,
            total_steps=4,
            lookup_table={"A": 4.0, "B": 3.0},
        )
        model_fields = {
            "grade_point": {"type": "Float", "_chain_meta": chain_meta},
            "grade": {"type": "Selection"},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert "GRADE_MAP" in result["computation_pattern"] or ".get(" in result["computation_pattern"]
        assert result["this_step"]["source"] == "lookup"
        assert result["this_step"]["lookup_table"] is not None

    def test_count_aggregation(self):
        stub = _make_stub(
            method_name="_compute_count",
            target_fields=["count"],
            decorator='@api.depends("line_ids")',
        )
        chain_meta = _make_chain_meta(
            source="aggregation", aggregation="count",
            position_in_chain=1, total_steps=2,
        )
        model_fields = {
            "count": {"type": "Integer", "_chain_meta": chain_meta},
            "line_ids": {"type": "One2many", "comodel_name": "sale.order.line"},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert "len(" in result["computation_pattern"] or "filtered" in result["computation_pattern"]

    def test_min_aggregation(self):
        stub = _make_stub(
            method_name="_compute_min_score",
            target_fields=["min_score"],
            decorator='@api.depends("line_ids.score")',
        )
        chain_meta = _make_chain_meta(
            source="aggregation", aggregation="min",
            position_in_chain=1, total_steps=2,
        )
        model_fields = {
            "min_score": {"type": "Float", "_chain_meta": chain_meta},
            "line_ids": {"type": "One2many"},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert "min(" in result["computation_pattern"]

    def test_max_aggregation(self):
        stub = _make_stub(
            method_name="_compute_max_score",
            target_fields=["max_score"],
            decorator='@api.depends("line_ids.score")',
        )
        chain_meta = _make_chain_meta(
            source="aggregation", aggregation="max",
            position_in_chain=1, total_steps=2,
        )
        model_fields = {
            "max_score": {"type": "Float", "_chain_meta": chain_meta},
            "line_ids": {"type": "One2many"},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert "max(" in result["computation_pattern"]

    def test_computation_source_empty_pattern(self):
        stub = _make_stub(
            method_name="_compute_weighted_grade_points",
            model_name="uni.enrollment",
            target_fields=["weighted_grade_points"],
            decorator='@api.depends("result_ids.grade_point", "course_id.credit_hours")',
        )
        chain_meta = _make_chain_meta(
            source="computation", aggregation=None,
            position_in_chain=2, total_steps=4,
        )
        model_fields = {
            "weighted_grade_points": {"type": "Float", "_chain_meta": chain_meta},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert result["computation_pattern"] == ""

    def test_direct_input_empty_pattern(self):
        stub = _make_stub(
            method_name="_compute_grade",
            model_name="exam.result",
            target_fields=["grade"],
            decorator="",
        )
        chain_meta = _make_chain_meta(
            source="direct_input", aggregation=None,
            position_in_chain=0, total_steps=4,
        )
        model_fields = {
            "grade": {"type": "Selection", "_chain_meta": chain_meta},
        }
        result = _build_chain_context(stub, model_fields, {})
        assert result is not None
        assert result["computation_pattern"] == ""


# ---------------------------------------------------------------------------
# build_stub_context integration
# ---------------------------------------------------------------------------


class TestBuildStubContextIntegration:
    """build_stub_context wires chain_context correctly."""

    def test_chain_context_populated_for_chain_field(self):
        spec = {
            "models": [
                {
                    "name": "uni.student",
                    "description": "Student",
                    "fields": [
                        {
                            "name": "cgpa",
                            "type": "Float",
                            "compute": "_compute_cgpa",
                            "depends": ["enrollment_ids.weighted_grade_points"],
                            "store": True,
                            "_chain_meta": _make_chain_meta(),
                        },
                        {
                            "name": "enrollment_ids",
                            "type": "One2many",
                            "comodel_name": "uni.enrollment",
                            "inverse_name": "student_id",
                        },
                    ],
                }
            ]
        }
        stub = _make_stub()
        ctx = build_stub_context(stub, spec)
        assert ctx.chain_context is not None
        assert ctx.chain_context["chain_id"] == "cgpa_chain"

    def test_chain_context_none_for_non_chain_field(self):
        spec = {
            "models": [
                {
                    "name": "sale.order",
                    "description": "Sale Order",
                    "fields": [
                        {"name": "total", "type": "Float", "compute": "_compute_total"},
                    ],
                }
            ]
        }
        stub = _make_stub(
            method_name="_compute_total",
            model_name="sale.order",
            target_fields=["total"],
        )
        ctx = build_stub_context(stub, spec)
        assert ctx.chain_context is None


# ---------------------------------------------------------------------------
# _stub_to_dict serialization
# ---------------------------------------------------------------------------


class TestStubToDictChainContext:
    """_stub_to_dict includes/omits chain_context correctly."""

    def test_includes_chain_context_when_present(self):
        stub = _make_stub()
        ctx = StubContext(
            model_fields={},
            related_fields={},
            business_rules=[],
            registry_source=None,
            method_type="compute",
            chain_context={"chain_id": "test_chain", "position_in_chain": 0},
        )
        result = _stub_to_dict(stub, ctx, "quality")
        assert "chain_context" in result
        assert result["chain_context"]["chain_id"] == "test_chain"

    def test_omits_chain_context_when_none(self):
        stub = _make_stub()
        ctx = StubContext(
            model_fields={},
            related_fields={},
            business_rules=[],
            registry_source=None,
            method_type="compute",
        )
        result = _stub_to_dict(stub, ctx, "quality")
        assert "chain_context" not in result

    def test_chain_context_serialized_in_report_entry(self):
        stub = _make_stub()
        chain_ctx = {
            "chain_id": "cgpa_chain",
            "position_in_chain": 3,
            "total_steps": 4,
            "computation_pattern": "sum(r.X * r.Y) / sum(r.Y)",
        }
        ctx = StubContext(
            model_fields={"cgpa": {"type": "Float"}},
            related_fields={},
            business_rules=[],
            registry_source=None,
            method_type="compute",
            chain_context=chain_ctx,
        )
        result = _stub_to_dict(stub, ctx, "quality")
        # Verify JSON-serializable
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["chain_context"]["chain_id"] == "cgpa_chain"
        assert parsed["chain_context"]["total_steps"] == 4


# ---------------------------------------------------------------------------
# End-to-end: spec -> preprocessor -> context builder -> report
# ---------------------------------------------------------------------------


class TestEndToEndChainFlow:
    """Full CGPA chain spec -> preprocessor -> context builder -> chain_context."""

    @pytest.fixture()
    def cgpa_spec(self) -> dict[str, Any]:
        with open(FIXTURES_DIR / "cgpa_chain_spec.json") as f:
            return json.load(f)

    @pytest.fixture()
    def enriched_spec(self, cgpa_spec: dict[str, Any]) -> dict[str, Any]:
        return _process_computation_chains(cgpa_spec)

    def test_cgpa_step_chain_context(self, enriched_spec: dict[str, Any]):
        """CGPA field (step 3): weighted_average aggregation."""
        stub = _make_stub(
            method_name="_compute_cgpa",
            model_name="uni.student",
            target_fields=["cgpa"],
            decorator='@api.depends("enrollment_ids.weighted_grade_points", "enrollment_ids.course_id.credit_hours")',
        )
        ctx = build_stub_context(stub, enriched_spec)
        assert ctx.chain_context is not None
        assert ctx.chain_context["chain_id"] == "cgpa_chain"
        assert ctx.chain_context["position_in_chain"] == 3
        assert ctx.chain_context["total_steps"] == 4
        assert ctx.chain_context["this_step"]["source"] == "aggregation"
        assert ctx.chain_context["this_step"]["aggregation"] == "weighted_average"
        assert len(ctx.chain_context["upstream_steps"]) == 3
        assert ctx.chain_context["downstream_steps"] == []

    def test_grade_point_step_chain_context(self, enriched_spec: dict[str, Any]):
        """Grade point field (step 1): lookup source with lookup_table."""
        stub = _make_stub(
            method_name="_compute_grade_point",
            model_name="exam.result",
            target_fields=["grade_point"],
            decorator='@api.depends("grade")',
        )
        ctx = build_stub_context(stub, enriched_spec)
        assert ctx.chain_context is not None
        assert ctx.chain_context["chain_id"] == "cgpa_chain"
        assert ctx.chain_context["position_in_chain"] == 1
        assert ctx.chain_context["this_step"]["source"] == "lookup"
        assert ctx.chain_context["this_step"]["lookup_table"] is not None
        assert "GRADE_MAP" in ctx.chain_context["computation_pattern"] or ".get(" in ctx.chain_context["computation_pattern"]

    def test_weighted_grade_points_step_chain_context(self, enriched_spec: dict[str, Any]):
        """Weighted grade points (step 2): computation source."""
        stub = _make_stub(
            method_name="_compute_weighted_grade_points",
            model_name="uni.enrollment",
            target_fields=["weighted_grade_points"],
            decorator='@api.depends("result_ids.grade_point", "course_id.credit_hours")',
        )
        ctx = build_stub_context(stub, enriched_spec)
        assert ctx.chain_context is not None
        assert ctx.chain_context["chain_id"] == "cgpa_chain"
        assert ctx.chain_context["position_in_chain"] == 2
        assert ctx.chain_context["this_step"]["source"] == "computation"
        assert ctx.chain_context["computation_pattern"] == ""

    def test_direct_input_no_stub_expected(self, enriched_spec: dict[str, Any]):
        """Grade field (step 0): direct_input -- not computed, but chain_context still attached."""
        # direct_input fields don't have _compute_ stubs normally,
        # but if someone creates one, chain_context still works
        stub = _make_stub(
            method_name="_compute_grade",
            model_name="exam.result",
            target_fields=["grade"],
            decorator="",
        )
        ctx = build_stub_context(stub, enriched_spec)
        # grade has _chain_meta with source=direct_input
        assert ctx.chain_context is not None
        assert ctx.chain_context["this_step"]["source"] == "direct_input"
        assert ctx.chain_context["computation_pattern"] == ""

    def test_non_chain_compute_stub_has_no_chain_context(self, enriched_spec: dict[str, Any]):
        """A compute stub on a non-chain field has chain_context=None."""
        stub = _make_stub(
            method_name="_compute_name",
            model_name="uni.student",
            target_fields=["name"],
            decorator='@api.depends("first_name", "last_name")',
        )
        ctx = build_stub_context(stub, enriched_spec)
        assert ctx.chain_context is None

    def test_cgpa_computation_pattern_has_actual_field_names(self, enriched_spec: dict[str, Any]):
        """Weighted average computation_pattern contains actual field names."""
        stub = _make_stub(
            method_name="_compute_cgpa",
            model_name="uni.student",
            target_fields=["cgpa"],
            decorator='@api.depends("enrollment_ids.weighted_grade_points", "enrollment_ids.course_id.credit_hours")',
        )
        ctx = build_stub_context(stub, enriched_spec)
        assert ctx.chain_context is not None
        pattern = ctx.chain_context["computation_pattern"]
        assert "weighted_grade_points" in pattern
        assert "credit_hours" in pattern

    def test_stub_report_entry_includes_chain_context(self, enriched_spec: dict[str, Any]):
        """_stub_to_dict includes chain_context in JSON entry for chain stub."""
        stub = _make_stub()
        ctx = build_stub_context(stub, enriched_spec)
        result = _stub_to_dict(stub, ctx, "quality")
        assert "chain_context" in result
        # Verify serializable
        json.dumps(result)

    def test_stub_report_entry_omits_chain_context_for_non_chain(self, enriched_spec: dict[str, Any]):
        """_stub_to_dict omits chain_context for non-chain compute stub."""
        stub = _make_stub(
            method_name="_compute_name",
            model_name="uni.student",
            target_fields=["name"],
            decorator='@api.depends("first_name")',
        )
        ctx = build_stub_context(stub, enriched_spec)
        result = _stub_to_dict(stub, ctx, "budget")
        assert "chain_context" not in result
