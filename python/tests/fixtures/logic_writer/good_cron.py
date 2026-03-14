"""Good cron fixture: correct cron method with @api.model decorator."""

SOURCE = """\
from odoo import api, fields, models


class TestCronGood(models.Model):
    _name = "test.cron.good"
    _description = "Good Cron"

    name = fields.Char(string="Name")
    reminder_sent = fields.Boolean(default=False)

    @api.model
    def _cron_send_reminders(self):
        records = self.env['test.cron.good'].search([
            ('reminder_sent', '=', False),
        ])
        for rec in records:
            rec.reminder_sent = True
"""
