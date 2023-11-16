# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class DevopsExec(models.Model):
    _name = "devops.exec"
    _description = "Execution process"

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )

    active = fields.Boolean(default=True)

    exec_start_date = fields.Datetime(
        string="Execution start date",
        default=fields.Datetime.now,
        readonly=True,
    )

    exec_stop_date = fields.Datetime(
        string="Execution stop date", readonly=True
    )

    exec_time_duration = fields.Integer(
        string="Execution time duration",
        compute="_compute_exec_time_duration",
        store=True,
        help="Time in second, duration of execution",
    )

    cmd = fields.Char(readonly=True)

    folder = fields.Char(readonly=True)

    time_duration_result = fields.Char(
        compute="_compute_time_duration_result",
        store=True,
    )

    execution_finish = fields.Boolean(
        compute="_compute_execution_finish",
        store=True,
    )

    module = fields.Char()

    new_project_id = fields.Many2one(comodel_name="devops.cg.new_project")

    devops_workspace = fields.Many2one(
        comodel_name="devops.workspace", readonly=True
    )

    devops_exec_error_ids = fields.One2many(
        comodel_name="devops.exec.error",
        inverse_name="devops_exec_id",
        string="Executions errors",
        readonly=True,
    )

    devops_exec_bundle_id = fields.Many2one(
        comodel_name="devops.exec.bundle", readonly=True
    )

    log_stdin = fields.Text(readonly=True)

    log_stdout = fields.Text(readonly=True)

    log_stderr = fields.Text(readonly=True)

    log_all = fields.Text(
        compute="_compute_log_all",
        store=True,
    )

    log_error = fields.Text()

    log_warning = fields.Text()

    @api.depends(
        "devops_workspace",
        "module",
        "time_duration_result",
        "execution_finish",
    )
    def _compute_name(self):
        for rec in self:
            if not isinstance(rec.id, models.NewId):
                rec.name = f"{rec.id}: "
            else:
                rec.name = ""
            rec.name += f"workspace {rec.devops_workspace.id}"
            if rec.module:
                rec.name += f" - {rec.module}"

    @api.depends("exec_start_date", "exec_stop_date")
    def _compute_exec_time_duration(self):
        for rec in self:
            if rec.exec_start_date and rec.exec_stop_date:
                rec.exec_time_duration = (
                    rec.exec_stop_date - rec.exec_start_date
                ).total_seconds()
            else:
                rec.exec_time_duration = False

    @api.depends("log_stdout", "log_stderr")
    def _compute_log_all(self):
        for rec in self:
            rec.log_all = ""
            if rec.log_stdout:
                rec.log_all += rec.log_stdout
            if rec.log_stderr:
                rec.log_all += rec.log_stderr
            # extract error/warning
            lst_error = []
            lst_warning = []
            lst_item_ignore_error = [
                "fetchmail_notify_error_to_sender",
                "odoo.sql_db: bad query: ALTER TABLE \"db_backup\" DROP CONSTRAINT \"db_backup_db_backup_name_unique\"",
                "ERROR: constraint \"db_backup_db_backup_name_unique\" of relation \"db_backup\" does not exist",
                "odoo.sql_db: bad query: ALTER TABLE \"db_backup\" DROP CONSTRAINT \"db_backup_db_backup_days_to_keep_positive\"",
                "ERROR: constraint \"db_backup_db_backup_days_to_keep_positive\" of relation \"db_backup\" does not exist",
                "odoo.addons.code_generator.extractor_module_file: Ignore next error about ALTER TABLE DROP CONSTRAINT.",
                "Storing computed values of devops.code_generator.module.model.field.has_error",
                "Storing computed values of devops.exec.error.name",
                "Storing computed values of devops.workspace.devops_exec_error_count",
                "loading erplibre_devops/views/devops_exec_error.xml",
            ]
            lst_item_ignore_warning = [
                "have the same label:",
                "odoo.addons.code_generator.extractor_module_file: Ignore next error about ALTER TABLE DROP CONSTRAINT."
            ]
            for line in rec.log_all.split("\n"):
                if "error" in line or "ERROR" in line:
                    for ignore_item in lst_item_ignore_error:
                        if ignore_item in line:
                            break
                    else:
                        lst_error.append(line)
                if "warning" in line or "WARNING" in line:
                    for ignore_item in lst_item_ignore_warning:
                        if ignore_item in line:
                            break
                    else:
                        lst_warning.append(line)
            rec.log_error = "\n".join(lst_error)
            rec.log_warning = "\n".join(lst_warning)

    @api.depends("exec_stop_date")
    def _compute_execution_finish(self):
        for rec in self:
            rec.execution_finish = bool(rec.exec_stop_date)

    @api.depends("exec_time_duration")
    def _compute_time_duration_result(self):
        for rec in self:
            rec.time_duration_result = (
                f" {'{:0>8}'.format(str(timedelta(seconds=rec.exec_time_duration)))}"
            )
