from odoo import _, api, fields, models


class ErplibreModeVersionBase(models.Model):
    _name = "erplibre.mode.version.base"
    _description = "erplibre_mode_version_base"

    name = fields.Char()

    value = fields.Char()

    is_tag = fields.Boolean(help="Is it a tag from Git?")
