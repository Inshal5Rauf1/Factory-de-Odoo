"""Good constraint fixture: correct implementation that should pass all E7-E12 checks."""

SOURCE = """\
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FeeInvoice(models.Model):
    _name = "fee.invoice"
    _description = "Fee Invoice"

    amount = fields.Float(string="Amount")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError("Amount must be positive.")

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError("Start date must be before end date.")
"""
