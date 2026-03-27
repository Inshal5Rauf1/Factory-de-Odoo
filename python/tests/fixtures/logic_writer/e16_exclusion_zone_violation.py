"""E16 test helper: skeleton + filled file pair for exclusion zone violation testing.

E16 tests need a skeleton directory and a filled file with differences
outside BUSINESS LOGIC marker zones. This module provides helper functions
to create the necessary file structures in tmp_path.
"""

SKELETON_SOURCE = """\
from odoo import api, fields, models


class TestModel(models.Model):
    _name = "test.model"
    _description = "Test Model"

    name = fields.Char(string="Name")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')])

    def create(self, vals_list):
        # Audit trail logging
        vals_list = self._add_audit_fields(vals_list)
        # --- BUSINESS LOGIC START ---
        pass  # TODO: implement business logic
        # --- BUSINESS LOGIC END ---
        return super().create(vals_list)
"""

# Filled source: ONLY changes inside marker zone (should pass E16)
FILLED_GOOD_SOURCE = """\
from odoo import api, fields, models


class TestModel(models.Model):
    _name = "test.model"
    _description = "Test Model"

    name = fields.Char(string="Name")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')])

    def create(self, vals_list):
        # Audit trail logging
        vals_list = self._add_audit_fields(vals_list)
        # --- BUSINESS LOGIC START ---
        if not vals_list.get('name'):
            vals_list['name'] = 'Default Name'
        # --- BUSINESS LOGIC END ---
        return super().create(vals_list)
"""

# Filled source: changes OUTSIDE marker zone (should trigger E16)
FILLED_BAD_SOURCE = """\
from odoo import api, fields, models


class TestModel(models.Model):
    _name = "test.model"
    _description = "Test Model MODIFIED"

    name = fields.Char(string="Name")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')])
    extra_field = fields.Boolean()

    def create(self, vals_list):
        # Audit trail logging -- MODIFIED COMMENT
        vals_list = self._add_audit_fields(vals_list)
        # --- BUSINESS LOGIC START ---
        if not vals_list.get('name'):
            vals_list['name'] = 'Default Name'
        # --- BUSINESS LOGIC END ---
        return super().create(vals_list)
"""
