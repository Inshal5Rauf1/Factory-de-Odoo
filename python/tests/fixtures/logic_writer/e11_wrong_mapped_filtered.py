"""E11 bad-fill fixture: mapped() with bare Name arg and filtered() with string comparison."""

SOURCE = """\
from odoo import api, fields, models


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    total = fields.Float(string="Total", compute="_compute_total")
    line_ids = fields.One2many("fee.invoice.line", "invoice_id")
    state = fields.Selection([("draft", "Draft"), ("done", "Done")])

    @api.depends("line_ids.amount")
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.line_ids.mapped(amount))

    @api.constrains("state")
    def _check_state(self):
        for rec in self:
            bad_lines = rec.line_ids.filtered('state == done')
            if bad_lines:
                pass
"""
