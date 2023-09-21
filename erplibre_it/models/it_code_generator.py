from odoo import _, api, exceptions, fields, models
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

    force_clean_before_generate = fields.Boolean(
        help="Will remove all modules to generate news."
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
                    for field_id in model_id.field_ids:
                        dct_value_field = {
                            "name": field_id.name,
                            "help": field_id.help,
                            "type": field_id.type,
                        }
                        if field_id.type in [
                            "many2one",
                            "many2many",
                            "one2many",
                        ]:
                            dct_value_field["relation"] = (
                                field_id.relation.name
                                if field_id.relation
                                else field_id.relation_manual
                            )
                            if not dct_value_field["relation"]:
                                msg_err = (
                                    f"Model '{model_id.name}', field"
                                    f" '{field_id.name}' need a relation"
                                    f" because type is '{field_id.type}'"
                                )
                                raise exceptions.Warning(msg_err)
                        if field_id.type in [
                            "one2many",
                        ]:
                            dct_value_field["relation_field"] = (
                                field_id.field_relation.name
                                if field_id.field_relation
                                else field_id.field_relation_manual
                            )
                            if not dct_value_field["relation_field"]:
                                msg_err = (
                                    f"Model '{model_id.name}', field"
                                    f" '{field_id.name}' need a relation field"
                                    f" because type is '{field_id.type}'"
                                )
                                raise exceptions.Warning(msg_err)
                        if field_id.widget:
                            dct_value_field = field_id.widget
                        lst_field.append(dct_value_field)
                if rec.force_clean_before_generate:
                    rec.action_clear_all_code()
                model_conf = (
                    json.dumps(dct_model_conf)
                    .replace('"', '\\"')
                    .replace("'", "")
                )
                extra_arg = ""
                if model_conf:
                    extra_arg = f" --config '{model_conf}'"
                cmd = (
                    "cd /ERPLibre;./script/code_generator/new_project.py"
                    f" --keep_bd_alive -m {module_name} -d"
                    f" addons/addons{extra_arg}"
                )
                result = rec.it_workspace_id.exec_docker(cmd)
                rec.it_workspace_id.it_code_generator_log_addons = result
                # TODO option install continuous or stop execution

    def action_clear_all_code(self):
        for rec in self:
            for module_id in rec.module_ids:
                rec.it_workspace_id.exec_docker(
                    f"cd /ERPLibre/addons/addons;rm -rf ./{module_id.name};"
                )
                rec.it_workspace_id.exec_docker(
                    "cd /ERPLibre/addons/addons;rm -rf"
                    f" ./code_generator_template_{module_id.name};"
                )
                rec.it_workspace_id.exec_docker(
                    "cd /ERPLibre/addons/addons;rm -rf"
                    f" ./code_generator_{module_id.name};"
                )

    def action_git_commit_all_code(self):
        for rec in self:
            # Validate git directory exist
            result = rec.it_workspace_id.exec_docker(
                f"ls /ERPLibre/addons/addons/.git"
            )
            if not result:
                # Suppose git not exist
                # This is not good if .git directory is in parent directory
                result = rec.it_workspace_id.exec_docker(
                    f"cd /ERPLibre/addons/addons;git init"
                )
            result = rec.it_workspace_id.exec_docker(
                f"cd /ERPLibre/addons/addons;git status -s"
            )
            if result:
                # Force add file and commit
                result = rec.it_workspace_id.exec_docker(
                    f"cd /ERPLibre/addons/addons;git add ."
                )
                result = rec.it_workspace_id.exec_docker(
                    f"cd /ERPLibre/addons/addons;git commit -m 'Commit by"
                    f" RobotLibre'"
                )

    def git_status_all_code(self):
        diff = ""
        for rec in self:
            # Validate git directory exist
            result = rec.it_workspace_id.exec_docker(
                f"ls /ERPLibre/addons/addons/.git"
            )
            if result:
                result = rec.it_workspace_id.exec_docker(
                    f"cd /ERPLibre/addons/addons;git status"
                )
                if result:
                    diff += result
        return diff

    def git_diff_all_code(self):
        diff = ""
        for rec in self:
            # Validate git directory exist
            result = rec.it_workspace_id.exec_docker(
                f"ls /ERPLibre/addons/addons/.git"
            )
            if result:
                result = rec.it_workspace_id.exec_docker(
                    f"cd /ERPLibre/addons/addons;git diff"
                )
                if result:
                    diff += result
        return diff

    def git_stat_all_code(self):
        diff = ""
        for rec in self:
            for module_id in rec.module_ids:
                result = rec.it_workspace_id.exec_docker(
                    "cd /ERPLibre;./script/statistic/code_count.sh"
                    f" ./addons/addons/{module_id.name};"
                )
                if result:
                    diff += f" ./addons/addons/{module_id.name}"
                    diff += result
                result = rec.it_workspace_id.exec_docker(
                    "cd /ERPLibre;./script/statistic/code_count.sh"
                    f" ./addons/addons/code_generator_template_{module_id.name};"
                )
                if result:
                    diff += (
                        f" ./addons/addons/code_generator_template_{module_id.name}"
                    )
                    diff += result
                result = rec.it_workspace_id.exec_docker(
                    "cd /ERPLibre;./script/statistic/code_count.sh"
                    f" ./addons/addons/code_generator_{module_id.name};"
                )
                if result:
                    diff += f" ./addons/addons/code_generator_{module_id.name}"
                    diff += result
        return diff
