"""Good override fixture: correct create/write calling super()."""

SOURCE = """\
from odoo import api, fields, models


class TestOverrideGood(models.Model):
    _name = "test.override.good"
    _description = "Good Override"

    name = fields.Char(string="Name")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')])

    def create(self, vals_list):
        # --- BUSINESS LOGIC START ---
        if not vals_list.get('name'):
            vals_list['name'] = 'Default'
        # --- BUSINESS LOGIC END ---
        return super().create(vals_list)

    def write(self, vals):
        # --- BUSINESS LOGIC START ---
        if 'state' in vals:
            self._check_state_transition(vals['state'])
        # --- BUSINESS LOGIC END ---
        return super().write(vals)
"""
