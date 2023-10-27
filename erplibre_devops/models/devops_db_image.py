from odoo import _, api, exceptions, fields, models, tools


class DevopsDbImage(models.Model):
    _name = "devops.db.image"
    _description = "DB image fast restoration"

    name = fields.Char()

    path = fields.Char()
