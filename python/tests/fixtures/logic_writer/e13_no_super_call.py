"""E13 bad-fill fixture: create/write overrides that don't call super()."""

SOURCE = """\
from odoo import api, fields, models


class TestOverrideBad(models.Model):
    _name = "test.override.bad"
    _description = "Bad Override"

    name = fields.Char(string="Name")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')])

    def create(self, vals_list):
        # Missing super() call -- E13 should fire
        return self.env['test.override.bad'].browse()

    def write(self, vals):
        # Missing super() call -- E13 should fire
        if 'name' in vals:
            self.env.cr.execute("SELECT 1")
        return True
"""
