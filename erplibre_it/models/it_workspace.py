# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json
import logging
import os
import re
import shutil
import time
import traceback
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta
from glob import iglob
import xmltodict

import paramiko
import requests

from odoo import _, api, exceptions, fields, models, tools
from odoo.service import db

_logger = logging.getLogger(__name__)
try:
    import pysftp
except ImportError:  # pragma: no cover
    _logger.debug("Cannot import pysftp")


class ItWorkspace(models.Model):
    _name = "it.workspace"
    _inherit = "mail.thread"
    _description = "ERPLibre IT Workspace"

    # _sql_constraints = [
    # ("name_unique", "UNIQUE(name)", "Cannot duplicate a configuration."),
    # (
    # "days_to_keep_positive",
    # "CHECK(days_to_keep >= 0)",
    # "I cannot remove it_workspaces from the future. Ask Doc for that.",
    # ),
    # ]
    name = fields.Char(
        compute="_compute_name",
        store=True,
        help="Summary of this it_workspace process",
    )

    it_workspace_format = fields.Selection(
        selection=[
            ("zip", "zip (includes filestore)"),
            ("dump", "pg_dump custom format (without filestore)"),
        ],
        default="zip",
        help="Choose the format for this it_workspace.",
    )

    log_workspace = fields.Text()

    docker_compose_ps = fields.Text()

    docker_version = fields.Char(default="technolibre/erplibre:1.5.0_c0c6f23")

    docker_cmd_extra = fields.Char(
        help="Extra command to share to odoo executable", default=""
    )

    docker_nb_proc = fields.Integer(
        help=(
            "Number of processor/thread, 0 if not behind a proxy, else 2 or"
            " more."
        ),
        default=0,
    )

    docker_config_gen_cg = fields.Boolean(
        default=False,
        help="Will reduce config path to improve speed to code generator",
    )

    docker_config_cache = fields.Char(
        help="Fill when docker_config_gen_cg is True, will be erase after",
    )

    docker_is_behind_proxy = fields.Boolean(
        help="Longpolling need a proxy when workers > 1", default=False
    )

    docker_initiate_succeed = fields.Boolean(
        help="Docker is ready to run", default=False
    )

    need_debugger_cg_erplibre_it = fields.Boolean(
        help="CG erplibre_it got error, detect can use the debugger",
        default=False,
    )

    path_code_generator_to_generate = fields.Char(
        default="addons/addons", help=""
    )

    path_working_erplibre = fields.Char(default="/ERPLibre", help="")

    is_installed = fields.Boolean(
        help="Need to install environnement before execute it."
    )

    folder = fields.Char(
        required=True,
        default=lambda self: self._default_folder(),
        help="Absolute path for storing the it_workspaces",
    )

    system_id = fields.Many2one(
        "it.system",
        required=True,
        default=lambda self: self.env.ref(
            "erplibre_it.it_system_local", raise_if_not_found=False
        ),
    )

    # TODO backup button and restore button

    port_http = fields.Integer(
        string="port http",
        default=8069,
        help="The port of http odoo.",
    )

    is_self_instance = fields.Boolean(
        default=False, help="Is the instance who run this database"
    )

    port_longpolling = fields.Integer(
        string="port longpolling",
        default=8071,
        help="The port of longpolling odoo.",
    )

    db_name = fields.Char(string="DB instance name", default="test")

    db_is_restored = fields.Boolean(
        readonly=True, help="When false, it's because actually restoring a DB."
    )

    docker_is_running = fields.Boolean(
        readonly=True, help="When false, it's because not running docker."
    )

    url_instance = fields.Char()

    url_instance_database_manager = fields.Char()

    it_code_generator_ids = fields.Many2many(
        comodel_name="it.code_generator",
        inverse_name="it_workspace_id",
        string="Project",
    )

    it_code_generator_module_ids = fields.Many2many(
        comodel_name="it.code_generator.module",
        # related="it_code_generator_ids.module_ids",
        string="Module",
        readonly=False,
    )

    it_code_generator_model_ids = fields.Many2many(
        # related="it_code_generator_module_ids.model_ids",
        comodel_name="it.code_generator.module.model",
        string="Model",
        readonly=False,
    )

    it_code_generator_field_ids = fields.Many2many(
        # related="it_code_generator_model_ids.field_ids",
        comodel_name="it.code_generator.module.model.field",
        string="Field",
        readonly=False,
    )

    # it_code_generator_finish_compute = fields.Boolean(
    #     store=True, compute="_compute_it_code_generator_finish_compute"
    # )

    it_code_generator_tree_addons = fields.Text(
        string="Tree addons",
        help="Will show generated files from code generator or humain",
    )

    it_code_generator_diff = fields.Text(
        string="Diff addons",
        help="Will show diff git",
    )

    it_code_generator_status = fields.Text(
        string="Status addons",
        help="Will show status git",
    )

    it_code_generator_stat = fields.Text(
        string="Stat addons",
        help="Will show statistique code",
    )

    it_code_generator_log_addons = fields.Text(
        string="Log code generator",
        help="Will show code generator log, last execution",
    )

    it_cg_erplibre_it_log = fields.Text(
        string="Log CG erplibre_it new_project",
        help=(
            "Will show code generator log for new project erplibr_it, last"
            " execution"
        ),
        readonly=True,
    )

    it_cg_erplibre_it_error_log = fields.Text(
        string="Error CG erplibre_it new_project",
        help=(
            "Will show code generator error for new project erplibr_it, last"
            " execution"
        ),
        readonly=True,
    )

    force_create_docker_compose = fields.Boolean(
        default=True,
        help="Recreate docker-compose from configuration.",
    )

    time_exec_action_code_generator_generate_all = fields.Char(
        readonly=True,
        help="Execution time of method action_code_generator_generate_all",
    )

    time_exec_action_cg_erplibre_it = fields.Char(
        readonly=True,
        help="Execution time of method action_cg_erplibre_it",
    )

    mode_exec = fields.Selection(
        selection=[("docker", "Docker"), ("git", "Git")], default="docker"
    )

    mode_environnement = fields.Selection(
        selection=[
            ("dev", "Dev"),
            ("test", "Test"),
            ("prod", "Prod"),
            ("stage", "Stage"),
        ],
        default="test",
        help=(
            "Dev to improve, test to test, prod ready for production, stage to"
            " use a dev and replace a prod"
        ),
    )

    mode_version_erplibre = fields.Selection(
        selection=[
            ("1.5.0", "1.5.0"),
            ("master", "Master"),
            ("develop", "Develop"),
        ],
        default="1.5.0",
        help=(
            "Dev to improve, test to test, prod ready for production, stage to"
            " use a dev and replace a prod"
        ),
    )

    mode_version_base = fields.Selection(
        selection=[("12.0", "12.0"), ("14.0", "14.0")],
        default="12.0",
        help="Support base version communautaire",
    )

    git_branch = fields.Char("Git branch")

    git_url = fields.Char(
        "Git URL", default="https://github.com/ERPLibre/ERPLibre"
    )

    time_exec_action_clear_all_generated_module = fields.Char(
        readonly=True,
        help="Execution time of method action_clear_all_generated_module",
    )

    time_exec_action_install_all_generated_module = fields.Char(
        readonly=True,
        help="Execution time of method action_install_all_generated_module",
    )

    time_exec_action_install_all_uca_generated_module = fields.Char(
        readonly=True,
        help=(
            "Execution time of method action_install_all_uca_generated_module"
        ),
    )

    time_exec_action_install_all_ucb_generated_module = fields.Char(
        readonly=True,
        help=(
            "Execution time of method action_install_all_ucb_generated_module"
        ),
    )

    time_exec_action_install_and_generate_all_generated_module = fields.Char(
        readonly=True,
        help=(
            "Execution time of method"
            " action_install_and_generate_all_generated_module"
        ),
    )

    time_exec_action_refresh_meta_cg_generated_module = fields.Char(
        readonly=True,
        help=(
            "Execution time of method action_refresh_meta_cg_generated_module"
        ),
    )

    time_exec_action_git_commit_all_generated_module = fields.Char(
        readonly=True,
        help="Execution time of method action_git_commit_all_generated_module",
    )

    def _default_image_db_selection(self):
        return self.env["it.db.image"].search(
            [("name", "like", "erplibre_base")], limit=1
        )

    image_db_selection = fields.Many2one(
        comodel_name="it.db.image", default=_default_image_db_selection
    )

    @api.model
    def _default_folder(self):
        return os.getcwd()

    @api.multi
    @api.depends("folder")
    def _compute_name(self):
        """Get the right summary for this job."""
        for rec in self:
            rec.name = rec.folder

    @api.multi
    @api.depends("folder", "system_id")
    def _compute_is_installed(self):
        for rec in self:
            # TODO validate installation is done before
            rec.is_installed = False

    def update_docker_compose_ps(self):
        for rec in self:
            with rec.it_workspace_log():
                if rec.mode_exec in ["docker"]:
                    result = rec.system_id.execute_with_result(
                        f"cd {rec.folder};docker compose ps"
                    )
                    rec.docker_compose_ps = f"\n{result}"

    @api.multi
    def action_stop_docker_compose(self):
        for rec in self:
            with rec.it_workspace_log():
                if rec.mode_exec in ["docker"]:
                    rec.system_id.execute_with_result(
                        f"cd {rec.folder};docker compose down"
                    )
        self.update_docker_compose_ps()
        self.action_docker_check_docker_ps()

    @api.multi
    def action_docker_status(self):
        for rec in self:
            with rec.it_workspace_log():
                result = rec.system_id.execute_with_result(
                    f"cd {rec.folder};docker compose ps"
                )
                rec.docker_compose_ps = f"\n{result}"

    @api.multi
    def action_cg_erplibre_it(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                rec.it_cg_erplibre_it_error_log = False
                # rec.need_debugger_cg_erplibre_it = False
                addons_path = "./addons/ERPLibre_erplibre_addons"
                module_name = "erplibre_it"
                new_project_id = self.env["it.cg.new_project"].create(
                    {
                        "module": module_name,
                        "directory": addons_path,
                        "it_workspace": rec.id,
                    }
                )
                new_project_id.action_new_project()
                # result = rec.system_id.execute_with_result(
                #     f"cd {rec.folder};./script/code_generator/new_project.py"
                #     f" -d {addons_path} -m {module_name}",
                # )
                result = ""
                rec.it_cg_erplibre_it_log = result
                index_error = result.rfind("odoo.exceptions.ValidationError")
                if index_error >= 0:
                    rec.it_cg_erplibre_it_error_log = result[
                        index_error : result.find("\n", index_error)
                    ]
                    rec.need_debugger_cg_erplibre_it = True

                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_cg_erplibre_it = f"{td:.03f}s"

    @api.multi
    def action_cg_setup_pycharm_debug(self):
        for rec in self:
            with rec.it_workspace_log():
                index_error = rec.it_cg_erplibre_it_log.rfind(
                    "odoo.exceptions.ValidationError"
                )
                search_path = (
                    "File"
                    f' "{os.path.normpath(os.path.join(rec.folder, "./addons"))}'
                )
                no_last_file_error = rec.it_cg_erplibre_it_log.rfind(
                    search_path, 0, index_error
                )
                no_end_line_error = rec.it_cg_erplibre_it_log.find(
                    "\n", no_last_file_error
                )
                error_line = rec.it_cg_erplibre_it_log[
                    no_last_file_error:no_end_line_error
                ]
                # Detect no line
                regex = r"line (\d+),"
                result_regex = re.search(regex, error_line)
                line_breakpoint = None
                if result_regex:
                    line_breakpoint = int(result_regex.group(1))
                # Detect filepath
                regex = r'File "(.*?)"'
                result_regex = re.search(regex, error_line)
                filepath_breakpoint = None
                if result_regex:
                    filepath_breakpoint = result_regex.group(1)
                if line_breakpoint is None or filepath_breakpoint is None:
                    _logger.error("Cannot find breakpoint information")
                    continue
                # -1 to line because start 0, but show 1
                dct_config_breakpoint = {
                    "@enabled": "true",
                    "@suspend": "THREAD",
                    "@type": "python-line",
                    "url": filepath_breakpoint.replace(
                        rec.folder, "file://$PROJECT_DIR$/"
                    ),
                    "line": str(line_breakpoint - 1),
                    # "option": {"@name": "timeStamp", "@value": "104"},
                }
                self._add_breakpoint(rec.folder, dct_config_breakpoint)

    def _add_breakpoint(self, folder_name, dct_config_breakpoint):
        workspace_xml_path = os.path.join(
            folder_name, ".idea", "workspace.xml"
        )
        with open(workspace_xml_path) as xml:
            xml_as_string = xml.read()
            dct_project_xml = xmltodict.parse(xml_as_string)

        # Add a line-breakpoint
        project = dct_project_xml.get("project")
        if not project:
            _logger.error(f"Cannot find <project> into {workspace_xml_path}")
            return
        component = project.get("component")
        if not component:
            _logger.error(f"Cannot find <component> into {workspace_xml_path}")
            return
        for x_debug_manager in component:
            if x_debug_manager.get("@name") == "XDebuggerManager":
                break
        else:
            _logger.error(
                f"Cannot find <XDebuggerManager> into {workspace_xml_path}"
            )
            return

        has_update = False
        breakpoints = None
        breakpoint_manager = x_debug_manager.get("breakpoint-manager")
        if not breakpoint_manager:
            x_debug_manager["breakpoint-manager"] = {
                "breakpoints": {"line-breakpoint": dct_config_breakpoint}
            }
            has_update = True

        if not has_update:
            breakpoints = breakpoint_manager.get("breakpoints")
            if not breakpoints:
                breakpoint_manager["breakpoints"] = {
                    "line-breakpoint": dct_config_breakpoint
                }
                has_update = True

        if not has_update:
            line_breakpoint = breakpoints.get("line-breakpoint")
            # line_breakpoint can be dict or list
            if type(line_breakpoint) is dict:
                line_breakpoint = [line_breakpoint]
                breakpoints["line-breakpoint"] = line_breakpoint

            config_exist = False
            if type(line_breakpoint) is list:
                for a_line_bp in line_breakpoint:
                    if a_line_bp.get("url") == dct_config_breakpoint.get(
                        "url"
                    ) and a_line_bp.get("line") == dct_config_breakpoint.get(
                        "line"
                    ):
                        config_exist = True
                if not config_exist:
                    breakpoints["line-breakpoint"].append(
                        dct_config_breakpoint
                    )
                    has_update = True
            else:
                breakpoints["line-breakpoint"] = dct_config_breakpoint
                has_update = True

        # Write modification
        if has_update:
            xml_format = xmltodict.unparse(
                dct_project_xml, pretty=True, indent="  "
            )
            with open(workspace_xml_path, mode="w") as xml:
                xml.write(xml_format)
            # TODO format with prettier
            # subprocess.call(
            #     "prettier --tab-width 2 --print-width 999999 --write"
            #     f" '{xml_format}'",
            #     shell=True,
            # )
            _logger.info(f"Write file '{workspace_xml_path}'")

    @api.multi
    def action_open_terminal_path_erplibre_it(self):
        for rec in self:
            with rec.it_workspace_log():
                folder_path = os.path.join(
                    rec.folder, "addons", "ERPLibre_erplibre_addons"
                )
                rec.system_id.execute_gnome_terminal(folder_path)

    @api.multi
    def action_docker_check_docker_ps(self):
        for rec in self:
            with rec.it_workspace_log():
                result = rec.system_id.execute_with_result(
                    f"cd {rec.folder};docker compose ps --format json"
                )
                # rec.docker_compose_ps = f"\n{result}"
                rec.docker_is_running = result

    @api.multi
    def action_docker_check_docker_tree_addons(self):
        for rec in self:
            with rec.it_workspace_log():
                result = rec.system_id.execute_with_result(
                    f"cd {rec.folder};tree"
                )
                rec.it_code_generator_tree_addons = result

    @api.multi
    def action_code_generator_generate_all(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                # TODO add try catch, add breakpoint, rerun loop. Careful when lose context
                # Start with local storage
                # Increase speed
                # TODO keep old configuration of config.conf and not overwrite all
                # rec.system_id.exec_docker(f"cd {rec.path_working_erplibre};make config_gen_code_generator", rec.folder)
                if rec.it_code_generator_ids:
                    rec.action_stop_docker_compose()
                    rec.docker_config_gen_cg = True
                    rec.action_start_docker_compose()
                    rec.docker_config_gen_cg = False
                for rec_cg in rec.it_code_generator_ids:
                    for module_id in rec_cg.module_ids:
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
                                            f" '{field_id.name}' need a"
                                            " relation because type is"
                                            f" '{field_id.type}'"
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
                                            f" '{field_id.name}' need a"
                                            " relation field because type is"
                                            f" '{field_id.type}'"
                                        )
                                        raise exceptions.Warning(msg_err)
                                if field_id.widget:
                                    dct_value_field = field_id.widget
                                lst_field.append(dct_value_field)
                        if rec_cg.force_clean_before_generate:
                            self._docker_remove_module(module_id)
                        model_conf = (
                            json.dumps(dct_model_conf)
                            # .replace('"', '\\"')
                            # .replace("'", "")
                        )
                        dct_new_project = {
                            "module": module_name,
                            "directory": rec.path_code_generator_to_generate,
                            "keep_bd_alive": True,
                            "it_workspace": rec.id,
                        }
                        # extra_arg = ""
                        if model_conf:
                            dct_new_project["config"] = model_conf
                            # extra_arg = f" --config '{model_conf}'"

                        new_project_id = self.env["it.cg.new_project"].create(
                            dct_new_project
                        )
                        new_project_id.action_new_project()
                        # cmd = (
                        #     f"cd {rec.path_working_erplibre};./script/code_generator/new_project.py"
                        #     f" --keep_bd_alive -m {module_name} -d"
                        #     f" {rec.path_code_generator_to_generate}{extra_arg}"
                        # )
                        # result = rec.system_id.exec_docker(cmd, rec.folder)
                        # rec.it_code_generator_log_addons = result
                if rec.it_code_generator_ids:
                    rec.action_stop_docker_compose()
                    rec.action_start_docker_compose()
                # rec.system_id.exec_docker(f"cd {rec.path_working_erplibre};make config_gen_all", rec.folder)
                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_code_generator_generate_all = (
                    f"{td:.03f}s"
                )

    def _docker_remove_module(self, module_id):
        for rec in self:
            with rec.it_workspace_log():
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};rm"
                    f" -rf ./{module_id.name};",
                    rec.folder,
                )
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};rm"
                    f" -rf ./code_generator_template_{module_id.name};",
                    rec.folder,
                )
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};rm"
                    f" -rf ./code_generator_{module_id.name};",
                    rec.folder,
                )

    @api.multi
    def action_clear_all_generated_module(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                for cg in rec.it_code_generator_ids:
                    for module_id in cg.module_ids:
                        self._docker_remove_module(module_id)
                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_clear_all_generated_module = f"{td:.03f}s"
        self.action_it_check_all()

    @api.multi
    def action_git_commit_all_generated_module(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                # for cg in rec.it_code_generator_ids:
                # Validate git directory exist
                result = rec.system_id.exec_docker(
                    f"ls {rec.path_working_erplibre}/{rec.path_code_generator_to_generate}/.git",
                    rec.folder,
                )
                if "No such file or directory" in result:
                    # Suppose git not exist
                    # This is not good if .git directory is in parent directory
                    result = rec.system_id.exec_docker(
                        f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};git"
                        " init",
                        rec.folder,
                    )
                result = rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};git"
                    " status -s",
                    rec.folder,
                )
                if result:
                    # Force add file and commit
                    result = rec.system_id.exec_docker(
                        f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};git"
                        " add .",
                        rec.folder,
                    )
                    result = rec.system_id.exec_docker(
                        f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};git"
                        " commit -m 'Commit by RobotLibre'",
                        rec.folder,
                    )
                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_git_commit_all_generated_module = (
                    f"{td:.03f}s"
                )

    @api.multi
    def action_refresh_meta_cg_generated_module(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                diff = ""
                status = ""
                stat = ""
                result = rec.system_id.exec_docker(
                    f"ls {rec.path_working_erplibre}/{rec.path_code_generator_to_generate}/.git",
                    rec.folder,
                )
                if result:
                    # Create diff
                    diff += rec.system_id.exec_docker(
                        f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};git"
                        " diff",
                        rec.folder,
                    )
                    # Create status
                    status += rec.system_id.exec_docker(
                        f"cd {rec.path_working_erplibre}/{rec.path_code_generator_to_generate};git"
                        " status",
                        rec.folder,
                    )
                    for cg in rec.it_code_generator_ids:
                        # Create statistic
                        for module_id in cg.module_ids:
                            result = rec.system_id.exec_docker(
                                f"cd {rec.path_working_erplibre};./script/statistic/code_count.sh"
                                f" ./{rec.path_code_generator_to_generate}/{module_id.name};",
                                rec.folder,
                            )
                            if result:
                                stat += f"./{rec.path_code_generator_to_generate}/{module_id.name}"
                                stat += result

                            result = rec.system_id.exec_docker(
                                f"cd {rec.path_working_erplibre};./script/statistic/code_count.sh"
                                f" ./{rec.path_code_generator_to_generate}/code_generator_template_{module_id.name};",
                                rec.folder,
                            )
                            if result:
                                stat += f"./{rec.path_code_generator_to_generate}/code_generator_template_{module_id.name}"
                                stat += result

                            result = rec.system_id.exec_docker(
                                f"cd {rec.path_working_erplibre};./script/statistic/code_count.sh"
                                f" ./{rec.path_code_generator_to_generate}/code_generator_{module_id.name};",
                                rec.folder,
                            )
                            if result:
                                stat += f"./{rec.path_code_generator_to_generate}/code_generator_{module_id.name}"
                                stat += result

                            # Autofix attached field to workspace
                            if rec not in module_id.it_workspace_ids:
                                module_id.it_workspace_ids = [(4, rec.id)]
                            for model_id in module_id.model_ids:
                                if rec not in model_id.it_workspace_ids:
                                    model_id.it_workspace_ids = [(4, rec.id)]
                                for field_id in model_id.field_ids:
                                    if rec not in field_id.it_workspace_ids:
                                        field_id.it_workspace_ids = [
                                            (4, rec.id)
                                        ]

                rec.it_code_generator_diff = diff
                rec.it_code_generator_status = status
                rec.it_code_generator_stat = stat
                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_refresh_meta_cg_generated_module = (
                    f"{td:.03f}s"
                )

    @api.multi
    def write(self, values):
        cg_before_ids_i = self.it_code_generator_ids.ids

        status = super().write(values)
        if "it_code_generator_ids" in values.keys():
            # Update all the list of code generator, associate to this workspace
            for rec in self:
                with rec.it_workspace_log():
                    cg_missing_ids_i = list(
                        set(cg_before_ids_i).difference(
                            set(rec.it_code_generator_ids.ids)
                        )
                    )
                    cg_missing_ids = self.env["it.code_generator"].browse(
                        cg_missing_ids_i
                    )
                    for cg_id in cg_missing_ids:
                        for module_id in cg_id.module_ids:
                            if rec in module_id.it_workspace_ids:
                                module_id.it_workspace_ids = [(3, rec.id)]
                            for model_id in module_id.model_ids:
                                if rec in model_id.it_workspace_ids:
                                    model_id.it_workspace_ids = [(3, rec.id)]
                                for field_id in model_id.field_ids:
                                    if rec in field_id.it_workspace_ids:
                                        field_id.it_workspace_ids = [
                                            (3, rec.id)
                                        ]
                    cg_adding_ids_i = list(
                        set(rec.it_code_generator_ids.ids).difference(
                            set(cg_before_ids_i)
                        )
                    )
                    cg_adding_ids = self.env["it.code_generator"].browse(
                        cg_adding_ids_i
                    )
                    for cg_id in cg_adding_ids:
                        for module_id in cg_id.module_ids:
                            if rec not in module_id.it_workspace_ids:
                                module_id.it_workspace_ids = [(4, rec.id)]
                            for model_id in module_id.model_ids:
                                if rec not in model_id.it_workspace_ids:
                                    model_id.it_workspace_ids = [(4, rec.id)]
                                for field_id in model_id.field_ids:
                                    if rec not in field_id.it_workspace_ids:
                                        field_id.it_workspace_ids = [
                                            (4, rec.id)
                                        ]
        return status

    @api.multi
    def action_install_all_generated_module(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                module_list = ",".join(
                    [
                        m.name
                        for cg in rec.it_code_generator_ids
                        for m in cg.module_ids
                    ]
                )
                last_cmd = rec.docker_cmd_extra
                rec.docker_cmd_extra = (
                    f"-d {rec.db_name} -i {module_list} -u {module_list}"
                )
                # TODO option install continuous or stop execution.
                # TODO Use install continuous in production, else stop execution for dev
                # TODO actually, it's continuous
                # TODO maybe add an auto-update when detect installation finish
                rec.action_stop_docker_compose()
                rec.action_start_docker_compose()
                rec.docker_cmd_extra = last_cmd
                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_install_all_generated_module = (
                    f"{td:.03f}s"
                )
        self.action_it_check_all()

    @api.multi
    def action_install_all_uca_generated_module(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                module_list = ",".join(
                    [
                        f"code_generator_template_{m.name},{m.name}"
                        for cg in rec.it_code_generator_ids
                        for m in cg.module_ids
                    ]
                )
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre};./script/database/db_restore.py"
                    " --database cg_uca",
                    rec.folder,
                )
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre};./script/addons/install_addons_dev.sh"
                    f" cg_uca {module_list}",
                    rec.folder,
                )

                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_install_all_uca_generated_module = (
                    f"{td:.03f}s"
                )
        self.action_it_check_all()

    @api.multi
    def action_install_all_ucb_generated_module(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                module_list = ",".join(
                    [
                        f"code_generator_{m.name}"
                        for cg in rec.it_code_generator_ids
                        for m in cg.module_ids
                    ]
                )
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre};./script/database/db_restore.py"
                    " --database cg_ucb",
                    rec.folder,
                )
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre};./script/addons/install_addons_dev.sh"
                    f" cg_ucb {module_list}",
                    rec.folder,
                )

                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_install_all_ucb_generated_module = (
                    f"{td:.03f}s"
                )
        self.action_it_check_all()

    @api.multi
    def action_install_and_generate_all_generated_module(self):
        for rec in self:
            with rec.it_workspace_log():
                start = datetime.now()
                rec.action_code_generator_generate_all()
                rec.action_install_all_generated_module()
                rec.action_git_commit_all_generated_module()
                rec.action_refresh_meta_cg_generated_module()
                end = datetime.now()
                td = (end - start).total_seconds()
                rec.time_exec_action_install_and_generate_all_generated_module = (
                    f"{td:.03f}s"
                )

    @api.multi
    def action_docker_logs(self):
        for rec in self:
            with rec.it_workspace_log():
                rec.system_id.execute_gnome_terminal(
                    rec.folder, cmd="docker compose logs -f"
                )

    @api.multi
    def action_open_terminal(self):
        for rec in self:
            with rec.it_workspace_log():
                rec.system_id.execute_gnome_terminal(rec.folder)

    @api.multi
    def action_open_terminal_docker(self):
        for rec in self:
            with rec.it_workspace_log():
                workspace = os.path.basename(rec.folder)
                docker_name = f"{workspace}-ERPLibre-1"
                rec.system_id.execute_gnome_terminal(
                    rec.folder,
                    cmd=f"docker exec -u root -ti {docker_name} /bin/bash",
                )

    @api.multi
    def action_open_terminal_tig(self):
        for rec in self:
            with rec.it_workspace_log():
                result = rec.system_id.exec_docker("which tig", rec.folder)
                if not result:
                    self.action_docker_install_dev_soft()
                rec.system_id.execute_gnome_terminal(
                    rec.folder,
                    cmd=(
                        f"cd {rec.path_working_erplibre};cd"
                        f" ./{rec.path_code_generator_to_generate};tig"
                    ),
                    docker=True,
                )

    @api.multi
    def action_docker_install_dev_soft(self):
        for rec in self:
            with rec.it_workspace_log():
                rec.system_id.exec_docker(
                    f"apt update;apt install -y tig vim htop tree watch",
                    rec.folder,
                )

    @api.multi
    def action_os_user_permission_docker(self):
        for rec in self:
            with rec.it_workspace_log():
                rec.system_id.execute_gnome_terminal(
                    rec.folder,
                    cmd=(
                        "sudo groupadd docker;sudo usermod -aG docker"
                        f" {rec.system_id.ssh_user}"
                    ),
                )
                rec.system_id.execute_gnome_terminal(
                    rec.folder,
                    cmd="sudo systemctl start docker.service",
                )
                # TODO check if all good
        self.docker_initiate_succeed = True

    @api.multi
    def action_analyse_docker_image(self):
        for rec in self:
            with rec.it_workspace_log():
                rec.system_id.execute_gnome_terminal(
                    rec.folder,
                    cmd=f"dive {rec.docker_version}",
                )

    @api.multi
    def action_it_check_all(self):
        for rec in self:
            # rec.docker_initiate_succeed = not rec.docker_initiate_succeed
            lst_file = (
                rec.system_id.execute_with_result(f"ls {rec.folder}")
                .strip()
                .split("\n")
            )
            if any(
                [
                    "No such file or directory" in str_file
                    for str_file in lst_file
                ]
            ):
                rec.is_installed = False
        self.action_docker_status()
        self.action_docker_check_docker_ps()
        self.action_docker_check_docker_tree_addons()
        # TODO check is_self_instance
        # for rec in self:
        #     print(rec)

    @api.multi
    def action_install_me_workspace(self):
        for rec in self:
            with rec.it_workspace_log():
                # Set same BD of this instance
                rec.db_name = self.env.cr.dbname
                # Detect the mode exec of this instance
                status_ls = rec.system_id.execute_with_result(
                    f"ls {rec.folder}/.git"
                )
                if "No such file or directory" not in status_ls:
                    rec.mode_exec = "git"
                self.action_install_workspace()

    @api.multi
    def action_install_workspace(self):
        for rec in self:
            with rec.it_workspace_log():
                lst_file = (
                    rec.system_id.execute_with_result(f"ls {rec.folder}")
                    .strip()
                    .split("\n")
                )
                if rec.mode_exec in ["docker"]:
                    if "docker-compose.yml" in lst_file:
                        # TODO try to reuse
                        print("detect docker-compose.yml, please read it")
                    self.action_pre_install_workspace()
                elif rec.mode_exec in ["git"]:
                    branch_str = ""
                    if rec.mode_version_erplibre:
                        if rec.mode_version_erplibre[0].isnumeric():
                            branch_str = f" -b v{rec.mode_version_erplibre}"
                        else:
                            branch_str = f" -b {rec.mode_version_erplibre}"

                    # TODO bug if file has same key
                    # if any(["ls:cannot access " in str_file for str_file in lst_file]):
                    if any(
                        [
                            "No such file or directory" in str_file
                            for str_file in lst_file
                        ]
                    ):
                        self.action_pre_install_workspace(
                            ignore_last_directory=True
                        )
                        result = rec.system_id.execute_with_result(
                            f"git clone {rec.git_url}{branch_str} {rec.folder}"
                        )
                        rec.log_workspace = result
                        result = rec.system_id.execute_with_result(
                            f"cd {rec.folder};./script/install/install_locally_dev.sh"
                        )
                        rec.log_workspace += result
                    else:
                        # TODO try te reuse
                        print("Git project already exist")

                    # lst_file = rec.system_id.execute_with_result(f"ls {rec.folder}").strip().split("\n")
                    # if "docker-compose.yml" in lst_file:
                    # if rec.mode_environnement in ["prod", "test"]:
                    #     result = rec.system_id.execute_with_result(
                    #         f"git clone https://github.com{rec.path_working_erplibre}{rec.path_working_erplibre}"
                    #         f"{branch_str}"
                    #     )
                    # else:
                rec.action_network_change_port_random()
            rec.is_installed = True

    @api.multi
    def action_pre_install_workspace(self, ignore_last_directory=False):
        for rec in self:
            with rec.it_workspace_log():
                folder = (
                    rec.folder
                    if not ignore_last_directory
                    else os.path.basename(rec.folder)
                )
                # Directory must exist
                # TODO make test to validate if remove next line, permission root the project /tmp/project/addons root
                addons_path = os.path.join(folder, "addons")
                rec.system_id.execute_with_result(f"mkdir -p '{addons_path}'")

    @api.multi
    def action_docker_restore_db_image(self):
        for rec in self:
            with rec.it_workspace_log():
                # TODO not working
                # maybe send by network REST web/database/restore
                # result = rec.system_id.exec_docker(f"cd {rec.path_working_erplibre};time ./script/database/db_restore.py --database test;", rec.folder)
                # rec.log_workspace = f"\n{result}"
                url_list = f"{rec.url_instance}/web/database/list"
                url_restore = f"{rec.url_instance}/web/database/restore"
                url_drop = f"{rec.url_instance}/web/database/drop"
                if not rec.image_db_selection:
                    # TODO create stage, need a stage ready to restore
                    raise exceptions.Warning(
                        _("Error, need field db_selection")
                    )
                rec.db_is_restored = False
                backup_file_path = rec.image_db_selection.path
                session = requests.Session()
                response = requests.get(
                    url_list,
                    data=json.dumps({}),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                if response.status_code == 200:
                    database_list = response.json()
                    print(database_list)
                else:
                    # TODO remove print
                    print("une erreur")
                    continue

                # Delete first
                result_db_list = database_list.get("result")
                if result_db_list:
                    result_db_list = result_db_list[0]
                    if result_db_list:
                        files = {
                            "master_pwd": (None, "admin"),
                            "name": (None, result_db_list),
                        }
                        response = session.post(url_drop, files=files)
                        if response.status_code == 200:
                            print("Le drop a été envoyé avec succès.")
                        else:
                            print("Une erreur s'est produite lors du drop.")
                            # Strange, retry for test
                            time.sleep(1)
                            response = requests.get(
                                url_list,
                                data=json.dumps({}),
                                headers={
                                    "Content-Type": "application/json",
                                    "Accept": "application/json",
                                },
                            )
                            if response.status_code == 200:
                                database_list = response.json()
                                print(database_list)

                with open(backup_file_path, "rb") as backup_file:
                    files = {
                        "backup_file": (
                            backup_file.name,
                            backup_file,
                            "application/octet-stream",
                        ),
                        "master_pwd": (None, "admin"),
                        "name": (None, rec.db_name),
                    }
                    response = session.post(url_restore, files=files)
                if response.status_code == 200:
                    print(
                        "Le fichier de restauration a été envoyé avec succès."
                    )
                    rec.db_is_restored = True
                else:
                    print(
                        "Une erreur s'est produite lors de l'envoi du fichier"
                        " de restauration."
                    )

                # f = {'file data': open(f'./image_db{rec.path_working_erplibre}_base.zip', 'rb')}
                # res = requests.post(url_restore, files=f)
                # print(res.text)

    @api.multi
    def action_network_change_port_random(
        self, min_port=10000, max_port=20000
    ):
        # Choose 2 sequence
        for rec in self:
            with rec.it_workspace_log():
                # port_1
                while rec.check_port_is_open(
                    rec, rec.system_id.iterator_port_generator
                ):
                    rec.system_id.iterator_port_generator += 1
                rec.port_http = rec.system_id.iterator_port_generator
                rec.system_id.iterator_port_generator += 1
                # port_2
                while rec.check_port_is_open(
                    rec, rec.system_id.iterator_port_generator
                ):
                    rec.system_id.iterator_port_generator += 1
                rec.port_longpolling = rec.system_id.iterator_port_generator
                rec.system_id.iterator_port_generator += 1
                if rec.system_id.iterator_port_generator >= max_port:
                    rec.system_id.iterator_port_generator = min_port

    @staticmethod
    def check_port_is_open(rec, port):
        # TODO move to it_network
        script = f"""
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(("127.0.0.1",{port}))
if result == 0:
   print("Port is open")
else:
   print("Port is not open")
sock.close()
        """
        if rec.system_id.debug_command:
            print(script)
        result = rec.system_id.execute_with_result(
            script,
            engine="python",
        )
        return result == "Port is open"

    @api.multi
    def action_start_docker_compose(self):
        for rec in self:
            with rec.it_workspace_log():
                rec.docker_is_running = False

                url_host = (
                    rec.system_id.ssh_host
                    if rec.system_id.method == "ssh"
                    else "127.0.0.1"
                )
                rec.url_instance = f"http://{url_host}:{rec.port_http}"
                rec.url_instance_database_manager = (
                    f"{rec.url_instance}/web/database/manager"
                )

                file_docker_compose = os.path.join(
                    rec.folder, "docker-compose.yml"
                )
                if rec.docker_cmd_extra:
                    docker_cmd_extra = f" {rec.docker_cmd_extra}"
                else:
                    docker_cmd_extra = ""
                if rec.docker_is_behind_proxy:
                    docker_behind_proxy = f" --proxy-mode"
                    workers = f"--workers {max(2, rec.docker_nb_proc)}"
                else:
                    docker_behind_proxy = ""
                    workers = f"--workers {rec.docker_nb_proc}"
                docker_compose_content = f"""
version: "3.3"
services:
  ERPLibre:
    image: {rec.docker_version}
    ports:
      - {rec.port_http}:8069
      - {rec.port_longpolling}:8072
    environment:
      HOST: db
      PASSWORD: mysecretpassword
      USER: odoo
      POSTGRES_DB: postgres
      STOP_BEFORE_INIT: "False"
      DB_NAME: ""
      UPDATE_ALL_DB: "False"
    depends_on:
      - db
    # not behind a proxy
    #command: odoo --workers 0
    # behind a proxy
    #command: odoo --workers 2 --proxy-mode
    command: odoo {workers}{docker_behind_proxy}{docker_cmd_extra}
    volumes:
      # See the volume section at the end of the file
      - erplibre_data_dir:/home/odoo/.local/share/Odoo
      - erplibre_conf:/etc/odoo
{'      - ' + '''
      - '''.join([f'./{path}:{rec.path_working_erplibre}/{path}' for path in rec.path_code_generator_to_generate.split(";")]) if rec.path_code_generator_to_generate else ''}
    restart: always

  db:
    image: postgis/postgis:12-3.1-alpine
    environment:
      POSTGRES_PASSWORD: mysecretpassword
      POSTGRES_USER: odoo
      POSTGRES_DB: postgres
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - erplibre-db-data:/var/lib/postgresql/data/pgdata
    restart: always

# We configure volume without specific destination to let docker manage it. To configure it through docker use (read related documentation before continuing) :
# - docker volume --help
# - docker-compose down --help
volumes:
  erplibre_data_dir:
  erplibre_conf:
  erplibre-db-data:
"""
                if rec.force_create_docker_compose or not os.path.exists(
                    file_docker_compose
                ):
                    rec.system_id.execute_with_result(
                        f"echo '{docker_compose_content}' >"
                        f" {file_docker_compose}"
                    )

                result = rec.system_id.execute_with_result(
                    f"cd {rec.folder};cat docker-compose.yml"
                )
                rec.docker_compose_ps = result
                result = rec.system_id.execute_with_result(
                    f"cd {rec.folder};docker compose up -d"
                )

                if (
                    "Cannot connect to the Docker daemon at"
                    " unix:///var/run/docker.sock. Is the docker daemon"
                    " running?"
                    in result
                ):
                    rec.docker_initiate_succeed = False

                rec.log_workspace = f"\n{result}"
                result = rec.system_id.execute_with_result(
                    f"cd {rec.folder};docker compose ps"
                )
                rec.log_workspace += f"\n{result}"
                rec.update_docker_compose_ps()

                result = rec.system_id.exec_docker(
                    "cat /etc/odoo/odoo.conf;", rec.folder
                )
                has_change = False
                if "db_host" not in result:
                    # TODO remove this information from executable of docker
                    result += (
                        "db_host = db\ndb_port = 5432\ndb_user ="
                        " odoo\ndb_password = mysecretpassword\n"
                    )
                if "admin_passwd" not in result:
                    result += "admin_passwd = admin\n"
                # TODO remove repo OCA_connector-jira
                str_to_replace = (
                    f",{rec.path_working_erplibre}/addons/OCA_connector-jira"
                )
                if str_to_replace in result:
                    result = result.replace(str_to_replace, "")
                    has_change = True

                if (
                    rec.docker_config_gen_cg
                    or not rec.docker_config_gen_cg
                    and rec.docker_config_cache
                ):
                    # TODO this is not good, need a script from manifest to rebuild this path
                    if rec.docker_config_gen_cg:
                        addons_path = (
                            "addons_path ="
                            f" {rec.path_working_erplibre}/odoo/addons,"
                            f"{rec.path_working_erplibre}/{rec.path_code_generator_to_generate},"
                            f"{rec.path_working_erplibre}/addons/OCA_web,"
                            f"{rec.path_working_erplibre}/addons{rec.path_working_erplibre}_erplibre_addons,"
                            f"{rec.path_working_erplibre}/addons{rec.path_working_erplibre}_erplibre_theme_addons,"
                            f"{rec.path_working_erplibre}/addons/MathBenTech_development,"
                            f"{rec.path_working_erplibre}/addons/MathBenTech_erplibre-family-management,"
                            f"{rec.path_working_erplibre}/addons/MathBenTech_odoo-business-spending-management-quebec-canada,"
                            f"{rec.path_working_erplibre}/addons/MathBenTech_scrummer,"
                            f"{rec.path_working_erplibre}/addons/Numigi_odoo-partner-addons,"
                            f"{rec.path_working_erplibre}/addons/Numigi_odoo-web-addons,"
                            f"{rec.path_working_erplibre}/addons/OCA_contract,"
                            f"{rec.path_working_erplibre}/addons/OCA_geospatial,"
                            f"{rec.path_working_erplibre}/addons/OCA_helpdesk,"
                            f"{rec.path_working_erplibre}/addons/OCA_server-auth,"
                            f"{rec.path_working_erplibre}/addons/OCA_server-brand,"
                            f"{rec.path_working_erplibre}/addons/OCA_server-tools,"
                            f"{rec.path_working_erplibre}/addons/OCA_server-ux,"
                            f"{rec.path_working_erplibre}/addons/OCA_social,"
                            f"{rec.path_working_erplibre}/addons/OCA_website,"
                            f"{rec.path_working_erplibre}/addons/TechnoLibre_odoo-code-generator,"
                            f"{rec.path_working_erplibre}/addons/TechnoLibre_odoo-code-generator-template,"
                            f"{rec.path_working_erplibre}/addons/ajepe_odoo-addons,"
                            f"{rec.path_working_erplibre}/addons/muk-it_muk_base,"
                            f"{rec.path_working_erplibre}/addons/muk-it_muk_misc,"
                            f"{rec.path_working_erplibre}/addons/muk-it_muk_web,"
                            f"{rec.path_working_erplibre}/addons/muk-it_muk_website,"
                            f"{rec.path_working_erplibre}/addons/odoo_design-themes"
                        )
                    elif (
                        not rec.docker_config_gen_cg
                        and rec.docker_config_cache
                    ):
                        addons_path = rec.docker_config_cache
                        rec.docker_config_cache = ""

                    # TODO use configparser instead of string parsing
                    lst_result = result.split("\n")
                    for i, a_result in enumerate(lst_result):
                        if a_result.startswith("addons_path = "):
                            if (
                                rec.docker_config_gen_cg
                                and not rec.docker_config_cache
                            ):
                                rec.docker_config_cache = a_result
                            lst_result[i] = addons_path
                            break
                    result = "\n".join(lst_result)
                    has_change = True

                if has_change:
                    # TODO rewrite conf file and reformat
                    rec.system_id.exec_docker(
                        f"echo -e '{result}' > /etc/odoo/odoo.conf", rec.folder
                    )
                # TODO support only one file, and remove /odoo.conf
                rec.system_id.exec_docker(
                    f"cd {rec.path_working_erplibre};cp /etc/odoo/odoo.conf"
                    " ./config.conf;",
                    rec.folder,
                )
                rec.action_docker_check_docker_ps()

    @api.multi
    @contextmanager
    def it_workspace_log(self):
        # TODO adapt for erplibre_it
        """Log a it_workspace result."""
        try:
            _logger.info("Starting database it_workspace: %s", self.name)
            yield
        except Exception:
            _logger.exception("Database it_workspace failed: %s", self.name)
            escaped_tb = tools.html_escape(traceback.format_exc())
            self.message_post(  # pylint: disable=translation-required
                body="<p>%s</p><pre>%s</pre>"
                % (_("Database it_workspace failed."), escaped_tb),
                subtype=self.env.ref(
                    "erplibre_it.mail_message_subtype_failure"
                ),
            )
        else:
            _logger.info("Database it_workspace succeeded: %s", self.name)
            self.message_post(body=_("Database it_workspace succeeded."))
