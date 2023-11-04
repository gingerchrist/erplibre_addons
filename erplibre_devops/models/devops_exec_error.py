# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class DevopsExecError(models.Model):
    _name = "devops.exec.error"
    _description = "Execution error"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(compute="_compute_name")

    description = fields.Char()

    escaped_tb = fields.Text(help="Traceback")

    active = fields.Boolean(default=True)

    devops_workspace = fields.Many2one(
        comodel_name="devops.workspace", readonly=True
    )

    partner_ids = fields.Many2many(comodel_name="res.partner")

    channel_ids = fields.Many2many(comodel_name="mail.channel")

    type_error = fields.Selection(
        selection=[("internal", "Internal"), ("execution", "Execution")]
    )

    line_file_tb_detected = fields.Char(
        help="Detected line to add breakpoint."
    )

    devops_exec_ids = fields.Many2one(
        comodel_name="devops.exec",
        readonly=True,
    )

    devops_exec_bundle_id = fields.Many2one(
        comodel_name="devops.exec.bundle",
        readonly=True,
    )

    parent_root_exec_bundle_id = fields.Many2one(
        comodel_name="devops.exec.bundle",
        readonly=True,
    )

    find_resolution = fields.Selection(
        selection=[
            ("find", "Find"),
            ("error", "Error"),
            ("diagnostic", "Diagnostic"),
        ],
        help="If resolution to resolv the error was found.",
    )

    diagnostic_idea = fields.Text(help="Auto correction try to diagnostic.")

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        for rec in result:
            # ERROR, cannot support error into error if generate error, each error will generate error
            # with rec.devops_workspace.devops_create_exec_bundle(
            #         "Create exec error"
            # ) as rec_ws:
            #     raise Exception("test error into error, no infinity")
            rec.message_post(  # pylint: disable=translation-required
                body="<p>%s</p><pre>%s</pre>"
                % (
                    _("devops.workspace '%s' failed.") % rec.description,
                    rec.escaped_tb,
                ),
                subtype=self.env.ref(
                    "erplibre_devops.mail_message_subtype_failure"
                ),
                author_id=self.env.ref("base.user_root").partner_id.id,
                partner_ids=[(6, 0, rec.partner_ids.ids)],
                channel_ids=[(6, 0, rec.channel_ids.ids)],
            )
            rec.devops_workspace.ide_pycharm.action_cg_setup_pycharm_debug(
                log=rec.escaped_tb.replace("&quot;", '"'), exec_error_id=rec
            )
        return result

    @api.depends(
        "devops_workspace",
    )
    def _compute_name(self):
        for rec in self:
            if not isinstance(rec.id, models.NewId):
                rec.name = f"{rec.id:03d}"
            else:
                rec.name = ""
            # rec.name += f"workspace {rec.devops_workspace.id}"
            if rec.description:
                rec.name += f" '{rec.description}'"

    @api.multi
    def action_reboot_force_os_workspace(self):
        self.ensure_one()
        self.devops_workspace.with_context(
            default_exec_reboot_process=True
        ).action_reboot()

    @api.multi
    def action_kill_workspace(self):
        self.ensure_one()
        self.devops_workspace.action_stop()

    @api.multi
    def action_kill_pycharm(self):
        self.ensure_one()
        self.devops_workspace.ide_pycharm.action_kill_pycharm()

    @api.multi
    def action_start_pycharm(self):
        self.ensure_one()
        self.devops_workspace.ide_pycharm.action_start_pycharm()

    @api.multi
    def action_set_breakpoint_pycharm(self):
        for rec_o in self:
            with rec_o.devops_workspace.devops_create_exec_bundle(
                "Set breakpoint on error"
            ) as rec:
                rec.ide_pycharm.action_cg_setup_pycharm_debug(
                    log=rec_o.escaped_tb.replace(
                        "&quot;", '"', exec_error_id=rec
                    )
                )
