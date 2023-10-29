import base64
import json
import logging
import os
import subprocess

from odoo import _, api, exceptions, fields, models

_logger = logging.getLogger(__name__)


class DevopsTest(models.Model):
    _name = "devops.test"
    _description = "devops_test"

    name = fields.Char()

    is_executed = fields.Boolean()

    debug = fields.Boolean(help="Enable output debug")

    log = fields.Text()

    devops_workspace_ids = fields.Many2many(
        comodel_name="devops.workspace",
        inverse_name="test_id",
        string="DevOps Workspace",
    )

    @api.multi
    @api.depends("devops_workspace_ids")
    def _compute_name(self):
        for rec in self:
            rec.name = f" - ".join(rec.devops_workspace_ids.name)

    @api.multi
    def action_run_erplibre_test(self):
        lst_out = []
        for rec in self:
            for devops_workspace_id in rec.devops_workspace_ids:
                name_cmd = f"test_full_fast"
                if rec.debug:
                    name_cmd += "_debug"
                exec_id = devops_workspace_id.execute(
                    cmd=(
                        f"cd {devops_workspace_id.path_working_erplibre};make"
                        f" {name_cmd}"
                    ),
                    to_instance=True,
                )
                lst_out.append(exec_id.log_all)
            rec.log = "\n".join(lst_out)
            rec.is_executed = True
