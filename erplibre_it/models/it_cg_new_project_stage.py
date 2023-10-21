# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class ItCgNewProjectStage(models.Model):
    _name = "it.cg.new_project.stage"
    _description = "Stage new project for CG project"
    _order = "sequence, name, id"

    name = fields.Char()

    description = fields.Char()

    sequence = fields.Integer(
        "Sequence",
        default=10,
        help="Used to order new project stages. Lower is better.",
    )

    fold = fields.Boolean(
        "Folded in Pipeline",
        help=(
            "This stage is folded in the kanban view when there are no records"
            " in that stage to display."
        ),
    )
