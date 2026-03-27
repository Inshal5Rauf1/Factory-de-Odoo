"""Tests for AST-based logic verifier."""
from __future__ import annotations

import textwrap
from pathlib import Path

from amil_utils.logic_verifier import verify_action_methods, verify_compute_methods


class TestVerifyComputeMethods:
    def test_valid_compute_passes(self, tmp_path: Path):
        """Compute that assigns target field should pass."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")

                @api.depends("line_ids.price")
                def _compute_total(self):
                    for rec in self:
                        rec.total = sum(line.price for line in rec.line_ids)
        '''))
        issues = verify_compute_methods(tmp_path)
        assert len(issues) == 0

    def test_stub_compute_flagged(self, tmp_path: Path):
        """Compute with only 'pass' should be flagged."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")

                @api.depends("line_ids.price")
                def _compute_total(self):
                    for rec in self:
                        pass
        '''))
        issues = verify_compute_methods(tmp_path)
        assert len(issues) == 1
        assert "total" in issues[0]["issue"]

    def test_compute_assigns_wrong_field(self, tmp_path: Path):
        """Compute that assigns a different field should be flagged."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")

                @api.depends("qty")
                def _compute_total(self):
                    for rec in self:
                        rec.name = "wrong field"
        '''))
        issues = verify_compute_methods(tmp_path)
        assert len(issues) == 1

    def test_no_models_dir_returns_empty(self, tmp_path: Path):
        """Module without models/ dir should return empty list."""
        issues = verify_compute_methods(tmp_path)
        assert issues == []

    def test_syntax_error_file_skipped(self, tmp_path: Path):
        """Files with syntax errors should be skipped gracefully."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "broken.py").write_text("def broken(\n")
        issues = verify_compute_methods(tmp_path)
        assert issues == []

    def test_multiple_compute_methods(self, tmp_path: Path):
        """Multiple compute methods: only the invalid one is flagged."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")
                tax = fields.Float(compute="_compute_tax")

                @api.depends("line_ids.price")
                def _compute_total(self):
                    for rec in self:
                        rec.total = sum(line.price for line in rec.line_ids)

                @api.depends("total")
                def _compute_tax(self):
                    pass
        '''))
        issues = verify_compute_methods(tmp_path)
        assert len(issues) == 1
        assert issues[0]["method"] == "_compute_tax"


class TestVerifyActionMethods:
    def test_action_with_state_check_passes(self, tmp_path: Path):
        """Action that checks state before modifying should pass."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import api, fields, models
            from odoo.exceptions import ValidationError

            class Order(models.Model):
                _name = "sale.order"
                state = fields.Selection([("draft", "Draft"), ("done", "Done")])

                def action_confirm(self):
                    for rec in self:
                        if rec.state != "draft":
                            raise ValidationError("Can only confirm drafts")
                        rec.state = "done"
        '''))
        issues = verify_action_methods(tmp_path)
        assert len(issues) == 0

    def test_action_without_state_check_flagged(self, tmp_path: Path):
        """Action that modifies state without checking should be flagged."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import fields, models

            class Order(models.Model):
                _name = "sale.order"
                state = fields.Selection([("draft", "Draft"), ("done", "Done")])

                def action_confirm(self):
                    for rec in self:
                        rec.state = "done"
        '''))
        issues = verify_action_methods(tmp_path)
        assert len(issues) >= 1
        assert "state" in issues[0]["issue"]

    def test_action_without_state_write_passes(self, tmp_path: Path):
        """Action that does not write state at all should pass."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import fields, models

            class Order(models.Model):
                _name = "sale.order"
                state = fields.Selection([("draft", "Draft"), ("done", "Done")])

                def action_print(self):
                    return self.env.ref("module.report").report_action(self)
        '''))
        issues = verify_action_methods(tmp_path)
        assert len(issues) == 0

    def test_no_models_dir_returns_empty(self, tmp_path: Path):
        """Module without models/ dir should return empty list."""
        issues = verify_action_methods(tmp_path)
        assert issues == []

    def test_non_action_method_ignored(self, tmp_path: Path):
        """Methods not starting with action_ should be ignored."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "order.py").write_text(textwrap.dedent('''\
            from odoo import fields, models

            class Order(models.Model):
                _name = "sale.order"
                state = fields.Selection([("draft", "Draft"), ("done", "Done")])

                def confirm(self):
                    for rec in self:
                        rec.state = "done"
        '''))
        issues = verify_action_methods(tmp_path)
        assert len(issues) == 0
