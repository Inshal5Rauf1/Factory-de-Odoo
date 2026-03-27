"""E7 bad-fill fixture: compute method assigns to self.field without for-loop over self."""

SOURCE = """\
from odoo import api, fields, models


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    total = fields.Float(string="Total")
    line_ids = fields.One2many("fee.invoice.line", "invoice_id")

    @api.depends("line_ids.amount")
    def _compute_total(self):
        self.total = sum(self.line_ids.mapped('amount'))
"""
