from odoo import _, api, fields, models


class ItCodeGeneratorModule(models.Model):
    _name = "it.code_generator.module"
    _description = "it_code_generator_module"

    name = fields.Char()

    code_generator = fields.Many2one(
        comodel_name="it.code_generator",
        string="Project",
        required=True,
        ondelete="cascade",
    )

    model_ids = fields.One2many(
        comodel_name="it.code_generator.module.model",
        inverse_name="module_id",
        string="Model",
    )

    it_workspace_ids = fields.Many2many(
        comodel_name="it.workspace",
        required=True,
        string="It Workspace",
    )
