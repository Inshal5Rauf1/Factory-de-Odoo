"""E9 bad-fill fixture: constraint method that never raises ValidationError."""

SOURCE = """\
from odoo import api, fields, models


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    amount = fields.Float(string="Amount")

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                # BUG: logs instead of raising ValidationError
                print("Amount is negative!")
"""
