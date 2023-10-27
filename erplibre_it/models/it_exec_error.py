# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class ItExecError(models.Model):
    _name = "it.exec.error"
    _description = "Execution error"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(compute="_compute_name")

    description = fields.Char()

    escaped_tb = fields.Text(help="Traceback")

    active = fields.Boolean(default=True)

    it_workspace = fields.Many2one(comodel_name="it.workspace", readonly=True)

    partner_ids = fields.Many2many(comodel_name="res.partner")

    channel_ids = fields.Many2many(comodel_name="mail.channel")

    it_exec_ids = fields.Many2one(
        comodel_name="it.exec",
        readonly=True,
    )

    it_exec_bundle_ids = fields.Many2one(
        comodel_name="it.exec.bundle",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        for rec in result:
            rec.message_post(  # pylint: disable=translation-required
                body="<p>%s</p><pre>%s</pre>"
                % (
                    _("it.workspace '%s' failed.") % rec.description,
                    rec.escaped_tb,
                ),
                subtype=self.env.ref(
                    "erplibre_it.mail_message_subtype_failure"
                ),
                author_id=self.env.ref("base.user_root").partner_id.id,
                partner_ids=[(6, 0, rec.partner_ids.ids)],
                channel_ids=[(6, 0, rec.channel_ids.ids)],
            )
        return result

    @api.depends(
        "it_workspace",
    )
    def _compute_name(self):
        for rec in self:
            if not isinstance(rec.id, models.NewId):
                rec.name = f"{rec.id:03d}"
            else:
                rec.name = ""
            # rec.name += f"workspace {rec.it_workspace.id}"
            if rec.description:
                rec.name += f" '{rec.description}'"

    @api.multi
    def action_kill_pycharm(self):
        self.ensure_one()
        cmd = "pkill -f $(ps aux | grep pycharm | grep -v grep | grep bin/java | awk '{print $11}')"
        self.it_workspace.system_id.execute_process(cmd)

    @api.multi
    def action_start_pycharm(self):
        self.ensure_one()
        cmd = "~/.local/share/JetBrains/Toolbox/scripts/pycharm"
        self.it_workspace.system_id.execute_terminal_gui("", cmd=cmd)

    @api.multi
    def action_set_breakpoint_pycharm(self):
        for rec_o in self:
            with rec_o.it_workspace.it_create_exec_bundle(
                "Set breakpoint on error"
            ) as rec:
                if not rec.ide_pycharm:
                    rec.ide_pycharm = self.env["it.ide.pycharm"].create(
                        {"it_workspace": rec.id}
                    )
                rec.ide_pycharm.action_cg_setup_pycharm_debug(
                    log=rec_o.escaped_tb.replace("&quot;", '"')
                )
