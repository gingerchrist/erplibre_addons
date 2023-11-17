# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class DevopsLogWarning(models.Model):
    _name = "devops.log.warning"
    _description = "Log warning"

    name = fields.Char()

    exec_id = fields.Many2one(comodel_name="devops.exec", readonly=True)

    new_project_id = fields.Many2one(comodel_name="devops.cg.new_project")
