"""Tests for logic_writer.stub_detector -- AST-based stub detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from amil_utils.logic_writer.stub_detector import (
    StubInfo,
    _extract_decorator_string,
    _extract_model_name,
    _extract_target_fields,
    _find_stub_zones,
    _is_stub_body,
    detect_stubs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_py(tmp_path: Path, rel: str, source: str) -> Path:
    """Write *source* to *tmp_path / rel* and return the file path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# StubInfo frozen dataclass
# ---------------------------------------------------------------------------


class TestStubInfoDataclass:
    """StubInfo is a frozen dataclass with all 7 fields."""

    def test_stub_info_fields(self) -> None:
        info = StubInfo(
            file="models/fee.py",
            line=42,
            class_name="UniFee",
            model_name="uni.fee",
            method_name="_compute_total",
            decorator='@api.depends("amount")',
            target_fields=["total"],
        )
        assert info.file == "models/fee.py"
        assert info.line == 42
        assert info.class_name == "UniFee"
        assert info.model_name == "uni.fee"
        assert info.method_name == "_compute_total"
        assert info.decorator == '@api.depends("amount")'
        assert info.target_fields == ["total"]

    def test_stub_info_is_frozen(self) -> None:
        info = StubInfo(
            file="models/fee.py",
            line=42,
            class_name="UniFee",
            model_name="uni.fee",
            method_name="_compute_total",
            decorator="",
            target_fields=[],
        )
        with pytest.raises(AttributeError):
            info.file = "other.py"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Compute stub detection: for rec in self: rec.field = constant
# ---------------------------------------------------------------------------


class TestComputeStub:
    """detect_stubs() identifies compute stubs."""

    def test_compute_stub_detected(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models, fields, api

class UniFee(models.Model):
    _name = "uni.fee"

    total = fields.Float()

    @api.depends("amount", "discount")
    def _compute_total(self):
        for rec in self:
            rec.total = 0
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        s = stubs[0]
        assert s.method_name == "_compute_total"
        assert s.target_fields == ["total"]
        assert s.model_name == "uni.fee"
        assert s.class_name == "UniFee"

    def test_compute_stub_multiple_fields(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models, fields, api

class UniFee(models.Model):
    _name = "uni.fee"

    @api.depends("amount")
    def _compute_totals(self):
        for rec in self:
            rec.total = 0
            rec.subtotal = 0
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert set(stubs[0].target_fields) == {"total", "subtotal"}


# ---------------------------------------------------------------------------
# Constraint stub detection: for rec in self: pass
# ---------------------------------------------------------------------------


class TestConstraintStub:
    """detect_stubs() identifies constraint stubs."""

    def test_constraint_stub_detected(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models, fields, api

class UniFee(models.Model):
    _name = "uni.fee"

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].method_name == "_check_amount"


# ---------------------------------------------------------------------------
# Action/cron stub detection: bare pass
# ---------------------------------------------------------------------------


class TestActionStub:
    """detect_stubs() identifies action and cron stubs (bare pass)."""

    def test_action_stub_detected(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].method_name == "action_confirm"

    def test_cron_stub_detected(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models, api

class UniFee(models.Model):
    _name = "uni.fee"

    @api.model
    def _cron_check_deadlines(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].method_name == "_cron_check_deadlines"


# ---------------------------------------------------------------------------
# Docstring handling
# ---------------------------------------------------------------------------


class TestDocstringHandling:
    """detect_stubs() handles docstrings correctly."""

    def test_docstring_plus_pass_is_stub(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        """Confirm the fee."""
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].method_name == "action_confirm"

    def test_docstring_only_is_stub(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        """Confirm the fee."""
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].method_name == "action_confirm"


# ---------------------------------------------------------------------------
# Real implementation NOT detected
# ---------------------------------------------------------------------------


class TestRealImplementation:
    """detect_stubs() ignores methods with real implementations."""

    def test_real_implementation_skipped(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models, fields, api

class UniFee(models.Model):
    _name = "uni.fee"

    @api.depends("amount", "discount")
    def _compute_total(self):
        for rec in self:
            rec.total = rec.amount - rec.discount
            if rec.total < 0:
                rec.total = 0
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 0

    def test_multi_statement_body_skipped(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        self.ensure_one()
        self.env["uni.fee.line"].search([("fee_id", "=", self.id)]).unlink()
        self.state = "confirmed"
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 0


# ---------------------------------------------------------------------------
# Decorator extraction
# ---------------------------------------------------------------------------


class TestDecoratorExtraction:
    """_extract_decorator_string() returns full decorator text from source."""

    def test_depends_decorator(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models, fields, api

class UniFee(models.Model):
    _name = "uni.fee"

    @api.depends("amount", "discount")
    def _compute_total(self):
        for rec in self:
            rec.total = 0
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert '@api.depends("amount", "discount")' in stubs[0].decorator

    def test_no_decorator(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].decorator == ""


# ---------------------------------------------------------------------------
# SyntaxError handling
# ---------------------------------------------------------------------------


class TestSyntaxErrorHandling:
    """detect_stubs() handles files with syntax errors gracefully."""

    def test_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/broken.py",
            "def foo(\n    # unclosed paren\n",
        )
        stubs = detect_stubs(tmp_path)
        assert stubs == []

    def test_syntax_error_does_not_crash_with_good_files(
        self, tmp_path: Path
    ) -> None:
        _write_py(
            tmp_path,
            "models/broken.py",
            "class BadSyntax(\n",
        )
        _write_py(
            tmp_path,
            "models/good.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].method_name == "action_confirm"


# ---------------------------------------------------------------------------
# Recursive scanning
# ---------------------------------------------------------------------------


class TestRecursiveScanning:
    """detect_stubs() finds stubs in subdirectories."""

    def test_scans_models_subdirectory(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        pass
''',
        )
        _write_py(
            tmp_path,
            "wizard/fee_wizard.py",
            '''\
from odoo import models

class UniFeeWizard(models.TransientModel):
    _name = "uni.fee.wizard"

    def action_apply(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 2
        methods = {s.method_name for s in stubs}
        assert methods == {"action_confirm", "action_apply"}


# ---------------------------------------------------------------------------
# _extract_model_name
# ---------------------------------------------------------------------------


class TestExtractModelName:
    """_extract_model_name() returns _name value from class body."""

    def test_class_without_name_skipped(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
class HelperMixin:
    """Not an Odoo model -- no _name."""

    def action_confirm(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 0


# ---------------------------------------------------------------------------
# Line number accuracy
# ---------------------------------------------------------------------------


class TestLineNumberAccuracy:
    """StubInfo.line is correct and 1-based."""

    def test_line_number_correct(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        # def action_confirm(self): is on line 6
        assert stubs[0].line == 6


# ---------------------------------------------------------------------------
# File path in StubInfo
# ---------------------------------------------------------------------------


class TestFilePathInStubInfo:
    """StubInfo.file is a relative path within the module."""

    def test_file_path_relative(self, tmp_path: Path) -> None:
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models

class UniFee(models.Model):
    _name = "uni.fee"

    def action_confirm(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        assert len(stubs) == 1
        assert stubs[0].file == "models/fee.py"


# ---------------------------------------------------------------------------
# Marker zone detection: _find_stub_zones()
# ---------------------------------------------------------------------------


class TestMarkerZones:
    """_find_stub_zones() detects BUSINESS LOGIC marker pairs in source."""

    def test_single_zone_detected(self) -> None:
        """Source with one marker pair returns one zone dict."""
        lines = [
            "    def write(self, vals):",
            "        result = super().write(vals)",
            "        # --- BUSINESS LOGIC START ---",
            "        # TODO: implement post-write business logic",
            "        pass",
            "        # --- BUSINESS LOGIC END ---",
            "        return result",
        ]
        zones = _find_stub_zones(lines)
        assert len(zones) == 1
        zone = zones[0]
        assert zone["start_line"] == 3  # 1-based
        assert zone["end_line"] == 6
        assert zone["marker"] == "BUSINESS LOGIC"

    def test_dual_zones_detected(self) -> None:
        """Source with two marker pairs (pre-super + post-super) returns 2 zones."""
        lines = [
            "    @api.model_create_multi",
            "    def create(self, vals_list):",
            "        # --- BUSINESS LOGIC START ---",
            "        # TODO: implement pre-create business logic",
            "        pass",
            "        # --- BUSINESS LOGIC END ---",
            "        records = super().create(vals_list)",
            "        # --- BUSINESS LOGIC START ---",
            "        # TODO: implement post-create business logic",
            "        pass",
            "        # --- BUSINESS LOGIC END ---",
            "        return records",
        ]
        zones = _find_stub_zones(lines)
        assert len(zones) == 2
        assert zones[0]["start_line"] == 3
        assert zones[0]["end_line"] == 6
        assert zones[1]["start_line"] == 8
        assert zones[1]["end_line"] == 11

    def test_no_markers_returns_empty(self) -> None:
        """Source with no markers returns empty list."""
        lines = [
            "    def write(self, vals):",
            "        result = super().write(vals)",
            "        return result",
        ]
        zones = _find_stub_zones(lines)
        assert zones == []

    def test_unclosed_marker_ignored(self) -> None:
        """START without matching END is ignored (returns empty list)."""
        lines = [
            "    def write(self, vals):",
            "        # --- BUSINESS LOGIC START ---",
            "        pass",
            "        result = super().write(vals)",
            "        return result",
        ]
        zones = _find_stub_zones(lines)
        assert zones == []

    def test_detect_stubs_works_with_markers(self, tmp_path: Path) -> None:
        """detect_stubs still works on files containing BUSINESS LOGIC markers."""
        _write_py(
            tmp_path,
            "models/fee.py",
            '''\
from odoo import models, api

class UniFee(models.Model):
    _name = "uni.fee"

    @api.model_create_multi
    def create(self, vals_list):
        # --- BUSINESS LOGIC START ---
        # TODO: implement pre-create business logic
        pass
        # --- BUSINESS LOGIC END ---
        records = super().create(vals_list)
        # --- BUSINESS LOGIC START ---
        # TODO: implement post-create business logic
        pass
        # --- BUSINESS LOGIC END ---
        return records

    def action_confirm(self):
        pass
''',
        )
        stubs = detect_stubs(tmp_path)
        # action_confirm is detected as stub; create is NOT detected because
        # its body is more than just bare pass (it has marker comments + super call)
        assert len(stubs) == 1
        assert stubs[0].method_name == "action_confirm"

    def test_jinja_create_template_markers(self) -> None:
        """Create method template has pre-super and post-super marker zones."""
        # Simulate what the Jinja template would produce for create
        rendered = [
            "    @api.model_create_multi",
            "    def create(self, vals_list):",
            "        # --- BUSINESS LOGIC START ---",
            "        # TODO: implement pre-create business logic",
            "        pass",
            "        # --- BUSINESS LOGIC END ---",
            "        records = super().create(vals_list)",
            "        # --- BUSINESS LOGIC START ---",
            "        # TODO: implement post-create business logic",
            "        pass",
            "        # --- BUSINESS LOGIC END ---",
            "        return records",
        ]
        zones = _find_stub_zones(rendered)
        assert len(zones) == 2

    def test_jinja_write_template_markers(self) -> None:
        """Write method template has post-super marker zone only."""
        rendered = [
            "    def write(self, vals):",
            "        result = super().write(vals)",
            "        # --- BUSINESS LOGIC START ---",
            "        # TODO: implement post-write business logic",
            "        pass",
            "        # --- BUSINESS LOGIC END ---",
            "        return result",
        ]
        zones = _find_stub_zones(rendered)
        assert len(zones) == 1
