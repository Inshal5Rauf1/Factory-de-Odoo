"""Good compute fixture: correct implementation that should pass all E7-E12 checks."""

SOURCE = """\
from odoo import api, fields, models


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    total = fields.Float(string="Total", compute="_compute_total", store=True)
    line_ids = fields.One2many("fee.invoice.line", "invoice_id")
    discount = fields.Float(string="Discount")

    @api.depends("line_ids.amount", "discount")
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.line_ids.mapped('amount')) - rec.discount
"""
