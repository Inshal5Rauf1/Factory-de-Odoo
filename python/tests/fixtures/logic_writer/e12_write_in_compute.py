"""E12 bad-fill fixture: self.write()/create()/unlink() inside @api.depends method."""

SOURCE = """\
from odoo import api, fields, models


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    total = fields.Float(string="Total", compute="_compute_total")
    line_ids = fields.One2many("fee.invoice.line", "invoice_id")

    @api.depends("line_ids.amount")
    def _compute_total(self):
        total = sum(self.line_ids.mapped('amount'))
        self.write({'total': total})
"""
