from odoo import _, api, exceptions, fields, models, tools


class ITDbImage(models.Model):
    _name = "it.db.image"
    _description = "DB image fast restoration"

    name = fields.Char()
    path = fields.Char()
