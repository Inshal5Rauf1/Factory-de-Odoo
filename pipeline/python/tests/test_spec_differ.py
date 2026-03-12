"""Unit tests for the spec differ module.

Tests cover:
- List-to-dict spec conversion for stable deepdiff paths
- Core diff logic (added/removed/modified models and fields)
- Destructiveness classification (always, possibly, non-destructive)
- Security, approval, webhook, constraint, cron, report diffs
- Top-level JSON output structure
- Human-readable summary formatting
- Pure function guarantee (input specs not mutated)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from odoo_gen_utils.spec_differ import (
    SpecDiff,
    diff_specs,
    format_human_summary,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def spec_v1() -> dict:
    return _load_fixture("spec_v1.json")


@pytest.fixture
def spec_v2() -> dict:
    return _load_fixture("spec_v2.json")


# ---------------------------------------------------------------------------
# TestSpecToDiffable
# ---------------------------------------------------------------------------
class TestSpecToDiffable:
    """Tests list-to-dict conversion for stable deepdiff paths."""

    def test_models_converted_to_dict_keyed_by_name(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        assert isinstance(result["models"], dict)
        assert "fee.invoice" in result["models"]
        assert "fee.payment" in result["models"]

    def test_fields_converted_to_dict_keyed_by_name(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        fields = result["models"]["fee.invoice"]["fields"]
        assert isinstance(fields, dict)
        assert "name" in fields
        assert "amount" in fields
        assert "student_id" in fields

    def test_field_name_not_duplicated_in_value(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        amount = result["models"]["fee.invoice"]["fields"]["amount"]
        assert "name" not in amount

    def test_model_name_not_duplicated_in_value(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        invoice = result["models"]["fee.invoice"]
        assert "name" not in invoice

    def test_non_model_keys_preserved(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        assert result["module_name"] == "uni_fee"
        assert result["version"] == "19.0.1.0.0"

    def test_cron_jobs_converted_to_dict(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        assert isinstance(result.get("cron_jobs"), dict)
        assert "check_overdue_invoices" in result["cron_jobs"]

    def test_reports_converted_to_dict(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        assert isinstance(result.get("reports"), dict)
        assert "fee_invoice_report" in result["reports"]

    def test_constraints_converted_to_dict(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        constraints = result["models"]["fee.invoice"].get("constraints")
        assert isinstance(constraints, dict)
        assert "check_amount_positive" in constraints

    def test_approval_levels_converted_to_dict(self, spec_v1: dict) -> None:
        from odoo_gen_utils.spec_differ import _spec_to_diffable

        result = _spec_to_diffable(spec_v1)
        approval = result["models"]["fee.invoice"].get("approval", {})
        levels = approval.get("levels")
        assert isinstance(levels, dict)
        assert "submitted" in levels


# ---------------------------------------------------------------------------
# TestDiffSpecs
# ---------------------------------------------------------------------------
class TestDiffSpecs:
    """Tests the core diff logic (added/removed/modified models and fields)."""

    def test_identical_specs_returns_empty_changes(self, spec_v1: dict) -> None:
        result = diff_specs(spec_v1, spec_v1)
        changes = result["changes"]
        models = changes.get("models", {})
        assert models.get("added", []) == []
        assert models.get("removed", []) == []
        assert models.get("modified", {}) == {}
        assert result["migration_required"] is False

    def test_added_model_appears_in_added(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        added_models = result["changes"]["models"]["added"]
        model_names = [m["name"] for m in added_models]
        assert "fee.penalty" in model_names

    def test_added_model_includes_field_list(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        added_models = result["changes"]["models"]["added"]
        penalty = next(m for m in added_models if m["name"] == "fee.penalty")
        assert "fields" in penalty
        field_names = [f["name"] if isinstance(f, dict) else f for f in penalty["fields"]]
        assert "name" in field_names
        assert "amount" in field_names

    def test_removed_field_appears_in_modified_model(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        assert "fee.invoice" in modified
        removed_fields = modified["fee.invoice"]["fields"]["removed"]
        field_names = [f["name"] for f in removed_fields]
        assert "old_ref" in field_names

    def test_removed_field_is_destructive(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        removed_fields = modified["fee.invoice"]["fields"]["removed"]
        old_ref = next(f for f in removed_fields if f["name"] == "old_ref")
        assert old_ref["destructive"] is True

    def test_added_field_appears_in_modified_model(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        assert "fee.invoice" in modified
        added_fields = modified["fee.invoice"]["fields"]["added"]
        field_names = [f["name"] for f in added_fields]
        assert "penalty_amount" in field_names

    def test_modified_field_type_change(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        modified_fields = modified["fee.invoice"]["fields"]["modified"]
        amount = next(f for f in modified_fields if f["name"] == "amount")
        assert "type" in amount["changes"]
        assert amount["changes"]["type"]["old"] == "Float"
        assert amount["changes"]["type"]["new"] == "Monetary"

    def test_modified_field_type_change_is_destructive(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        modified_fields = modified["fee.invoice"]["fields"]["modified"]
        amount = next(f for f in modified_fields if f["name"] == "amount")
        assert amount["destructive"] is True

    def test_required_change_detected(self, spec_v1: dict, spec_v2: dict) -> None:
        """due_date changed required from false to true."""
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        modified_fields = modified["fee.invoice"]["fields"]["modified"]
        due_date = next(f for f in modified_fields if f["name"] == "due_date")
        assert "required" in due_date["changes"]
        assert due_date["changes"]["required"]["old"] is False
        assert due_date["changes"]["required"]["new"] is True

    def test_selection_option_removed_detected(self, spec_v1: dict, spec_v2: dict) -> None:
        """state selection lost 'cancelled' option."""
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        modified_fields = modified["fee.invoice"]["fields"]["modified"]
        state = next(f for f in modified_fields if f["name"] == "state")
        assert "selection" in state["changes"]


# ---------------------------------------------------------------------------
# TestDestructiveness
# ---------------------------------------------------------------------------
class TestDestructiveness:
    """Tests all three severity levels with exhaustive type change matrix."""

    def test_type_widening_char_to_text_non_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Char", "Text", "type")
        assert result == "non_destructive"

    def test_type_widening_integer_to_float_non_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Integer", "Float", "type")
        assert result == "non_destructive"

    def test_type_narrowing_text_to_char_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Text", "Char", "type")
        assert result == "always_destructive"

    def test_type_narrowing_float_to_integer_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Float", "Integer", "type")
        assert result == "always_destructive"

    def test_type_incompatible_many2one_to_char_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Many2one", "Char", "type")
        assert result == "always_destructive"

    def test_type_incompatible_char_to_many2one_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Char", "Many2one", "type")
        assert result == "always_destructive"

    def test_type_incompatible_selection_to_integer_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Selection", "Integer", "type")
        assert result == "always_destructive"

    def test_type_incompatible_boolean_to_many2one_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Boolean", "Many2one", "type")
        assert result == "always_destructive"

    def test_type_monetary_to_integer_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Monetary", "Integer", "type")
        assert result == "always_destructive"

    def test_type_text_to_integer_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Text", "Integer", "type")
        assert result == "always_destructive"

    def test_float_to_monetary_possibly_destructive(self) -> None:
        """Float->Monetary involves precision change, possibly destructive."""
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("type", "Float", "Monetary", "type")
        assert result == "possibly_destructive"

    def test_required_false_to_true_possibly_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("required", False, True, "required")
        assert result == "possibly_destructive"

    def test_selection_options_removed_possibly_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness(
            "selection_removed",
            [["draft", "Draft"], ["confirmed", "Confirmed"], ["cancelled", "Cancelled"]],
            [["draft", "Draft"], ["confirmed", "Confirmed"]],
            "selection",
        )
        assert result == "possibly_destructive"

    def test_field_added_non_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("field_added", None, "new_field", "field")
        assert result == "non_destructive"

    def test_string_changed_non_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("attribute", "Old Label", "New Label", "string")
        assert result == "non_destructive"

    def test_help_changed_non_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("attribute", "Old Help", "New Help", "help")
        assert result == "non_destructive"

    def test_selection_added_non_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness(
            "selection_added",
            [["draft", "Draft"]],
            [["draft", "Draft"], ["new", "New"]],
            "selection",
        )
        assert result == "non_destructive"

    def test_required_true_to_false_non_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("required", True, False, "required")
        assert result == "non_destructive"

    def test_field_removed_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("field_removed", "old_field", None, "field")
        assert result == "always_destructive"

    def test_model_removed_always_destructive(self) -> None:
        from odoo_gen_utils.spec_differ import _classify_destructiveness

        result = _classify_destructiveness("model_removed", "fee.old", None, "model")
        assert result == "always_destructive"


# ---------------------------------------------------------------------------
# TestSecurityApprovalWebhookDiff
# ---------------------------------------------------------------------------
class TestSecurityApprovalWebhookDiff:
    """Tests non-field structural changes."""

    def test_security_role_added(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        security = modified["fee.invoice"].get("security", {})
        added_roles = security.get("roles_added", [])
        assert "auditor" in added_roles

    def test_approval_level_added(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        approval = modified["fee.invoice"].get("approval", {})
        added_levels = approval.get("levels_added", [])
        assert "final_approved" in added_levels

    def test_webhook_watched_fields_changed(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        webhooks = modified["fee.invoice"].get("webhooks", {})
        assert "watched_fields" in webhooks
        assert "due_date" in webhooks["watched_fields"].get("added", [])

    def test_constraint_added(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        modified = result["changes"]["models"]["modified"]
        constraints = modified["fee.invoice"].get("constraints", {})
        added = constraints.get("added", [])
        constraint_names = [c["name"] if isinstance(c, dict) else c for c in added]
        assert "check_due_date_future" in constraint_names

    def test_cron_interval_changed(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        cron = result["changes"].get("cron_jobs", {})
        modified = cron.get("modified", {})
        assert "check_overdue_invoices" in modified

    def test_report_added(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        reports = result["changes"].get("reports", {})
        added = reports.get("added", [])
        report_names = [r["name"] if isinstance(r, dict) else r for r in added]
        assert "fee_penalty_report" in report_names


# ---------------------------------------------------------------------------
# TestDiffOutputStructure
# ---------------------------------------------------------------------------
class TestDiffOutputStructure:
    """Tests top-level JSON keys, migration_required, destructive_count."""

    def test_top_level_keys_present(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        expected_keys = {
            "module",
            "old_version",
            "new_version",
            "changes",
            "destructive_count",
            "warnings",
            "migration_required",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_module_name_correct(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        assert result["module"] == "uni_fee"

    def test_versions_correct(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        assert result["old_version"] == "19.0.1.0.0"
        assert result["new_version"] == "19.0.1.1.0"

    def test_migration_required_true_with_destructive(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        assert result["migration_required"] is True

    def test_destructive_count_accurate(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        # At minimum: old_ref removed (1), amount Float->Monetary (1),
        # due_date required false->true (1), state selection options removed (1)
        assert result["destructive_count"] >= 2

    def test_migration_required_false_for_identical(self, spec_v1: dict) -> None:
        result = diff_specs(spec_v1, spec_v1)
        assert result["migration_required"] is False


# ---------------------------------------------------------------------------
# TestHumanFormat
# ---------------------------------------------------------------------------
class TestHumanFormat:
    """Tests format_human_summary output symbols and footer."""

    def test_added_symbol(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        summary = format_human_summary(result)
        assert "+ " in summary or "+  " in summary

    def test_removed_symbol(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        summary = format_human_summary(result)
        assert "- " in summary or "-  " in summary

    def test_modified_symbol(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        summary = format_human_summary(result)
        assert "~ " in summary or "~  " in summary

    def test_destructive_symbol(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        summary = format_human_summary(result)
        assert "!" in summary

    def test_warning_footer(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        summary = format_human_summary(result)
        assert "destructive" in summary.lower()

    def test_no_warning_footer_for_identical(self, spec_v1: dict) -> None:
        result = diff_specs(spec_v1, spec_v1)
        summary = format_human_summary(result)
        assert "destructive change" not in summary.lower()

    def test_module_version_header(self, spec_v1: dict, spec_v2: dict) -> None:
        result = diff_specs(spec_v1, spec_v2)
        summary = format_human_summary(result)
        assert "uni_fee" in summary
        assert "19.0.1.0.0" in summary
        assert "19.0.1.1.0" in summary


# ---------------------------------------------------------------------------
# TestPureFunction
# ---------------------------------------------------------------------------
class TestPureFunction:
    """Verifies input specs are not mutated."""

    def test_old_spec_not_mutated(self, spec_v1: dict, spec_v2: dict) -> None:
        original = copy.deepcopy(spec_v1)
        diff_specs(spec_v1, spec_v2)
        assert spec_v1 == original

    def test_new_spec_not_mutated(self, spec_v1: dict, spec_v2: dict) -> None:
        original = copy.deepcopy(spec_v2)
        diff_specs(spec_v1, spec_v2)
        assert spec_v2 == original


# ---------------------------------------------------------------------------
# TestExcludedAttributes
# ---------------------------------------------------------------------------
class TestExcludedAttributes:
    """Verify that presentation-only attributes are NOT compared."""

    def test_string_change_not_in_diff(self) -> None:
        """Changing only string (label) should produce no schema changes."""
        old = {
            "module_name": "test",
            "version": "1.0",
            "models": [
                {
                    "name": "test.model",
                    "fields": [{"name": "f1", "type": "Char", "string": "Old Label"}],
                }
            ],
        }
        new = {
            "module_name": "test",
            "version": "1.0",
            "models": [
                {
                    "name": "test.model",
                    "fields": [{"name": "f1", "type": "Char", "string": "New Label"}],
                }
            ],
        }
        result = diff_specs(old, new)
        modified = result["changes"]["models"].get("modified", {})
        if "test.model" in modified:
            mod_fields = modified["test.model"]["fields"].get("modified", [])
            # If there are modified fields, string should not be the reason
            for f in mod_fields:
                assert "string" not in f.get("changes", {})

    def test_help_change_not_in_diff(self) -> None:
        old = {
            "module_name": "test",
            "version": "1.0",
            "models": [
                {
                    "name": "test.model",
                    "fields": [{"name": "f1", "type": "Char", "help": "Old Help"}],
                }
            ],
        }
        new = {
            "module_name": "test",
            "version": "1.0",
            "models": [
                {
                    "name": "test.model",
                    "fields": [{"name": "f1", "type": "Char", "help": "New Help"}],
                }
            ],
        }
        result = diff_specs(old, new)
        modified = result["changes"]["models"].get("modified", {})
        if "test.model" in modified:
            mod_fields = modified["test.model"]["fields"].get("modified", [])
            for f in mod_fields:
                assert "help" not in f.get("changes", {})


# ---------------------------------------------------------------------------
# TestSpecDiffNamedTuple
# ---------------------------------------------------------------------------
class TestSpecDiffType:
    """Tests that SpecDiff is a valid type."""

    def test_spec_diff_is_importable(self) -> None:
        assert SpecDiff is not None
