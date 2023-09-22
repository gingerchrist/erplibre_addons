from odoo import _, api, exceptions, fields, models
import json


class ItCodeGenerator(models.Model):
    _name = "it.code_generator"
    _description = "it_code_generator"

    name = fields.Char()

    # TODO if share result, do a command to copy file all and recreate it like a mirror on other workspace
    it_workspace_ids = fields.Many2many(
        comodel_name="it.workspace",
        string="It Workspace",
    )

    # TODO create boolean cache with default workspace to work for the other
    default_workspace_master = fields.Many2one(
        comodel_name="it.workspace",
        string="It Workspace default",
    )

    module_ids = fields.One2many(
        comodel_name="it.code_generator.module",
        inverse_name="code_generator",
    )

    force_clean_before_generate = fields.Boolean(
        help="Will remove all modules to generate news."
    )

    @api.model_create_multi
    def create(self, vals_list):
        r = super().create(vals_list)
        w_ids = self.env.context.get("default_it_workspace_ids")
        if w_ids:
            for cg_id in r:
                if not cg_id.default_workspace_master:
                    cg_id.default_workspace_master = w_ids[0]

                if not cg_id.it_workspace_ids:
                    cg_id.it_workspace_ids = [6, 0, w_ids]
                for module_id in cg_id.module_ids:
                    if not module_id.it_workspace_ids:
                        module_id.it_workspace_ids = [
                            (
                                6,
                                0,
                                w_ids,
                            )
                        ]
                    for model_id in module_id.model_ids:
                        if not model_id.it_workspace_ids:
                            model_id.it_workspace_ids = [
                                (
                                    6,
                                    0,
                                    w_ids,
                                )
                            ]
                        for field_id in model_id.field_ids:
                            if not field_id.it_workspace_ids:
                                field_id.it_workspace_ids = [
                                    (
                                        6,
                                        0,
                                        w_ids,
                                    )
                                ]
        return r
