"""E8 bad-fill fixture: compute method with @api.depends that never assigns to target field."""

SOURCE = """\
from odoo import api, fields, models


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    total = fields.Float(string="Total", compute="_compute_total", store=True)
    line_ids = fields.One2many("fee.invoice.line", "invoice_id")

    @api.depends("line_ids.amount")
    def _compute_total(self):
        for rec in self:
            # BUG: never assigns to rec.total
            subtotal = sum(rec.line_ids.mapped('amount'))
            print(subtotal)
"""
