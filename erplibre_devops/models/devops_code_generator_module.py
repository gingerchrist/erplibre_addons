from odoo import _, api, fields, models


class DevopsCodeGeneratorModule(models.Model):
    _name = "devops.code_generator.module"
    _description = "devops_code_generator_module"

    name = fields.Char()

    code_generator = fields.Many2one(
        comodel_name="devops.code_generator",
        string="Project",
        required=True,
        ondelete="cascade",
    )

    model_ids = fields.One2many(
        comodel_name="devops.code_generator.module.model",
        inverse_name="module_id",
        string="Model",
    )

    devops_workspace_ids = fields.Many2many(
        comodel_name="devops.workspace",
        string="DevOps Workspace",
        required=True,
    )
