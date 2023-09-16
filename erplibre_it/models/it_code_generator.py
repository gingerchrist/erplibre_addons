from odoo import _, api, fields, models


class ItCodeGenerator(models.Model):
    _name = "it.code_generator"
    _description = "it_code_generator"

    name = fields.Char()

    it_workspace_id = fields.Many2one(
        comodel_name="it.workspace",
        string="It Workspace",
    )

    module_ids = fields.One2many(
        comodel_name="it.code_generator.module",
        inverse_name="code_generator",
    )

    def action_generate_code(self):
        # Start with local storage
        for rec in self:
            if rec.it_workspace_id:
                module_name = "magasin"
                # cmd = f'./script/code_generator/new_project.py --keep_bd_alive -m gn -d ./addons/TechnoLibre_odoo-code-generator-template --config "{\"model\":[{\"name\":\"membre\",\"fields\":[{\"name\":\"courriel\",\"type\":\"char\"},{\"name\":\"adresse\",\"type\":\"char\"}]},{\"name\":\"personnage\",\"fields\":[{\"name\":\"membre\",\"type\":\"many2one\",\"relation\":\"membre\"},{\"name\":\"point_vie\",\"type\":\"integer\"},{\"name\":\"habilete\",\"type\":\"many2many\",\"relation\":\"habilete\"}]},{\"name\":\"habilete\",\"fields\":[{\"name\":\"nb_xp\",\"type\":\"integer\"}]}]}"'
                cmd = (
                    "cd /ERPLibre;./script/code_generator/new_project.py --keep_bd_alive"
                    f" -m {module_name} -d addons/addons"
                )
                rec.it_workspace_id.exec_docker(cmd)
