"""E15 bad-fill fixture: cron method without @api.model decorator."""

SOURCE = """\
from odoo import api, fields, models


class TestCronBad(models.Model):
    _name = "test.cron.bad"
    _description = "Bad Cron"

    name = fields.Char(string="Name")
    reminder_sent = fields.Boolean(default=False)

    def _cron_send_reminders(self):
        # Missing @api.model decorator -- E15 should fire
        records = self.env['test.cron.bad'].search([
            ('reminder_sent', '=', False),
        ])
        for rec in records:
            rec.reminder_sent = True
"""
