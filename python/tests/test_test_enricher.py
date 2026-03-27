"""Tests for post-logic-writer test enrichment."""
import textwrap
from pathlib import Path

from amil_utils.test_enricher import ComputeTestHint, extract_compute_hints


class TestExtractComputeHints:
    def test_extracts_compute_with_depends(self, tmp_path: Path) -> None:
        models = tmp_path / "models"
        models.mkdir()
        (models / "order.py").write_text(
            textwrap.dedent("""\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                quantity = fields.Integer()
                unit_price = fields.Float()
                total = fields.Float(compute="_compute_total")

                @api.depends("quantity", "unit_price")
                def _compute_total(self):
                    for rec in self:
                        rec.total = rec.quantity * rec.unit_price
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert len(hints) == 1
        h = hints[0]
        assert h.model_name == "sale.order"
        assert h.method_name == "_compute_total"
        assert h.target_field == "total"
        assert h.depends_fields == ["quantity", "unit_price"]
        assert h.field_type == "Float"

    def test_no_models_dir(self, tmp_path: Path) -> None:
        assert extract_compute_hints(tmp_path) == []

    def test_skips_non_compute_methods(self, tmp_path: Path) -> None:
        models = tmp_path / "models"
        models.mkdir()
        (models / "order.py").write_text(
            textwrap.dedent("""\
            from odoo import fields, models

            class Order(models.Model):
                _name = "sale.order"
                def action_confirm(self):
                    pass
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert len(hints) == 0

    def test_multiple_computes(self, tmp_path: Path) -> None:
        models = tmp_path / "models"
        models.mkdir()
        (models / "order.py").write_text(
            textwrap.dedent("""\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")
                tax = fields.Float(compute="_compute_tax")

                @api.depends("line_ids")
                def _compute_total(self):
                    pass

                @api.depends("total")
                def _compute_tax(self):
                    pass
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert len(hints) == 2
        assert hints[0].target_field == "total"
        assert hints[0].depends_fields == ["line_ids"]
        assert hints[1].target_field == "tax"
        assert hints[1].depends_fields == ["total"]

    def test_syntax_error_file_skipped(self, tmp_path: Path) -> None:
        models = tmp_path / "models"
        models.mkdir()
        (models / "broken.py").write_text("def bad syntax {{")
        hints = extract_compute_hints(tmp_path)
        assert hints == []

    def test_compute_without_depends_decorator(self, tmp_path: Path) -> None:
        """A _compute_ method without @api.depends should yield empty depends_fields."""
        models = tmp_path / "models"
        models.mkdir()
        (models / "order.py").write_text(
            textwrap.dedent("""\
            from odoo import fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")

                def _compute_total(self):
                    for rec in self:
                        rec.total = 0.0
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert len(hints) == 1
        assert hints[0].depends_fields == []
        assert hints[0].field_type == "Float"

    def test_unknown_field_type(self, tmp_path: Path) -> None:
        """When no field definition matches, field_type should be 'unknown'."""
        models = tmp_path / "models"
        models.mkdir()
        (models / "order.py").write_text(
            textwrap.dedent("""\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"

                @api.depends("name")
                def _compute_display(self):
                    for rec in self:
                        rec.display = rec.name
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert len(hints) == 1
        assert hints[0].field_type == "unknown"

    def test_class_without_name_skipped(self, tmp_path: Path) -> None:
        """A class without _name attribute should be skipped entirely."""
        models = tmp_path / "models"
        models.mkdir()
        (models / "mixin.py").write_text(
            textwrap.dedent("""\
            from odoo import api, fields, models

            class OrderMixin(models.AbstractModel):
                _description = "Order Mixin"

                @api.depends("name")
                def _compute_display(self):
                    pass
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert hints == []

    def test_hint_is_frozen(self, tmp_path: Path) -> None:
        """ComputeTestHint is a frozen dataclass -- attributes cannot be mutated."""
        models = tmp_path / "models"
        models.mkdir()
        (models / "order.py").write_text(
            textwrap.dedent("""\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")

                @api.depends("quantity")
                def _compute_total(self):
                    for rec in self:
                        rec.total = 0.0
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert len(hints) == 1
        import dataclasses

        assert dataclasses.is_dataclass(hints[0])
        # frozen=True means we cannot set attributes
        try:
            hints[0].model_name = "other.model"  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except dataclasses.FrozenInstanceError:
            pass

    def test_multiple_files(self, tmp_path: Path) -> None:
        """Hints are collected across multiple .py files in models/."""
        models = tmp_path / "models"
        models.mkdir()
        (models / "order.py").write_text(
            textwrap.dedent("""\
            from odoo import api, fields, models

            class Order(models.Model):
                _name = "sale.order"
                total = fields.Float(compute="_compute_total")

                @api.depends("quantity")
                def _compute_total(self):
                    pass
        """)
        )
        (models / "line.py").write_text(
            textwrap.dedent("""\
            from odoo import api, fields, models

            class OrderLine(models.Model):
                _name = "sale.order.line"
                subtotal = fields.Float(compute="_compute_subtotal")

                @api.depends("qty", "price")
                def _compute_subtotal(self):
                    pass
        """)
        )
        hints = extract_compute_hints(tmp_path)
        assert len(hints) == 2
        model_names = {h.model_name for h in hints}
        assert model_names == {"sale.order", "sale.order.line"}
