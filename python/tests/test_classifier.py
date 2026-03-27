"""Tests for logic_writer.classifier -- deterministic complexity routing."""

from __future__ import annotations

import pytest

from amil_utils.logic_writer.stub_detector import StubInfo
from amil_utils.logic_writer.classifier import classify_complexity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub(
    *,
    method_name: str = "_compute_total",
    decorator: str = '@api.depends("amount")',
    target_fields: list[str] | None = None,
) -> StubInfo:
    """Create a minimal StubInfo for classification testing."""
    return StubInfo(
        file="models/test.py",
        line=10,
        class_name="TestModel",
        model_name="test.model",
        method_name=method_name,
        decorator=decorator,
        target_fields=target_fields or [],
    )


# ---------------------------------------------------------------------------
# Rule 1: Cross-model depends -> quality
# ---------------------------------------------------------------------------


class TestCrossModelDepends:
    """Cross-model depends (dot notation in @api.depends) -> quality."""

    def test_dot_in_depends_triggers_quality(self) -> None:
        stub = _make_stub(decorator='@api.depends("partner_id.name")')
        assert classify_complexity(stub, []) == "quality"

    def test_multiple_dots_in_depends(self) -> None:
        stub = _make_stub(
            decorator='@api.depends("order_id.partner_id.name")'
        )
        assert classify_complexity(stub, []) == "quality"

    def test_depends_no_dot_not_triggered(self) -> None:
        """depends with no dot should NOT trigger cross-model rule."""
        stub = _make_stub(decorator='@api.depends("amount")')
        assert classify_complexity(stub, []) == "budget"

    def test_dot_without_depends_not_triggered(self) -> None:
        """A dot in a non-depends decorator should not trigger quality."""
        stub = _make_stub(decorator='@api.onchange("field.name")')
        # onchange does not have "depends" in it, so cross-model rule doesn't apply
        assert classify_complexity(stub, []) == "budget"


# ---------------------------------------------------------------------------
# Rule 2: Multiple target fields -> quality
# ---------------------------------------------------------------------------


class TestMultipleTargetFields:
    """Multiple target fields -> quality."""

    def test_two_target_fields_triggers_quality(self) -> None:
        stub = _make_stub(target_fields=["amount_total", "amount_tax"])
        assert classify_complexity(stub, []) == "quality"

    def test_three_target_fields_triggers_quality(self) -> None:
        stub = _make_stub(
            target_fields=["amount_total", "amount_tax", "amount_untaxed"]
        )
        assert classify_complexity(stub, []) == "quality"

    def test_single_target_field_not_triggered(self) -> None:
        stub = _make_stub(target_fields=["total"])
        assert classify_complexity(stub, []) == "budget"

    def test_empty_target_fields_not_triggered(self) -> None:
        stub = _make_stub(target_fields=[])
        assert classify_complexity(stub, []) == "budget"


# ---------------------------------------------------------------------------
# Rule 3: Conditional business rules -> quality
# ---------------------------------------------------------------------------


class TestConditionalBusinessRules:
    """Conditional business rules with keywords -> quality."""

    @pytest.mark.parametrize(
        "keyword",
        ["if", "when", "unless", "except", "only", "between"],
    )
    def test_conditional_keyword_triggers_quality(self, keyword: str) -> None:
        rules = [f"Total is computed {keyword} discount is applied"]
        stub = _make_stub()
        assert classify_complexity(stub, rules) == "quality"

    def test_keyword_case_insensitive(self) -> None:
        """Keywords should match case-insensitively."""
        rules = ["IF the order is confirmed THEN calculate"]
        stub = _make_stub()
        assert classify_complexity(stub, rules) == "quality"

    def test_no_conditional_keywords(self) -> None:
        rules = ["Total is computed from amount and discount"]
        stub = _make_stub()
        assert classify_complexity(stub, rules) == "budget"

    def test_empty_rules(self) -> None:
        stub = _make_stub()
        assert classify_complexity(stub, []) == "budget"


# ---------------------------------------------------------------------------
# Rule 4: create/write overrides -> quality
# ---------------------------------------------------------------------------


class TestCreateWriteOverrides:
    """create/write method names -> quality."""

    def test_create_method_triggers_quality(self) -> None:
        stub = _make_stub(method_name="create", decorator="@api.model")
        assert classify_complexity(stub, []) == "quality"

    def test_write_method_triggers_quality(self) -> None:
        stub = _make_stub(method_name="write", decorator="")
        assert classify_complexity(stub, []) == "quality"


# ---------------------------------------------------------------------------
# Rule 5: action_* / _cron_* methods -> quality
# ---------------------------------------------------------------------------


class TestActionCronMethods:
    """action_* and _cron_* method patterns -> quality."""

    def test_action_prefix_triggers_quality(self) -> None:
        stub = _make_stub(method_name="action_confirm", decorator="")
        assert classify_complexity(stub, []) == "quality"

    def test_cron_prefix_triggers_quality(self) -> None:
        stub = _make_stub(method_name="_cron_expire_orders", decorator="")
        assert classify_complexity(stub, []) == "quality"

    def test_method_containing_action_not_triggered(self) -> None:
        """Only action_ prefix, not substring."""
        stub = _make_stub(method_name="_compute_action_count", decorator="")
        assert classify_complexity(stub, []) == "budget"


# ---------------------------------------------------------------------------
# Rule 6: Default -> budget
# ---------------------------------------------------------------------------


class TestDefaultBudget:
    """Everything else -> budget."""

    def test_simple_single_field_compute(self) -> None:
        stub = _make_stub(
            method_name="_compute_total",
            decorator='@api.depends("amount")',
            target_fields=["total"],
        )
        assert classify_complexity(stub, []) == "budget"

    def test_constraint_no_quality_triggers(self) -> None:
        stub = _make_stub(
            method_name="_check_amount",
            decorator='@api.constrains("amount")',
            target_fields=[],
        )
        assert classify_complexity(stub, []) == "budget"


# ---------------------------------------------------------------------------
# Priority / combined rules
# ---------------------------------------------------------------------------


class TestPriority:
    """Verify that quality triggers win even with budget defaults."""

    def test_cross_model_wins_over_simple_method(self) -> None:
        """Cross-model depends should classify as quality even for simple method names."""
        stub = _make_stub(
            method_name="_compute_total",
            decorator='@api.depends("partner_id.discount")',
            target_fields=["total"],
        )
        assert classify_complexity(stub, []) == "quality"

    def test_multiple_quality_triggers_still_quality(self) -> None:
        """Multiple quality triggers should still return 'quality' (not error)."""
        stub = _make_stub(
            method_name="create",
            decorator='@api.depends("partner_id.name")',
            target_fields=["name", "display_name"],
        )
        rules = ["If confirmed then apply discount"]
        assert classify_complexity(stub, rules) == "quality"
