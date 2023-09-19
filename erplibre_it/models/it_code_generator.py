from odoo import _, api, fields, models
import json


class ItCodeGenerator(models.Model):
    _name = "it.code_generator"
    _description = "it_code_generator"

    name = fields.Char()

    # TODO need to be a many2many to execute on multiple platform (or only share the result ;-))
    # TODO if share result, do a command to copy file all and recreate it like a mirror on other workspace
    it_workspace_id = fields.Many2one(
        comodel_name="it.workspace",
        string="It Workspace",
    )

    # TODO create boolean cache with default workspace to work for the other
    default_workspace_master = fields.Many2one(
        comodel_name="it.workspace",
        string="It Workspace default",
    )

    module_ids = fields.One2many(
        comodel_name="it.code_generator.module",
        inverse_name="code_generator",
    )

    def action_generate_code(self):
        # TODO add try catch, add breakpoint, rerun loop. Careful when lose context
        # Start with local storage
        for rec in self:
            if rec.it_workspace_id:
                if not rec.module_ids:
                    continue
                module_id = rec.module_ids[0]
                # Support only 1, but can run in parallel multiple if no dependencies between
                module_name = module_id.name
                lst_model = []
                dct_model_conf = {"model": lst_model}
                for model_id in module_id.model_ids:
                    lst_field = []
                    lst_model.append(
                        {"name": model_id.name, "fields": lst_field}
                    )
                    # TODO missing support relation many2one many2many one2many
                    # TODO missing support related field
                    for field_id in model_id.field_ids:
                        dct_value_field = {
                            "name": field_id.name,
                            "help": field_id.help,
                            "type": field_id.type,
                        }
                        if field_id.widget:
                            dct_value_field = field_id.widget
                        lst_field.append(dct_value_field)
                # TODO option clean all repository before
                model_conf = json.dumps(dct_model_conf).replace('"', '\\"')
                extra_arg = ""
                if model_conf:
                    extra_arg = f" --config '{model_conf}'"
                cmd = (
                    "cd /ERPLibre;./script/code_generator/new_project.py"
                    f" --keep_bd_alive -m {module_name} -d"
                    f" addons/addons{extra_arg}"
                )
                rec.it_workspace_id.exec_docker(cmd)
                # TODO option install continuous or stop execution
