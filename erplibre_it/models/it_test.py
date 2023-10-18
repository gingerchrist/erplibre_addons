import base64
import json
import logging
import os
import subprocess

from odoo import _, api, exceptions, fields, models

_logger = logging.getLogger(__name__)


class ItTest(models.Model):
    _name = "it.test"
    _description = "it_test"

    name = fields.Char()

    is_executed = fields.Boolean()

    debug = fields.Boolean(help="Enable output debug")

    log = fields.Text()

    it_workspace_ids = fields.Many2many(
        comodel_name="it.workspace",
        inverse_name="test_id",
        string="It Workspace",
    )

    @api.multi
    @api.depends("it_workspace_ids")
    def _compute_name(self):
        for rec in self:
            rec.name = f" - ".join(rec.it_workspace_ids.name)

    @api.multi
    def action_run_erplibre_test(self):
        lst_out = []
        for rec in self:
            for it_workspace_id in rec.it_workspace_ids:
                name_cmd = f"test_full_fast"
                if rec.debug:
                    name_cmd += "_debug"
                out = it_workspace_id.execute_to_instance(
                    f"cd {it_workspace_id.path_working_erplibre};make"
                    f" {name_cmd}",
                )
                lst_out.append(out)
            rec.log = "\n".join(lst_out)
            rec.is_executed = True
