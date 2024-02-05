from odoo import _, api, fields, models


class ErplibreModeVersionErplibre(models.Model):
    _name = "erplibre.mode.version.erplibre"
    _description = "erplibre_mode_version_erplibre"

    name = fields.Char()

    value = fields.Char()

    is_tag = fields.Boolean(help="Is it a tag from Git?")
