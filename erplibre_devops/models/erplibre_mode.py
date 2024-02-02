from odoo import _, api, fields, models


class ErplibreMode(models.Model):
    _name = "erplibre.mode"
    _description = "erplibre_mode"

    name = fields.Char(store=True, compute="_compute_name")

    mode_env = fields.Many2one(comodel_name="erplibre.mode.env", required=True)

    mode_exec = fields.Many2one(
        comodel_name="erplibre.mode.exec", required=True
    )

    mode_source = fields.Many2one(
        comodel_name="erplibre.mode.source", required=True
    )

    mode_version_base = fields.Many2one(
        comodel_name="erplibre.mode.version.base",
        required=True,
        help="Support base version communautaire",
    )

    mode_version_erplibre = fields.Many2one(
        comodel_name="erplibre.mode.version.erplibre",
        required=True,
        help=(
            "Dev to improve, test to test, prod ready for production, stage to"
            " use a dev and replace a prod"
        ),
    )

    @api.multi
    @api.depends(
        "mode_env",
        "mode_exec",
        "mode_source",
        "mode_version_base",
        "mode_version_erplibre",
    )
    def _compute_name(self):
        for rec in self:
            rec.name = (
                "{"
                f"{rec.mode_env.name} "
                f"{rec.mode_exec.name} "
                f"{rec.mode_source.name} "
                f"{rec.mode_version_base.name} "
                f"{rec.mode_version_erplibre.name}"
                "}"
            )
