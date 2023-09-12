from odoo import _, api, fields, models


class ItCodeGenerator(models.Model):
    _name = "it.code_generator"
    _description = "it_code_generator"

    name = fields.Char()

    it_workspace_id = fields.Many2one(
        comodel_name="it.workspace",
        string="It Workspace",
    )

    module_ids = fields.One2many(
        comodel_name="it.code_generator.module",
        inverse_name="code_generator",
    )
