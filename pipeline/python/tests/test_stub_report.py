"""Tests for logic_writer.report -- JSON stub report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from amil_utils.logic_writer.report import StubReport, generate_stub_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_py(tmp_path: Path, rel: str, source: str) -> Path:
    """Write *source* to *tmp_path / rel* and return the file path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return p


def _minimal_spec(module_name: str = "test_module") -> dict[str, Any]:
    """Build a minimal spec dict matching a simple model."""
    return {
        "module_name": module_name,
        "models": [
            {
                "name": "test.order",
                "fields": [
                    {
                        "name": "amount",
                        "type": "Float",
                        "string": "Amount",
                    },
                    {
                        "name": "total",
                        "type": "Float",
                        "string": "Total",
                        "compute": "_compute_total",
                        "depends": ["amount"],
                    },
                    {
                        "name": "partner_id",
                        "type": "Many2one",
                        "comodel_name": "res.partner",
                        "string": "Partner",
                    },
                ],
            },
        ],
    }


_SIMPLE_COMPUTE_PY = '''\
from odoo import models, fields, api


class TestOrder(models.Model):
    _name = "test.order"
    _description = "Test Order"

    amount = fields.Float(string="Amount")
    total = fields.Float(string="Total", compute="_compute_total")

    @api.depends("amount")
    def _compute_total(self):
        for rec in self:
            rec.total = 0.0
'''

_QUALITY_STUBS_PY = '''\
from odoo import models, fields, api


class TestOrder(models.Model):
    _name = "test.order"
    _description = "Test Order"

    amount = fields.Float(string="Amount")
    total = fields.Float(string="Total", compute="_compute_total")
    tax = fields.Float(string="Tax", compute="_compute_total")
    partner_id = fields.Many2one("res.partner", string="Partner")
    state = fields.Selection(selection=[("draft", "Draft"), ("confirmed", "Confirmed")])

    @api.depends("partner_id.discount")
    def _compute_total(self):
        for rec in self:
            rec.total = 0.0
            rec.tax = 0.0

    def action_confirm(self):
        pass

    def create(self, vals_list):
        pass
'''


_EMPTY_MODULE_PY = '''\
from odoo import models


class EmptyModel(models.Model):
    _name = "empty.model"
    _description = "Empty Model"

    def real_method(self):
        return True
'''


# ---------------------------------------------------------------------------
# Test: Report file creation
# ---------------------------------------------------------------------------


class TestReportFileCreation:
    """generate_stub_report() produces .amil-stubs.json in module dir."""

    def test_report_file_created(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        result = generate_stub_report(mod, spec)

        report_file = mod / ".amil-stubs.json"
        assert report_file.exists(), "Report file should be created"

    def test_report_is_valid_json(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        report_file = mod / ".amil-stubs.json"
        data = json.loads(report_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Test: JSON schema compliance
# ---------------------------------------------------------------------------


class TestSchemaCompliance:
    """Generated JSON matches the locked schema from CONTEXT.md."""

    def test_meta_fields_present(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        meta = data["_meta"]
        assert meta["generator"] == "amil-utils"
        assert "generated_at" in meta
        assert meta["module"] == "test_module"
        assert isinstance(meta["total_stubs"], int)
        assert isinstance(meta["budget_count"], int)
        assert isinstance(meta["quality_count"], int)

    def test_stubs_array_present(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        assert "stubs" in data
        assert isinstance(data["stubs"], list)
        assert len(data["stubs"]) == 1  # one stub in simple compute

    def test_stub_entry_has_all_required_fields(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stub = data["stubs"][0]
        required_keys = {
            "id", "file", "line", "class", "model", "method",
            "decorator", "target_fields", "complexity", "context",
        }
        assert required_keys.issubset(stub.keys()), (
            f"Missing keys: {required_keys - stub.keys()}"
        )

    def test_context_has_all_subfields(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        ctx = data["stubs"][0]["context"]
        assert "model_fields" in ctx
        assert "related_fields" in ctx
        assert "business_rules" in ctx
        assert "registry_source" in ctx


# ---------------------------------------------------------------------------
# Test: Stub ID format
# ---------------------------------------------------------------------------


class TestStubIdFormat:
    """Stub id format is "{model_name}__{method_name}" with double underscore."""

    def test_id_uses_double_underscore(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stub = data["stubs"][0]
        assert stub["id"] == "test.order___compute_total"
        assert "__" in stub["id"]


# ---------------------------------------------------------------------------
# Test: StubReport dataclass return
# ---------------------------------------------------------------------------


class TestStubReportReturn:
    """generate_stub_report() returns a StubReport dataclass."""

    def test_returns_stub_report(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        result = generate_stub_report(mod, spec)

        assert isinstance(result, StubReport)
        assert result.total_stubs == 1
        assert result.budget_count == 1
        assert result.quality_count == 0
        assert result.report_path == mod / ".amil-stubs.json"

    def test_quality_stubs_counted(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _QUALITY_STUBS_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        result = generate_stub_report(mod, spec)

        assert result.total_stubs == 3  # _compute_total, action_confirm, create
        assert result.quality_count == 3  # all quality triggers
        assert result.budget_count == 0


# ---------------------------------------------------------------------------
# Test: Empty module (no stubs)
# ---------------------------------------------------------------------------


class TestEmptyModule:
    """Module with 0 stubs writes JSON with empty stubs array."""

    def test_zero_stubs_produces_empty_array(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _EMPTY_MODULE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        result = generate_stub_report(mod, spec)

        assert result.total_stubs == 0
        assert result.budget_count == 0
        assert result.quality_count == 0

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        assert data["stubs"] == []
        assert data["_meta"]["total_stubs"] == 0


# ---------------------------------------------------------------------------
# Integration test: end-to-end realistic stubs
# ---------------------------------------------------------------------------


class TestEndToEndIntegration:
    """Full pipeline from .py files -> JSON report with realistic stubs."""

    def test_mixed_complexity_stubs(self, tmp_path: Path) -> None:
        """Module with both budget and quality stubs."""
        mod = tmp_path / "test_module"
        mod.mkdir()

        mixed_py = '''\
from odoo import models, fields, api


class SaleOrder(models.Model):
    _name = "sale.order"
    _description = "Sale Order"

    amount = fields.Float(string="Amount")
    total = fields.Float(string="Total", compute="_compute_total")
    partner_id = fields.Many2one("res.partner", string="Partner")
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed")])

    @api.depends("amount")
    def _compute_total(self):
        for rec in self:
            rec.total = 0.0

    @api.depends("partner_id.credit_limit")
    def _compute_credit_check(self):
        for rec in self:
            rec.total = 0.0

    def action_confirm(self):
        pass
'''
        _write_py(mod, "models/sale.py", mixed_py)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = {
            "module_name": "test_module",
            "models": [
                {
                    "name": "sale.order",
                    "fields": [
                        {"name": "amount", "type": "Float"},
                        {
                            "name": "total",
                            "type": "Float",
                            "compute": "_compute_total",
                            "depends": ["amount"],
                        },
                        {
                            "name": "partner_id",
                            "type": "Many2one",
                            "comodel_name": "res.partner",
                        },
                    ],
                },
            ],
        }

        result = generate_stub_report(mod, spec)

        assert result.total_stubs == 3
        # _compute_total: budget (simple depends, 1 target field)
        # _compute_credit_check: quality (cross-model depends)
        # action_confirm: quality (action_ prefix)
        assert result.budget_count == 1
        assert result.quality_count == 2

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}

        assert stubs_by_method["_compute_total"]["complexity"] == "budget"
        assert stubs_by_method["_compute_credit_check"]["complexity"] == "quality"
        assert stubs_by_method["action_confirm"]["complexity"] == "quality"

        # Check context is populated for the budget stub
        ctx = stubs_by_method["_compute_total"]["context"]
        assert "amount" in ctx["model_fields"]
        assert isinstance(ctx["business_rules"], list)

    def test_report_trailing_newline(self, tmp_path: Path) -> None:
        """JSON report should end with a trailing newline."""
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        raw = (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        assert raw.endswith("\n"), "JSON should end with trailing newline"


# ---------------------------------------------------------------------------
# Enriched stub sources for report tests
# ---------------------------------------------------------------------------


_CONSTRAINT_STUB_PY = '''\
from odoo import models, fields, api


class TestOrder(models.Model):
    _name = "test.order"
    _description = "Test Order"

    amount = fields.Float(string="Amount")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            pass

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            pass
'''

_MIXED_ENRICHMENT_PY = '''\
from odoo import models, fields, api


class TestOrder(models.Model):
    _name = "test.order"
    _description = "Test Order"

    amount = fields.Float(string="Amount")
    line_ids = fields.One2many("test.order.line", "order_id", string="Lines")
    total = fields.Float(string="Total", compute="_compute_total", store=True)
    partner_id = fields.Many2one("res.partner", string="Partner")

    @api.depends("line_ids.amount")
    def _compute_total(self):
        for rec in self:
            rec.total = 0.0

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            pass

    def action_confirm(self):
        pass
'''


def _enrichment_spec() -> dict[str, Any]:
    """Spec matching _MIXED_ENRICHMENT_PY with line_ids One2many."""
    return {
        "module_name": "test_module",
        "models": [
            {
                "name": "test.order",
                "description": "Test Order",
                "fields": [
                    {"name": "amount", "type": "Float", "string": "Amount"},
                    {
                        "name": "line_ids",
                        "type": "One2many",
                        "string": "Lines",
                        "comodel_name": "test.order.line",
                    },
                    {
                        "name": "total",
                        "type": "Float",
                        "string": "Total",
                        "compute": "_compute_total",
                        "store": True,
                        "depends": ["line_ids.amount"],
                    },
                    {
                        "name": "partner_id",
                        "type": "Many2one",
                        "comodel_name": "res.partner",
                        "string": "Partner",
                    },
                ],
                "complex_constraints": [
                    {"message": "Amount must be between 0 and 10000"},
                ],
            },
        ],
    }


def _constraint_spec() -> dict[str, Any]:
    """Spec matching _CONSTRAINT_STUB_PY."""
    return {
        "module_name": "test_module",
        "models": [
            {
                "name": "test.order",
                "description": "Test Order",
                "fields": [
                    {
                        "name": "amount",
                        "type": "Float",
                        "string": "Amount",
                        "help": "Amount must be between 0 and 10000",
                    },
                    {"name": "start_date", "type": "Date", "string": "Start Date"},
                    {"name": "end_date", "type": "Date", "string": "End Date"},
                ],
                "complex_constraints": [
                    {"message": "Amount must be between 0 and 10000"},
                    {"message": "End date must be after start date"},
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Test: method_type in report
# ---------------------------------------------------------------------------


class TestMethodType:
    """method_type appears in report for all stub types."""

    def test_compute_method_type_in_report(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stub = data["stubs"][0]
        assert stub["method_type"] == "compute"

    def test_action_method_type_in_report(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _MIXED_ENRICHMENT_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _enrichment_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        assert stubs_by_method["action_confirm"]["method_type"] == "action"

    def test_constraint_method_type_in_report(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _CONSTRAINT_STUB_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _constraint_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        assert stubs_by_method["_check_amount"]["method_type"] == "constraint"


# ---------------------------------------------------------------------------
# Test: target_field_types in report
# ---------------------------------------------------------------------------


class TestTargetFieldTypes:
    """target_field_types appears in report for compute stubs with type metadata."""

    def test_compute_has_target_field_types(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _MIXED_ENRICHMENT_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _enrichment_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        compute_stub = stubs_by_method["_compute_total"]
        assert "target_field_types" in compute_stub
        assert "total" in compute_stub["target_field_types"]
        assert compute_stub["target_field_types"]["total"]["type"] == "Float"


# ---------------------------------------------------------------------------
# Test: computation_hint in report
# ---------------------------------------------------------------------------


class TestComputationHint:
    """computation_hint appears in report for compute stubs."""

    def test_compute_has_computation_hint(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _MIXED_ENRICHMENT_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _enrichment_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        compute_stub = stubs_by_method["_compute_total"]
        assert "computation_hint" in compute_stub
        assert compute_stub["computation_hint"] == "sum_related"


# ---------------------------------------------------------------------------
# Test: constraint_type in report
# ---------------------------------------------------------------------------


class TestConstraintTypeReport:
    """constraint_type appears in report for constraint stubs."""

    def test_constraint_has_constraint_type(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _CONSTRAINT_STUB_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _constraint_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        assert "constraint_type" in stubs_by_method["_check_amount"]
        assert stubs_by_method["_check_amount"]["constraint_type"] == "range"


# ---------------------------------------------------------------------------
# Test: error_messages in report
# ---------------------------------------------------------------------------


class TestErrorMessages:
    """error_messages appears in report for constraint stubs."""

    def test_constraint_has_error_messages(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _CONSTRAINT_STUB_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _constraint_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        check_amount = stubs_by_method["_check_amount"]
        assert "error_messages" in check_amount
        assert len(check_amount["error_messages"]) > 0
        msg = check_amount["error_messages"][0]
        assert msg["translatable"] is True


# ---------------------------------------------------------------------------
# Test: Enrichment omission
# ---------------------------------------------------------------------------


class TestEnrichmentOmission:
    """Empty enrichment values are NOT included in JSON (no clutter)."""

    def test_action_has_no_computation_hint(self, tmp_path: Path) -> None:
        """action_confirm stub should NOT have computation_hint in JSON."""
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _MIXED_ENRICHMENT_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _enrichment_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        action_stub = stubs_by_method["action_confirm"]
        assert "computation_hint" not in action_stub
        assert "constraint_type" not in action_stub
        assert "error_messages" not in action_stub

    def test_compute_has_no_constraint_type(self, tmp_path: Path) -> None:
        """Compute stub should NOT have constraint_type in JSON."""
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stub = data["stubs"][0]
        assert "constraint_type" not in stub
        assert "error_messages" not in stub

    def test_action_has_no_target_field_types(self, tmp_path: Path) -> None:
        """Non-compute stubs should NOT have target_field_types in JSON."""
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _MIXED_ENRICHMENT_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _enrichment_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        action_stub = stubs_by_method["action_confirm"]
        assert "target_field_types" not in action_stub


# ---------------------------------------------------------------------------
# Test: Phase 58 new fields in report
# ---------------------------------------------------------------------------


_ACTION_WITH_STATES_PY = '''\
from odoo import models, fields

class TestOrder(models.Model):
    _name = "test.order"
    _description = "Test Order"

    state = fields.Selection(
        selection=[("draft", "Draft"), ("submitted", "Submitted"),
                   ("approved", "Approved"), ("rejected", "Rejected")],
        default="draft",
    )

    def action_submit(self):
        pass

    def action_approve(self):
        pass
'''


_CRON_METHOD_PY = '''\
from odoo import models, api

class TestOrder(models.Model):
    _name = "test.order"
    _description = "Test Order"

    @api.model
    def _cron_send_reminders(self):
        pass
'''


_OVERRIDE_WITH_MARKERS_PY = '''\
from odoo import models, api

class TestOrder(models.Model):
    _name = "test.order"
    _description = "Test Order"

    def write(self, vals):
        result = super().write(vals)
        # --- BUSINESS LOGIC START ---
        # TODO: implement post-write business logic
        pass
        # --- BUSINESS LOGIC END ---
        return result
'''


def _action_spec_with_states() -> dict[str, Any]:
    """Spec with workflow states for action_context enrichment."""
    return {
        "module_name": "test_module",
        "models": [
            {
                "name": "test.order",
                "description": "Test Order",
                "fields": [
                    {
                        "name": "state",
                        "type": "Selection",
                        "string": "State",
                        "selection": [
                            ["draft", "Draft"],
                            ["submitted", "Submitted"],
                            ["approved", "Approved"],
                            ["rejected", "Rejected"],
                        ],
                    },
                ],
                "workflow_states": [
                    {"name": "draft", "description": "Initial state"},
                    {"name": "submitted", "description": "Submitted for review"},
                    {"name": "approved", "description": "Approved"},
                    {"name": "rejected", "description": "Rejected"},
                ],
                "complex_constraints": [
                    {"message": "Cannot submit without at least one line item"},
                    {"message": "Send notification email on submit"},
                ],
            },
        ],
    }


def _cron_spec_with_section() -> dict[str, Any]:
    """Spec with cron section for cron_context enrichment."""
    return {
        "module_name": "test_module",
        "models": [
            {
                "name": "test.order",
                "description": "For each overdue record, send reminder",
                "fields": [],
            },
        ],
        "cron": [
            {
                "method": "_cron_send_reminders",
                "name": "Send Reminders",
                "domain": "[('state', '=', 'overdue'), ('reminder_sent', '=', False)]",
            },
        ],
    }


class TestActionContextInReport:
    """action_context appears in report for action stubs with workflow states."""

    def test_action_has_action_context(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _ACTION_WITH_STATES_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _action_spec_with_states()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        submit_stub = stubs_by_method["action_submit"]
        assert "action_context" in submit_stub
        assert "full_state_machine" in submit_stub["action_context"]
        assert "states" in submit_stub["action_context"]["full_state_machine"]

    def test_action_context_omitted_when_none(self, tmp_path: Path) -> None:
        """action_* without workflow states has no action_context in JSON."""
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _MIXED_ENRICHMENT_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _enrichment_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        action_stub = stubs_by_method["action_confirm"]
        assert "action_context" not in action_stub


class TestCronContextInReport:
    """cron_context appears in report for cron stubs with cron section."""

    def test_cron_has_cron_context(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _CRON_METHOD_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _cron_spec_with_section()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stub = data["stubs"][0]
        assert "cron_context" in stub
        assert stub["cron_context"]["processing_pattern"] == "batch_per_record"
        assert stub["cron_context"]["batch_size_hint"] == 100
        assert stub["cron_context"]["error_handling"] == "log_and_continue"

    def test_cron_context_omitted_when_none(self, tmp_path: Path) -> None:
        """_cron_* without spec cron section has no cron_context in JSON."""
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _CRON_METHOD_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stub = data["stubs"][0]
        assert "cron_context" not in stub


class TestStubZoneInReport:
    """stub_zone and exclusion_zones appear in report for override stubs."""

    def test_override_has_stub_zone(self, tmp_path: Path) -> None:
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _OVERRIDE_WITH_MARKERS_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stubs_by_method = {s["method"]: s for s in data["stubs"]}
        if "write" in stubs_by_method:
            write_stub = stubs_by_method["write"]
            assert "stub_zone" in write_stub
            assert write_stub["stub_zone"]["marker"] == "BUSINESS LOGIC"

    def test_stub_zone_omitted_when_none(self, tmp_path: Path) -> None:
        """Non-override stubs have no stub_zone in JSON."""
        mod = tmp_path / "test_module"
        mod.mkdir()
        _write_py(mod, "models/test.py", _SIMPLE_COMPUTE_PY)
        _write_py(mod, "__init__.py", "")
        _write_py(mod, "models/__init__.py", "")

        spec = _minimal_spec()
        generate_stub_report(mod, spec)

        data = json.loads(
            (mod / ".amil-stubs.json").read_text(encoding="utf-8")
        )
        stub = data["stubs"][0]
        assert "stub_zone" not in stub
        assert "exclusion_zones" not in stub


# ---------------------------------------------------------------------------
# Chain context in stub report (Phase 61 Plan 02)
# ---------------------------------------------------------------------------

from amil_utils.logic_writer.context_builder import StubContext
from amil_utils.logic_writer.report import _stub_to_dict
from amil_utils.logic_writer.stub_detector import StubInfo


class TestChainContextInReport:
    """chain_context appears in report for chain compute stubs."""

    def test_chain_context_present_in_report_entry(self):
        """_stub_to_dict includes chain_context when StubContext has it."""
        stub = StubInfo(
            file="models/student.py",
            line=10,
            class_name="UniStudent",
            model_name="uni.student",
            method_name="_compute_cgpa",
            decorator='@api.depends("enrollment_ids.weighted_grade_points")',
            target_fields=["cgpa"],
        )
        chain_ctx: dict[str, Any] = {
            "chain_id": "cgpa_chain",
            "chain_description": "Grade -> Grade Points -> CGPA",
            "position_in_chain": 3,
            "total_steps": 4,
            "this_step": {"source": "aggregation", "aggregation": "weighted_average"},
            "upstream_steps": [
                {"model": "exam.result", "field": "grade", "source": "direct_input", "type": "Selection"},
            ],
            "downstream_steps": [],
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
        assert "chain_context" in result
        assert result["chain_context"]["chain_id"] == "cgpa_chain"
        assert result["chain_context"]["total_steps"] == 4

        # Verify JSON-serializable
        serialized = json.dumps(result, indent=2)
        parsed = json.loads(serialized)
        assert parsed["chain_context"]["chain_id"] == "cgpa_chain"

    def test_chain_context_absent_when_none(self):
        """_stub_to_dict omits chain_context when StubContext has None."""
        stub = StubInfo(
            file="models/order.py",
            line=5,
            class_name="SaleOrder",
            model_name="sale.order",
            method_name="_compute_total",
            decorator='@api.depends("amount")',
            target_fields=["total"],
        )
        ctx = StubContext(
            model_fields={"total": {"type": "Float"}},
            related_fields={},
            business_rules=[],
            registry_source=None,
            method_type="compute",
        )
        result = _stub_to_dict(stub, ctx, "budget")
        assert "chain_context" not in result
