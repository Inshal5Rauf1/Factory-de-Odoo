"""E10 bad-fill fixture: bare field name reference in for-loop body instead of record.field."""

SOURCE = """\
from odoo import api, fields, models


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    amount = fields.Float(string="Amount")
    tax_amount = fields.Float(string="Tax Amount")
    total = fields.Float(string="Total", compute="_compute_total")

    @api.depends("amount", "tax_amount")
    def _compute_total(self):
        for rec in self:
            rec.total = amount + tax_amount
"""
