"""Good action fixture: correct action method with state check before assignment."""

SOURCE = """\
from odoo import api, fields, models
from odoo.exceptions import UserError


class TestActionGood(models.Model):
    _name = "test.action.good"
    _description = "Good Action"

    name = fields.Char(string="Name")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], default='draft')

    def action_submit(self):
        if self.state != 'draft':
            raise UserError("Can only submit from draft state.")
        self.state = 'submitted'
"""
