from odoo import fields, models


class DockerTestModel(models.Model):
    _name = "docker.test.model"
    _description = "Docker Test Model"

    name = fields.Char(string="Test Name", required=True)
    description = fields.Text(string="Test Description")
    is_active = fields.Boolean(string="Active", default=True)
    partner_id = fields.Many2one("res.partner", string="Related Partner")
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done")],
        string="Status",
        default="draft",
    )
