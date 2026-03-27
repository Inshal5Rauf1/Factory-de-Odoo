"""W5 bad-fill fixture: action method assigns state without checking current state."""

SOURCE = """\
from odoo import api, fields, models


class TestActionBad(models.Model):
    _name = "test.action.bad"
    _description = "Bad Action"

    name = fields.Char(string="Name")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], default='draft')

    def action_submit(self):
        # Missing state check -- W5 should fire
        self.state = 'submitted'
"""
