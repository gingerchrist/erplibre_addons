from odoo import _, api, fields, models


class ErplibreConfigPathHome(models.Model):
    _name = "erplibre.config.path.home"
    _description = "erplibre_config_path_home"

    name = fields.Char()

    def get_path_home_id(self, path_home):
        path_home_id = self.search([("name", "=", path_home)], limit=1)
        if not path_home_id:
            path_home_id = self.create([{"name": path_home}])
        return path_home_id
