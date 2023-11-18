# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class DevopsIdePycharmConfiguration(models.Model):
    _name = "devops.ide.pycharm.configuration"
    _description = "Pycharm management configuration for a workspace"
    _order = "id desc"

    name = fields.Char()

    command = fields.Char()

    group = fields.Char()

    is_default = fields.Boolean()

    devops_workspace_id = fields.Many2one(
        comodel_name="devops.workspace",
        string="Devops Workspace",
        required=True,
    )

    devops_cg_new_project_id = fields.Many2one(
        comodel_name="devops.cg.new_project",
        string="Devops Cg New Project",
    )

    devops_ide_pycharm = fields.Many2one(comodel_name="devops.ide.pycharm")
