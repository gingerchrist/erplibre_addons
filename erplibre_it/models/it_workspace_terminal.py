# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging
import os
import time

import requests

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class ItWorkspaceTerminal(models.Model):
    _name = "it.workspace.terminal"
    _description = "ERPLibre IT Workspace Terminal"

    name = fields.Char(readonly=True, compute="_compute_name", store=True)

    workspace_id = fields.Many2one("it.workspace")

    terminal_is_running = fields.Boolean(
        readonly=True,
        help="When false, it's because not running terminal.",
        default=True,
    )

    terminal_initiate_succeed = fields.Boolean(
        help="Terminal is ready to run", default=False
    )

    has_error_restore_db = fields.Boolean()

    @api.multi
    @api.depends("workspace_id", "terminal_is_running")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.workspace_id.name} - {rec.terminal_is_running}"

    @api.multi
    def action_it_check_all(self):
        pass
