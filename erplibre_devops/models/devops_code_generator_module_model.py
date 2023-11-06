from odoo import _, api, fields, models


class DevopsCodeGeneratorModuleModel(models.Model):
    _name = "devops.code_generator.module.model"
    _description = "devops_code_generator_module_model"

    name = fields.Char()

    description = fields.Char()

    field_ids = fields.One2many(
        comodel_name="devops.code_generator.module.model.field",
        inverse_name="model_id",
        string="Field",
    )

    module_id = fields.Many2one(
        comodel_name="devops.code_generator.module",
        string="Module",
        required=True,
        ondelete="cascade",
    )

    devops_workspace_ids = fields.Many2many(
        comodel_name="devops.workspace",
        string="DevOps Workspace",
        required=True,
    )
