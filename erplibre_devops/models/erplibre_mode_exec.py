from odoo import _, api, fields, models


class ErplibreModeExec(models.Model):
    _name = "erplibre.mode.exec"
    _description = "erplibre_mode_exec"

    name = fields.Char()

    active = fields.Boolean(default=True)

    value = fields.Char()
