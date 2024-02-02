from odoo import _, api, fields, models


class ErplibreModeEnv(models.Model):
    _name = "erplibre.mode.env"
    _description = "erplibre_mode_env"

    name = fields.Char()

    value = fields.Char()
