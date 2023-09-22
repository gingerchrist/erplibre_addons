from odoo import _, api, fields, models


class ItCodeGeneratorModuleModel(models.Model):
    _name = "it.code_generator.module.model"
    _description = "it_code_generator_module_model"

    name = fields.Char()

    description = fields.Char()

    field_ids = fields.One2many(
        comodel_name="it.code_generator.module.model.field",
        inverse_name="model_id",
    )

    module_id = fields.Many2one(
        comodel_name="it.code_generator.module",
        string="Module",
    )

    it_workspace_ids = fields.Many2many(
        comodel_name="it.workspace",
        string="It Workspace",
    )
