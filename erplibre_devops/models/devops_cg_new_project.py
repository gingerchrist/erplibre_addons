# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import configparser
import json
import logging
import os
import tempfile
import uuid

from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError

from odoo import _, api, exceptions, fields, models, tools

CODE_GENERATOR_DIRECTORY = "./addons/TechnoLibre_odoo-code-generator-template/"
CODE_GENERATOR_DEMO_NAME = "code_generator_demo"
KEY_REPLACE_CODE_GENERATOR_DEMO = 'MODULE_NAME = "%s"'
_logger = logging.getLogger(__name__)


class DevopsCgNewProject(models.Model):
    _name = "devops.cg.new_project"
    _description = "Create new project for CG project"

    @api.model
    def default_stage_id(self):
        return self.env.ref("erplibre_devops.devops_cg_new_project_stage_init")

    name = fields.Char(compute="_compute_name")

    active = fields.Boolean(default=True)

    msg_error = fields.Char()

    has_error = fields.Boolean()

    stage_id = fields.Many2one(
        "devops.cg.new_project.stage",
        "Stage",
        default=lambda s: s.default_stage_id(),
    )

    project_type = fields.Selection(
        [("self", "Self generate"), ("cg", "Code generator")]
    )

    last_new_project = fields.Many2one(
        comodel_name="devops.cg.new_project",
        string="Last new project",
    )

    exec_start_date = fields.Datetime(string="Execution start date")

    exec_stop_date = fields.Datetime(string="Execution stop date")

    exec_time_duration = fields.Float(
        string="Execution time duration", compute="_compute_exec_time_duration"
    )

    execution_finish = fields.Boolean()

    module = fields.Char(required=True)

    directory = fields.Char(required=True)

    keep_bd_alive = fields.Boolean()

    config = fields.Char()

    code_generator_name = fields.Char()

    template_name = fields.Char()

    coverage = fields.Char()

    odoo_config = fields.Char(default="./config.conf")

    stop_execution_if_env_not_clean = fields.Boolean(default=True)

    force = fields.Boolean()

    internal_error = fields.Char(
        compute="_compute_internal_error",
        store=True,
    )

    devops_exec_bundle_id = fields.Many2one(comodel_name="devops.exec.bundle")

    devops_workspace = fields.Many2one(comodel_name="devops.workspace")

    @api.depends(
        "devops_workspace",
        "module",
        "exec_start_date",
        "exec_stop_date",
        "exec_time_duration",
    )
    def _compute_name(self):
        for rec in self:
            if not isinstance(rec.id, models.NewId):
                rec.name = f"{rec.id}: "
            else:
                rec.name = ""
            rec.name += f"{rec.devops_workspace.name} - {rec.module}"
            if rec.exec_stop_date:
                rec.name += (
                    f" - finish {rec.exec_stop_date} duration"
                    f" {rec.exec_time_duration}"
                )
            elif rec.exec_start_date:
                rec.name += f" - start {rec.exec_start_date}"

    @api.depends(
        "exec_start_date",
        "exec_stop_date",
    )
    def _compute_exec_time_duration(self):
        for rec in self:
            if rec.exec_start_date and rec.exec_stop_date:
                rec.exec_time_duration = (
                    rec.exec_stop_date - rec.exec_start_date
                ).total_seconds()
            else:
                rec.exec_time_duration = None

    @api.multi
    @api.depends("directory")
    def _compute_internal_error(self):
        """Get the right summary for this job."""
        for rec in self:
            if not os.path.exists(rec.directory):
                rec.internal_error = (
                    f"Path directory '{rec.directory}' not exist. You"
                    f" actual path is: '{os.getcwd()}'."
                )

    @api.multi
    def action_new_project(self):
        for rec in self:
            with rec.devops_workspace.devops_create_exec_bundle(
                "New project"
            ) as rec_ws:
                rec.exec_start_date = fields.Datetime.now(self)
                project = ProjectManagement(
                    rec,
                    rec.module,
                    rec.directory,
                    cg_name=rec.code_generator_name,
                    template_name=rec.template_name,
                    force=rec.force,
                    keep_bd_alive=rec.keep_bd_alive,
                    coverage=rec.coverage,
                    config=rec.config,
                    odoo_config=rec.odoo_config,
                )
                if project.msg_error:
                    rec.msg_error = project.msg_error
                    rec.has_error = True

                if not project.generate_module():
                    rec.has_error = True

                rec.exec_stop_date = fields.Datetime.now(self)
                rec.execution_finish = True


class ProjectManagement:
    def __init__(
        self,
        rec,
        module_name,
        module_directory,
        cg_name="",
        cg_directory="",
        template_name="",
        template_directory="",
        force=False,
        keep_bd_alive=False,
        coverage=False,
        config="",
        odoo_config="./config.conf",
    ):
        self.rec = rec
        self.force = force
        self._coverage = coverage
        self.keep_bd_alive = keep_bd_alive
        self.msg_error = ""
        self.has_config_update = False
        self.odoo_config = odoo_config
        self.module_directory = module_directory

        self.rec.stage_id = self.rec.env.ref(
            "erplibre_devops.devops_cg_new_project_stage_init"
        )

        # if not os.path.exists(self.module_directory):
        #     self.msg_error = (
        #         f"Path directory '{self.module_directory}' not exist. You"
        #         f" actual path is: '{os.getcwd()}'."
        #     )
        #     raise Exception(self.msg_error)

        self.cg_directory = cg_directory if cg_directory else module_directory
        if not os.path.exists(self.cg_directory):
            self.msg_error = (
                f"Path cg directory '{self.cg_directory}' not exist. You"
                f" actual path is: '{os.getcwd()}'."
            )
            raise Exception(self.msg_error)

        self.template_directory = (
            template_directory if template_directory else module_directory
        )
        if not os.path.exists(self.template_directory):
            self.msg_error = (
                f"Path template directory '{self.template_directory}' not"
                " exist."
            )
            raise Exception(self.msg_error)

        if not module_name:
            self.msg_error = "Module name is missing."
            raise Exception(self.msg_error)

        # Get module name
        self.module_name = module_name
        # Get code_generator name
        self.cg_name = self._generate_cg_name(default=cg_name)
        # Get template name
        self.template_name = self._generate_template_name(
            default=template_name
        )

        self._parse_config(config)

    def _parse_config(self, config):
        if not config:
            self.config = {}
            self.config_lst_model = []
        else:
            self.config = json.loads(config)
            self.config_lst_model = self.config.get("model")

    def _generate_cg_name(self, default=""):
        if default:
            return default
        return f"code_generator_{self.module_name}"

    def _generate_template_name(self, default=""):
        if default:
            return default
        return f"code_generator_template_{self.module_name}"

    def search_and_replace_file(self, filepath, lst_search_and_replace):
        """
        lst_search_and_replace is a list of tuple, first item is search, second is replace
        """
        with open(filepath, "r") as file:
            txt = file.read()
            for search, replace in lst_search_and_replace:
                if search not in txt:
                    self.msg_error = (
                        f"Cannot find '{search}' in file '{filepath}'"
                    )
                    raise Exception(self.msg_error)
                txt = txt.replace(search, replace)
        with open(filepath, "w") as file:
            file.write(txt)
        return True

    def validate_path_ready_to_be_override(self, name, directory, path=""):
        if not path:
            path = os.path.join(directory, name)
        if not os.path.exists(path):
            return True
        # Check if in git
        try:
            git_repo = Repo(directory)
        except NoSuchPathError:
            raise Exception(f"Directory not existing '{directory}'")
        except InvalidGitRepositoryError:
            raise Exception(
                f"The path '{path}' exist, but no git repo, use force to"
                " ignore it."
            )

        if self.rec.stop_execution_if_env_not_clean:
            status = git_repo.git.status(name, porcelain=True)
            if status:
                msg = (
                    f"The directory '{path}' has git difference, use force to"
                    " ignore it."
                )
                raise Exception(msg)
        return True

    @staticmethod
    def restore_git_code_generator_demo(
        code_generator_demo_path, relative_path
    ):
        try:
            git_repo = Repo(code_generator_demo_path)
        except NoSuchPathError:
            raise Exception(
                f"Directory not existing '{code_generator_demo_path}'"
            )
        except InvalidGitRepositoryError:
            raise Exception(
                f"The path '{code_generator_demo_path}' exist, but no git repo"
            )

        git_repo.git.restore(relative_path)

    def generate_module(self):
        with self.rec.devops_workspace.devops_create_exec_bundle(
            "Generate new project with CG"
        ) as rec_ws:
            rec = self.rec
            # TODO copy directory in temp workspace file before update it
            module_path = os.path.join(self.module_directory, self.module_name)
            is_over = self.validate_path_ready_to_be_override(
                self.module_name, self.module_directory, path=module_path
            )
            if not rec.force and not is_over:
                self.msg_error = (
                    f"Cannot generate on module path '{module_path}'"
                )
                raise Exception(self.msg_error)

            cg_path = os.path.join(self.cg_directory, self.cg_name)
            cg_hooks_py = os.path.join(cg_path, "hooks.py")
            if not rec.force and not self.validate_path_ready_to_be_override(
                self.cg_name, self.cg_directory, path=cg_path
            ):
                self.msg_error = f"Cannot generate on cg path '{cg_path}'"
                raise Exception(self.msg_error)

            template_path = os.path.join(
                self.template_directory, self.template_name
            )
            template_hooks_py = os.path.join(template_path, "hooks.py")
            if not rec.force and not self.validate_path_ready_to_be_override(
                self.template_name, self.template_directory, path=template_path
            ):
                self.msg_error = (
                    f"Cannot generate on template path '{template_path}'"
                )
                raise Exception(self.msg_error)

            # Validate code_generator_demo
            code_generator_demo_path = os.path.join(
                CODE_GENERATOR_DIRECTORY, CODE_GENERATOR_DEMO_NAME
            )
            code_generator_demo_hooks_py = os.path.join(
                code_generator_demo_path, "hooks.py"
            )
            code_generator_hooks_path_relative = os.path.join(
                CODE_GENERATOR_DEMO_NAME, "hooks.py"
            )
            if not os.path.exists(code_generator_demo_path):
                self.msg_error = (
                    "code_generator_demo is not accessible"
                    f" '{code_generator_demo_path}'"
                )
                raise Exception(self.msg_error)

            rec.stage_id = rec.env.ref(
                "erplibre_devops.devops_cg_new_project_stage_generate_config"
            )

            if not (
                self.validate_path_ready_to_be_override(
                    CODE_GENERATOR_DEMO_NAME, CODE_GENERATOR_DIRECTORY
                )
                and self.search_and_replace_file(
                    code_generator_demo_hooks_py,
                    [
                        (
                            KEY_REPLACE_CODE_GENERATOR_DEMO
                            % CODE_GENERATOR_DEMO_NAME,
                            KEY_REPLACE_CODE_GENERATOR_DEMO
                            % self.template_name,
                        ),
                        (
                            'value["enable_sync_template"] = False',
                            'value["enable_sync_template"] = True',
                        ),
                        (
                            "# path_module_generate ="
                            " os.path.normpath(os.path.join(os.path.dirname(__file__),"
                            " '..'))",
                            "path_module_generate ="
                            f' "{self.module_directory}"',
                        ),
                        (
                            '# "path_sync_code": path_module_generate,',
                            '"path_sync_code": path_module_generate,',
                        ),
                        (
                            '# value["template_module_path_generated_extension"]'
                            ' = "."',
                            'value["template_module_path_generated_extension"]'
                            f' = "{self.cg_directory}"',
                        ),
                    ],
                )
            ):
                return False
            config_path = self.update_config()

            rec.stage_id = rec.env.ref(
                "erplibre_devops.devops_cg_new_project_stage_generate_uc0"
            )

            bd_name_demo = f"new_project_code_generator_demo_{uuid.uuid4()}"[
                :63
            ]
            cmd = f"./script/database/db_restore.py --database {bd_name_demo}"
            _logger.info(cmd)
            rec_ws.execute(cmd=cmd)
            _logger.info("========= GENERATE code_generator_demo =========")

            if self._coverage:
                cmd = (
                    "./script/addons/coverage_install_addons_dev.sh"
                    f" {bd_name_demo} code_generator_demo {config_path}"
                )
            else:
                cmd = (
                    f"./script/addons/install_addons_dev.sh {bd_name_demo}"
                    f" code_generator_demo {config_path}"
                )
            rec_ws.execute(cmd=cmd)

            if not self.keep_bd_alive:
                cmd = (
                    "./.venv/bin/python3 ./odoo/odoo-bin db --drop --database"
                    f" {bd_name_demo}"
                )
                _logger.info(cmd)
                rec_ws.execute(cmd=cmd)

            # Revert code_generator_demo
            self.restore_git_code_generator_demo(
                CODE_GENERATOR_DIRECTORY, code_generator_hooks_path_relative
            )

            # Validate
            if not os.path.exists(template_path):
                raise Exception(
                    f"Module template not exists '{template_path}'"
                )
            else:
                _logger.info(f"Module template exists '{template_path}'")

            rec.stage_id = rec.env.ref(
                "erplibre_devops.devops_cg_new_project_stage_generate_uca"
            )

            lst_template_hooks_py_replace = [
                (
                    'value["enable_template_wizard_view"] = False',
                    'value["enable_template_wizard_view"] = True',
                ),
            ]

            # Add model from config
            if self.config:
                str_lst_model = "; ".join(
                    [a.get("name") for a in self.config_lst_model]
                )
                old_str = 'value["template_model_name"] = ""'
                new_str = f'value["template_model_name"] = "{str_lst_model}"'
                lst_template_hooks_py_replace.append((old_str, new_str))

                self.search_and_replace_file(
                    template_hooks_py,
                    lst_template_hooks_py_replace,
                )

            # Execute all
            bd_name_template = (
                f"new_project_code_generator_template_{uuid.uuid4()}"[:63]
            )
            cmd = (
                "./script/database/db_restore.py --database"
                f" {bd_name_template}"
            )
            rec_ws.execute(cmd=cmd)
            _logger.info(cmd)
            _logger.info(f"========= GENERATE {self.template_name} =========")
            # TODO maybe the module exist somewhere else
            if os.path.exists(module_path):
                # Install module before running code generator
                cmd = (
                    "./script/code_generator/search_class_model.py --quiet -d"
                    f" {module_path} -t {template_path}"
                )
                _logger.info(cmd)
                rec_ws.execute(cmd=cmd)
                if self._coverage:
                    cmd = (
                        "./script/addons/coverage_install_addons_dev.sh"
                        f" {bd_name_template} {self.module_name} {config_path}"
                    )
                else:
                    cmd = (
                        "./script/addons/install_addons_dev.sh"
                        f" {bd_name_template} {self.module_name} {config_path}"
                    )
                _logger.info(cmd)
                rec_ws.execute(cmd=cmd)

            if self._coverage:
                cmd = (
                    "./script/addons/coverage_install_addons_dev.sh"
                    f" {bd_name_template} {self.template_name} {config_path}"
                )
            else:
                cmd = (
                    f"./script/addons/install_addons_dev.sh {bd_name_template}"
                    f" {self.template_name} {config_path}"
                )
            _logger.info(cmd)
            rec_ws.execute(cmd=cmd)

            if not self.keep_bd_alive:
                cmd = (
                    "./.venv/bin/python3 ./odoo/odoo-bin db --drop --database"
                    f" {bd_name_template}"
                )
                _logger.info(cmd)
                rec_ws.execute(cmd=cmd)

            # Validate
            if not os.path.exists(cg_path):
                raise Exception(f"Module cg not exists '{cg_path}'")
            else:
                _logger.info(f"Module cg exists '{cg_path}'")

            rec.stage_id = rec.env.ref(
                "erplibre_devops.devops_cg_new_project_stage_generate_ucb"
            )

            bd_name_generator = f"new_project_code_generator_{uuid.uuid4()}"[
                :63
            ]
            cmd = (
                "./script/database/db_restore.py --database"
                f" {bd_name_generator}"
            )
            _logger.info(cmd)
            rec_ws.execute(cmd=cmd)
            _logger.info(f"========= GENERATE {self.cg_name} =========")

            # Add field from config
            if self.config:
                lst_update_cg = []
                for model in self.config_lst_model:
                    model_name = model.get("name")
                    dct_field = {}
                    for a in model.get("fields"):
                        dct_value = {"ttype": a.get("type")}
                        if "relation" in a.keys():
                            dct_value["relation"] = a["relation"]
                        if "relation_field" in a.keys():
                            dct_value["relation_field"] = a["relation_field"]
                        if "description" in a.keys():
                            dct_value["field_description"] = a["description"]
                        dct_field[a.get("name")] = dct_value
                    if "name" not in dct_field.keys():
                        dct_field["name"] = {"ttype": "char"}
                    old_str = (
                        f'model_model = "{model_name}"\n       '
                        " code_generator_id.add_update_model(model_model)"
                    )
                    new_str = (
                        f'model_model = "{model_name}"\n        dct_field ='
                        f" {dct_field}\n       "
                        " code_generator_id.add_update_model(model_model,"
                        " dct_field=dct_field)"
                    )
                    lst_update_cg.append((old_str, new_str))

                # Force add menu and access
                lst_update_cg.append(('"disable_generate_menu": True,', ""))
                lst_update_cg.append(('"disable_generate_access": True,', ""))
                self.search_and_replace_file(
                    cg_hooks_py,
                    lst_update_cg,
                )

            if self._coverage:
                cmd = (
                    "./script/addons/coverage_install_addons_dev.sh"
                    f" {bd_name_generator} {self.cg_name} {config_path}"
                )
            else:
                cmd = (
                    "./script/addons/install_addons_dev.sh"
                    f" {bd_name_generator} {self.cg_name} {config_path}"
                )
            _logger.info(cmd)
            rec_ws.with_context(devops_cg_new_project=rec.id).execute(cmd=cmd)

            if not self.keep_bd_alive:
                cmd = (
                    "./.venv/bin/python3 ./odoo/odoo-bin db --drop --database"
                    f" {bd_name_generator}"
                )
                _logger.info(cmd)
                rec_ws.execute(cmd=cmd)

            # Validate
            if not os.path.exists(module_path):
                raise Exception(f"Module not exists '{module_path}'")
            else:
                _logger.info(f"Module exists '{module_path}'")

            rec.stage_id = rec.env.ref(
                "erplibre_devops.devops_cg_new_project_stage_generate_terminate"
            )

        return True

    def update_config(self):
        config = configparser.ConfigParser()
        config.read(self.odoo_config)
        addons_path = config.get("options", "addons_path")
        lst_addons_path = addons_path.split(",")
        lst_directory = list(
            {
                self.cg_directory,
                self.module_directory,
                self.template_directory,
            }
        )
        has_change = False
        for new_addons_path in lst_directory:
            for actual_addons_path in lst_addons_path:
                if not actual_addons_path:
                    continue
                # Validate if not existing and valide is different path
                relative_actual_addons_path = os.path.relpath(
                    actual_addons_path
                )
                relative_new_addons_path = os.path.relpath(new_addons_path)
                if relative_actual_addons_path == relative_new_addons_path:
                    break
            else:
                lst_addons_path.insert(0, new_addons_path)
                has_change = True
        if has_change:
            config.set("options", "addons_path", ",".join(lst_addons_path))
        temp_file = tempfile.mktemp()
        with open(temp_file, "w") as configfile:
            config.write(configfile)
        _logger.info(f"Create temporary config file: {temp_file}")
        return temp_file
