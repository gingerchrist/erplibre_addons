from odoo import _, api, fields, models


class ErplibreModeSource(models.Model):
    _name = "erplibre.mode.source"
    _description = "erplibre_mode_source"

    name = fields.Char()

    value = fields.Char()
