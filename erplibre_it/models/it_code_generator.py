from odoo import _, api, fields, models


class ItCodeGenerator(models.Model):
    _name = "it.code_generator"
    _description = "it_code_generator"

    name = fields.Char()

    it_workspace_id = fields.Many2one("it.workspace")


