from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrTrainingAutoFixTest(models.Model):
    _name = "hr.training.auto.fix.test"
    _description = "Auto Fix Test Training"

    name = fields.Char(string="Name", required=True)
