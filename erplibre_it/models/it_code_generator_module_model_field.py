from odoo import _, api, fields, models


class ItCodeGeneratorModuleModelField(models.Model):
    _name = "it.code_generator.module.model.field"
    _description = "it_code_generator_module_model_field"

    name = fields.Char()

    help = fields.Char()

    model_id = fields.Many2one(
        comodel_name="it.code_generator.module.model",
        string="Model",
    )

    type = fields.Char()
