from odoo import _, api, fields, models


class DevopsTestResult(models.Model):
    _name = "devops.test.result"
    _description = "devops_test_result"

    name = fields.Char()

    active = fields.Boolean(default=True)

    log = fields.Text(readonly=True)

    is_finish = fields.Boolean(readonly=True)

    is_pass = fields.Boolean(readonly=True)

    test_case_exec_id = fields.Many2one(
        comodel_name="devops.test.case.exec",
        string="Test Case Exec",
    )

    test_plan_exec_id = fields.Many2one(
        comodel_name="devops.test.plan.exec",
        string="Plan",
        related="test_case_exec_id.test_plan_exec_id",
        readonly=True,
    )

    workspace_id = fields.Many2one(related="test_plan_exec_id.workspace_id")
