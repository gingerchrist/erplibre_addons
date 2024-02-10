import logging
import os
import time
import uuid

from odoo import _, api, exceptions, fields, models

_logger = logging.getLogger(__name__)


class DevopsPlanActionWizard(models.TransientModel):
    _name = "devops.plan.action.wizard"
    _description = "Devops planification do an action with a specific workflow"
    _inherit = ["multi.step.wizard.mixin"]

    def _default_image_db_selection(self):
        return self.env["devops.db.image"].search(
            [("name", "like", "erplibre_base")], limit=1
        )

    name = fields.Char()

    root_workspace_id = fields.Many2one(
        comodel_name="devops.workspace",
        string="Root workspace",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
        ondelete="cascade",
        help="Workspace where to execute the action.",
    )

    create_workspace_id = fields.Many2one(
        comodel_name="devops.workspace",
        string="Created workspace",
        ondelete="cascade",
        help="Workspace generate by this wizard.",
    )

    root_workspace_id_is_me = fields.Boolean(related="root_workspace_id.is_me")

    # working_workspace_ids = fields.One2many(
    #     related="working_system_id.devops_workspace_ids"
    # )

    workspace_folder = fields.Char(
        compute="_compute_workspace_folder",
        store=True,
        help="Absolute path for storing the devops_workspaces",
    )

    erplibre_mode = fields.Many2one(
        comodel_name="erplibre.mode",
    )

    generated_new_project_id = fields.Many2one(
        comodel_name="devops.cg.new_project",
        string="Generated project",
    )

    plan_cg_id = fields.Many2one(
        comodel_name="devops.plan.cg",
        string="Generated plan CG",
    )

    working_module_id = fields.Many2one(
        comodel_name="ir.module.module",
        string="Working module",
    )

    working_module_name_suggestion = fields.Selection(
        selection=[
            ("addons/addons", "Addons private"),
            ("addons/ERPLibre_erplibre_addons", "ERPLibre addons"),
            ("addons/TechnoLibre_odoo-code-generator", "Code generator"),
        ],
        help="Suggestion relative path",
    )

    working_module_name = fields.Char(
        help="working_module_id or working_module_name"
    )

    working_module_path = fields.Char(
        help="Need it for new module, relative path from folder of workspace."
    )

    system_name = fields.Char(string="System name")

    system_method = fields.Selection(related="working_system_id.method")

    system_erplibre_config_path_home_ids = fields.Many2many(
        related="working_system_id.erplibre_config_path_home_ids"
    )

    working_erplibre_config_path_home_id = fields.Many2one(
        string="Root path",
        comodel_name="erplibre.config.path.home",
    )

    working_relative_folder = fields.Char(string="Relative folder")

    is_force_local_system = fields.Boolean(
        help="Help for view to force local component."
    )

    is_new_or_exist_ssh = fields.Boolean(
        compute="_compute_is_new_or_exist_ssh", store=True
    )

    can_search_workspace = fields.Boolean(
        compute="_compute_can_search_workspace", store=True
    )

    ssh_user = fields.Char(
        string="SSH user", help="New remote system ssh_user."
    )

    ssh_password = fields.Char(
        string="SSH password", help="New remote system ssh_password."
    )

    ssh_host = fields.Char(
        string="SSH host/IP", help="New remote system ssh_host, like local ip."
    )

    ssh_port = fields.Integer(
        string="SSH Port",
        default=22,
        help="The port on the FTP server that accepts SSH calls.",
    )

    working_system_id = fields.Many2one(
        comodel_name="devops.system",
        string="New/Existing system",
    )

    working_cg_module_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="CG code builder",
    )

    working_cg_writer_id = fields.Many2one(
        comodel_name="code.generator.writer",
        string="CG code writer",
    )

    is_update_system = fields.Boolean(
        store=True,
        compute="_compute_is_update_system",
        help="True if editing an existing system or False to create a system",
    )

    mode_view_portal = fields.Selection(
        selection=[
            ("no_portal", "No portal"),
            ("enable_portal", "Enable portal"),
        ],
        default="no_portal",
        help="Will active feature to generate portal interface",
    )

    mode_view_portal_enable_create = fields.Boolean(
        default=True,
        help="Feature for portal_enable_create",
    )

    mode_view_portal_enable_read = fields.Boolean(
        default=True,
        help="Feature for portal_enable_read",
    )

    mode_view_portal_enable_update = fields.Boolean(
        default=True,
        help="Feature for portal_enable_update",
    )

    mode_view_portal_enable_delete = fields.Boolean(
        default=True,
        help="Feature for portal_enable_delete",
    )

    mode_view_portal_models = fields.Char(
        help="Separate models by ;",
    )

    mode_view_snippet = fields.Selection(
        selection=[
            ("no_snippet", "No snippet"),
            ("enable_snippet", "Enable snippet"),
        ],
        default="no_snippet",
        help="Will active feature to generate snippet on website interface",
    )

    mode_view_snippet_enable_template_website_snippet_view = fields.Boolean(
        default=True,
        help="Feature for mode_view_snippet",
    )

    mode_view_snippet_template_generate_website_snippet_generic_mdl = (
        fields.Char(help="Feature for mode_view_snippet")
    )

    mode_view_snippet_template_generate_website_snippet_ctrl_featur = (
        fields.Selection(
            selection=[
                ("helloworld", "helloworld"),
                ("model_show_item_individual", "Model show item individual"),
                ("model_show_item_list", "Model show item list"),
            ],
            default="model_show_item_individual",
            help="Feature for mode_view_snippet",
        )
    )

    mode_view_snippet_template_generate_website_enable_javascript = (
        fields.Boolean(
            default=True,
            help="Feature for mode_view_snippet",
        )
    )

    mode_view_snippet_template_generate_website_snippet_type = (
        fields.Selection(
            selection=[
                ("content", "Content"),
                ("effect", "Effect"),
                ("feature", "Feature"),
                ("structure", "Structure"),
            ],
            default="effect",
            help="Feature for mode_view_snippet",
        )
    )

    use_internal_cg = fields.Boolean(
        help=(
            "If internal, will use same database of devops for build code,"
            " this can interfere."
        ),
    )

    system_ssh_connection_status = fields.Boolean(
        related="working_system_id.ssh_connection_status",
        help="Status of test remote working_system_id",
    )

    state = fields.Selection(default="init")

    has_next = fields.Boolean(compute="_compute_has_next")

    force_generate = fields.Boolean(
        help=(
            "Ignore secure file edited, can overwrite this file and lost data."
        )
    )

    model_ids = fields.Many2many(
        comodel_name="devops.cg.model",
        string="Model",
    )

    model_to_remove_ids = fields.Many2many(
        comodel_name="devops.cg.model",
        string="Model to remove",
        relation="devops_plan_action_model_remove_rel",
    )

    image_db_selection = fields.Many2one(
        comodel_name="devops.db.image",
        default=_default_image_db_selection,
    )

    enable_package_srs = fields.Boolean()

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        default=lambda s: s.env.user.id,
    )

    def _compute_has_next(self):
        for record in self:
            record.has_next = getattr(
                record, "state_exit_%s" % record.state, False
            )

    @api.multi
    @api.depends("working_system_id")
    def _compute_is_update_system(self):
        for rec in self:
            is_update_system = bool(rec.working_system_id)
            if is_update_system:
                rec.system_name = rec.working_system_id.name_overwrite
                rec.ssh_host = rec.working_system_id.ssh_host
                rec.ssh_user = rec.working_system_id.ssh_user
                rec.ssh_password = rec.working_system_id.ssh_password

    @api.multi
    @api.depends(
        "working_erplibre_config_path_home_id",
        "working_erplibre_config_path_home_id.name",
        "working_relative_folder",
    )
    def _compute_workspace_folder(self):
        for rec in self:
            rec.workspace_folder = ""
            if (
                rec.working_erplibre_config_path_home_id
                and rec.working_erplibre_config_path_home_id.name
            ):
                if rec.working_relative_folder:
                    rec.workspace_folder = os.path.join(
                        rec.working_erplibre_config_path_home_id.name,
                        rec.working_relative_folder,
                    )
                else:
                    rec.workspace_folder = (
                        rec.working_erplibre_config_path_home_id.name
                    )

    @api.multi
    @api.depends("system_method", "working_system_id")
    def _compute_is_new_or_exist_ssh(self):
        for rec in self:
            rec.is_new_or_exist_ssh = (
                not rec.working_system_id
                or rec.working_system_id.method == "ssh"
            )

    @api.multi
    @api.depends(
        "working_system_id", "system_ssh_connection_status", "system_method"
    )
    def _compute_can_search_workspace(self):
        for rec in self:
            rec.can_search_workspace = False
            if rec.working_system_id:
                if (
                    rec.system_method == "ssh"
                    and rec.system_ssh_connection_status
                ):
                    rec.can_search_workspace = True
                elif rec.system_method == "local":
                    rec.can_search_workspace = True

    @api.model
    def _selection_state(self):
        return [
            ("init", "Init"),
            ("a_autopoiesis_devops", "Autopoiesis DevOps"),
            ("a_a_model", "Model autopoiesis devops"),
            ("a_b_field", "Field"),
            ("a_c_action", "Action"),
            ("a_d_view", "View"),
            ("a_f_devops_regen", "DevOps regenerate"),
            ("b_new_module", "New module"),
            ("c_existing_module", "Existing module"),
            ("c_a_model", "Model existing module"),
            ("d_import_data", "Import data"),
            ("e_migrate_from_external_ddb", "Migrate from external database"),
            ("f_new_project_society", "New society"),
            ("g_test_erplibre", "Test ERPLibre"),
            ("g_new_module", "New module ERPLibre"),
            ("g_a_local", "Test ERPLibre local"),
            ("h_run_test", "Run test"),
            ("h_a_test_plan_exec", "Run test plan execution"),
            ("h_b_cg", "Run test code generator"),
            ("i_new_remote_system", "New remote system"),
            ("not_supported", "Not supported"),
            ("final", "Final"),
        ]

    def clear_working_system_id(self):
        self.working_system_id = False
        return self._reopen_self()

    def state_goto_a_autopoiesis_devops(self):
        self.state = "a_autopoiesis_devops"
        return self._reopen_self()

    def state_goto_a_a_model(self):
        self.state = "a_a_model"
        return self._reopen_self()

    def state_goto_a_b_field(self):
        self.state = "a_b_field"
        return self._reopen_self()

    def state_goto_a_e_cg_regen(self):
        self.state = "a_e_cg_regen"
        return self._reopen_self()

    def state_goto_a_f_devops_regen(self):
        self.state = "a_f_devops_regen"
        return self._reopen_self()

    def state_goto_a_g_regen(self):
        self.state = "a_g_regen"
        return self._reopen_self()

    def state_goto_f_new_project_society(self):
        self.state = "f_new_project_society"
        return self._reopen_self()

    def state_goto_g_test_erplibre(self):
        self.state = "g_test_erplibre"
        return self._reopen_self()

    def state_goto_g_new_module(self):
        self.state = "g_new_module"
        return self._reopen_self()

    def state_goto_h_run_test(self):
        self.state = "h_run_test"
        return self._reopen_self()

    def state_goto_h_a_test_plan_exec(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "devops.test.plan.exec",
            "view_mode": "form",
            "target": "new",
            "context": {"default_workspace_id": self.root_workspace_id.id},
        }

    def state_goto_h_b_cg(self):
        self.state = "h_b_cg"
        return self._reopen_self()

    def state_goto_g_a_local(self):
        self.state = "g_a_local"
        return self._reopen_self()

    def state_goto_a_c_action(self):
        # self.state = "a_c_action"
        self.state = "not_supported"
        return self._reopen_self()

    def state_goto_a_d_view(self):
        # self.state = "a_d_view"
        self.state = "not_supported"
        return self._reopen_self()

    def state_goto_not_supported(self):
        self.state = "not_supported"
        return self._reopen_self()

    def state_goto_c_existing_module(self):
        self.state = "c_existing_module"
        return self._reopen_self()

    def state_goto_i_new_remote_system(self):
        self.state = "i_new_remote_system"
        self.working_system_id = False
        self.is_force_local_system = False
        return self._reopen_self()

    def state_goto_i_local_system(self):
        self.state = "i_new_remote_system"
        self.working_system_id = self.env.ref(
            "erplibre_devops.devops_system_local"
        ).id
        self.is_force_local_system = True
        self.system_name = self.working_system_id.name_overwrite
        return self._reopen_self()

    def state_goto_c_a_model(self):
        self.state = "c_a_model"
        return self._reopen_self()

    # def state_exit_configure(self):
    #     self.state = 'custom'

    def state_previous_not_supported(self):
        self.state = "init"

    def state_previous_a_autopoiesis_devops(self):
        self.state = "init"

    def state_previous_a_a_model(self):
        self.state = "a_autopoiesis_devops"

    def state_previous_a_b_field(self):
        self.state = "a_autopoiesis_devops"

    def state_previous_i_new_remote_system(self):
        self.state = "init"

    def state_previous_a_c_action(self):
        self.state = "a_autopoiesis_devops"

    def state_previous_a_d_view(self):
        self.state = "a_autopoiesis_devops"

    def state_previous_a_f_devops_regen(self):
        self.state = "a_autopoiesis_devops"

    def state_previous_f_new_project_society(self):
        self.state = "init"

    def state_previous_g_test_erplibre(self):
        self.state = "init"

    def state_previous_g_a_local(self):
        self.state = "g_test_erplibre"

    def state_previous_g_b_TODODO(self):
        self.state = "g_new_module"

    def state_previous_h_run_test(self):
        self.state = "init"

    #
    # def state_previous_h_a_test_plan_exec(self):
    #     self.state = "h_run_test"

    def state_previous_h_b_cg(self):
        self.state = "h_run_test"

    def state_exit_c_a_model(self):
        with self.root_workspace_id.devops_create_exec_bundle(
            "Plan c_a_model"
        ) as wp_id:
            module_name = (
                self.working_module_id.name
                if self.working_module_id
                else self.working_module_name
            )
            self.generate_new_model(
                wp_id, module_name, "Existing module new model"
            )

    def ssh_system_open_terminal(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        self.working_system_id.execute_terminal_gui(
            force_no_sshpass_no_arg=True
        )
        return self._reopen_self()

    def search_workspace_from_system(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        self.working_system_id.action_search_workspace()
        return self._reopen_self()

    def ssh_system_install_minimal(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        self.working_system_id.action_install_dev_system()
        return self._reopen_self()

    def ssh_system_install_docker(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        self.working_system_id.action_install_dev_system()
        return self._reopen_self()

    def ssh_system_install_dev(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        self.working_system_id.action_install_dev_system()
        return self._reopen_self()

    def ssh_system_install_production(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        self.working_system_id.action_install_dev_system()
        return self._reopen_self()

    def ssh_system_install_all(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        self.working_system_id.action_install_dev_system()
        return self._reopen_self()

    def ssh_system_create_workspace(self):
        if not self.working_system_id:
            # TODO manage this error
            return
        ws_value = {
            "system_id": self.working_system_id.id,
            "folder": self.workspace_folder,
            "erplibre_mode": self.erplibre_mode.id,
            "image_db_selection": self.image_db_selection.id,
        }
        ws_id = self.env["devops.workspace"].create(ws_value)
        self.create_workspace_id = ws_id.id
        # TODO missing check status before continue
        # TODO missing with workspace me to catch error
        ws_id.action_install_workspace()
        ws_id.action_start()
        # TODO implement detect when website is up or cancel state with error
        time.sleep(5)
        ws_id.action_restore_db_image()
        ws_id.action_open_local_view()
        return self._reopen_self()

    def search_subsystem_workspace(self):
        system_ids = (
            self.root_workspace_id.system_id.get_local_system_id_from_ssh_config()
        )
        for system_id in system_ids:
            if system_id.ssh_connection_status:
                # TODO the connection status is never activate for new remote system
                system_id.action_search_workspace()
        return self._reopen_self()

    def ssh_create_and_test(self):
        system_name = self.system_name
        if not system_name:
            system_name = "New remote system " + uuid.uuid4().hex[:6]
        system_value = {
            "name_overwrite": system_name,
            "parent_system_id": self.root_workspace_id.system_id.id,
            "method": "ssh",
            "ssh_use_sshpass": True,
            "ssh_host": self.ssh_host,
            "ssh_user": self.ssh_user,
            "ssh_password": self.ssh_password,
        }
        system_id = self.env["devops.system"].create(system_value)
        self.working_system_id = system_id
        try:
            # Just open and close the connection
            with self.working_system_id.ssh_connection():
                pass
        except Exception:
            pass
        return self._reopen_self()

    def ssh_test_system_exist(self):
        if not self.working_system_id:
            raise exceptions.Warning(
                "Missing SSH system id from plan Wizard, wrong configuration,"
                " please contact your administrator."
            )
        if self.system_name:
            self.working_system_id.name_overwrite = self.system_name
        self.working_system_id.ssh_host = self.ssh_host
        self.working_system_id.ssh_user = self.ssh_user
        self.working_system_id.ssh_password = self.ssh_password
        self.working_system_id.ssh_use_sshpass = True
        try:
            # Just open and close the connection
            with self.working_system_id.ssh_connection():
                pass
        except Exception:
            pass
        return self._reopen_self()

    def state_exit_g_new_module(self):
        with self.root_workspace_id.devops_create_exec_bundle(
            "Plan g_new_module"
        ) as wp_id:
            module_name = self.working_module_name
            if self.working_module_name_suggestion:
                module_path = self.working_module_name_suggestion
            else:
                module_path = self.working_module_path
            self.generate_new_model(
                wp_id,
                module_name,
                "New empty module",
                is_new_module=True,
                module_path=module_path,
                is_relative_path=True,
            )

    def state_exit_g_a_local(self):
        with self.root_workspace_id.devops_create_exec_bundle(
            "Plan g_a_local"
        ) as wp_id:
            self.erplibre_mode = self.env.ref(
                "erplibre_devops.erplibre_mode_docker_test"
            ).id
            # Create a workspace with same system of actual workspace, will be in test mode
            dct_wp = {
                "system_id": wp_id.system_id.id,
                "folder": f"/tmp/test_erplibre_{uuid.uuid4()}",
                "erplibre_mode": self.erplibre_mode.id,
                "image_db_selection": self.image_db_selection.id,
            }
            local_wp_id = self.env["devops.workspace"].create(dct_wp)
            self.create_workspace_id = local_wp_id.id
            local_wp_id.action_install_workspace()
            local_wp_id.action_start()
            # TODO implement detect when website is up or cancel state with error
            time.sleep(5)
            local_wp_id.action_restore_db_image()
            if self.enable_package_srs:
                local_wp_id.install_module("project_srs")
            local_wp_id.action_open_local_view()
            # finally
            self.state = "final"

    def state_exit_a_a_model(self):
        with self.root_workspace_id.devops_create_exec_bundle(
            "Plan a_a_model"
        ) as wp_id:
            module_name = "erplibre_devops"
            self.generate_new_model(
                wp_id, module_name, "Autopoiesis", is_autopoiesis=True
            )

    def state_exit_a_f_devops_regen(self):
        with self.root_workspace_id.devops_create_exec_bundle(
            "Plan a_f_devops_regen"
        ) as wp_id:
            # TODO this is a bug, no need that in reality, but action_code_generator_generate_all loop into it
            # Project
            cg_id = self.env["devops.cg"].create(
                {
                    "name": "Autopoiesis regenerate",
                    "devops_workspace_ids": [(6, 0, wp_id.ids)],
                    "force_clean_before_generate": self.force_generate,
                }
            )
            # Module
            cg_module_id = self.env["devops.cg.module"].create(
                {
                    "name": "erplibre_devops",
                    "code_generator": cg_id.id,
                    "devops_workspace_ids": [(6, 0, wp_id.ids)],
                }
            )
            plan_cg_value = {
                "workspace_id": wp_id.id,
                "cg_self_add_config_cg": True,
                "path_working_erplibre": wp_id.folder,
                "code_mode_context_generator": "autopoiesis",
                "mode_view": "same_view",
                "devops_cg_ids": [(6, 0, cg_id.ids)],
                "devops_cg_module_ids": [(6, 0, cg_module_id.ids)],
                "devops_cg_model_ids": [(6, 0, [])],
                "devops_cg_field_ids": [(6, 0, [])],
                "stop_execution_if_env_not_clean": not self.force_generate,
                "use_internal_cg": self.use_internal_cg,
            }
            plan_cg_id = self.env["devops.plan.cg"].create(plan_cg_value)
            # Generate
            plan_cg_id.action_code_generator_generate_all()
            self.generated_new_project_id = plan_cg_id.last_new_project_cg.id
            self.plan_cg_id = plan_cg_id.id
            self.working_cg_module_id = (
                self.plan_cg_id.last_code_generator_module.id
            )
            self.working_cg_writer_id = (
                self.plan_cg_id.last_code_generator_writer.id
            )
            # Format module
            cmd_format = (
                f"./script/maintenance/format.sh"
                f" ./addons/ERPLibre_erplibre_addons/erplibre_devops"
            )
            wp_id.execute(
                cmd=cmd_format,
                run_into_workspace=True,
                to_instance=True,
            )
            # finally
            self.state = "final"

    def generate_new_model(
        self,
        wp_id,
        module_name,
        project_name,
        is_autopoiesis=False,
        module_path=None,
        is_relative_path=False,
        is_new_module=False,
    ):
        path_module = ""
        if not is_new_module:
            # Search relative path
            exec_id = wp_id.execute(
                cmd=(
                    "./script/addons/check_addons_exist.py --output_path -m"
                    f" {module_name}"
                ),
                run_into_workspace=True,
            )
            if exec_id.exec_status:
                raise exceptions.Warning(f"Cannot find module '{module_name}'")
            path_module = exec_id.log_all.strip()
        if module_path:
            # Overwrite it
            path_module = module_path
        if not path_module:
            raise exceptions.Warning(f"Cannot find module path.")
        if not is_relative_path:
            dir_name, basename = os.path.split(path_module)
            if dir_name.startswith(wp_id.folder):
                relative_path_module = dir_name[len(wp_id.folder) + 1 :]
            else:
                relative_path_module = dir_name
        else:
            relative_path_module = path_module

        # Project
        cg_id = self.env["devops.cg"].create(
            {
                "name": project_name,
                "devops_workspace_ids": [(6, 0, wp_id.ids)],
                "force_clean_before_generate": False,
            }
        )
        # Module
        cg_module_id = self.env["devops.cg.module"].create(
            {
                "name": module_name,
                "code_generator": cg_id.id,
                "devops_workspace_ids": [(6, 0, wp_id.ids)],
            }
        )
        # Model
        for cg_model_id in self.model_ids:
            cg_model_id.module_id = cg_module_id.id
            cg_model_id.devops_workspace_ids = [(6, 0, wp_id.ids)]
        lst_field_id = [b.id for a in self.model_ids for b in a.field_ids]
        # Field
        # cg_field_id = self.env[
        #     "devops.cg.field"
        # ].create(
        #     {
        #         "name": "size",
        #         "help": "Size of this example.",
        #         "type": "integer",
        #         "model_id": cg_model_id.id,
        #         "devops_workspace_ids": [(6, 0, wp_id.ids)],
        #     }
        # )
        plan_cg_value = {
            "workspace_id": wp_id.id,
            "mode_view": "new_view",
            "path_working_erplibre": wp_id.folder,
            "path_code_generator_to_generate": relative_path_module,
            "devops_cg_ids": [(6, 0, cg_id.ids)],
            "devops_cg_module_ids": [(6, 0, cg_module_id.ids)],
            "devops_cg_model_ids": [(6, 0, self.model_ids.ids)],
            "devops_cg_model_to_remove_ids": [
                (6, 0, self.model_to_remove_ids.ids)
            ],
            "devops_cg_field_ids": [(6, 0, lst_field_id)],
            "stop_execution_if_env_not_clean": not self.force_generate,
            "use_internal_cg": self.use_internal_cg,
        }
        if self.mode_view_snippet and self.mode_view_snippet != "no_snippet":
            plan_cg_value["mode_view_snippet"] = self.mode_view_snippet
            plan_cg_value[
                "mode_view_snippet_enable_template_website_snippet_view"
            ] = self.mode_view_snippet_enable_template_website_snippet_view
            plan_cg_value[
                "mode_view_snippet_template_generate_website_snippet_generic_mdl"
            ] = (
                self.mode_view_snippet_template_generate_website_snippet_generic_mdl
            )
            plan_cg_value[
                "mode_view_snippet_template_generate_website_snippet_ctrl_featur"
            ] = (
                self.mode_view_snippet_template_generate_website_snippet_ctrl_featur
            )
            plan_cg_value[
                "mode_view_snippet_template_generate_website_enable_javascript"
            ] = (
                self.mode_view_snippet_template_generate_website_enable_javascript
            )
            plan_cg_value[
                "mode_view_snippet_template_generate_website_snippet_type"
            ] = self.mode_view_snippet_template_generate_website_snippet_type
        if self.mode_view_portal and self.mode_view_portal != "no_portal":
            plan_cg_value["mode_view_portal"] = self.mode_view_portal
            plan_cg_value[
                "mode_view_portal_enable_create"
            ] = self.mode_view_portal_enable_create
            plan_cg_value[
                "mode_view_portal_enable_read"
            ] = self.mode_view_portal_enable_read
            plan_cg_value[
                "mode_view_portal_enable_update"
            ] = self.mode_view_portal_enable_update
            plan_cg_value[
                "mode_view_portal_enable_delete"
            ] = self.mode_view_portal_enable_delete
            plan_cg_value[
                "mode_view_portal_models"
            ] = self.mode_view_portal_models
        # Update configuration self-gen
        if is_autopoiesis:
            plan_cg_value["cg_self_add_config_cg"] = True
            plan_cg_value["code_mode_context_generator"] = "autopoiesis"
        # Generate
        plan_cg_id = self.env["devops.plan.cg"].create(plan_cg_value)
        plan_cg_id.action_code_generator_generate_all()
        self.generated_new_project_id = plan_cg_id.last_new_project_cg.id
        self.plan_cg_id = plan_cg_id.id
        self.working_cg_module_id = plan_cg_id.last_code_generator_module.id
        self.working_cg_writer_id = plan_cg_id.last_code_generator_writer.id
        # Format module
        cmd_format = (
            "./script/maintenance/format.sh"
            f" {relative_path_module}/{module_name}"
        )
        wp_id.execute(
            cmd=cmd_format,
            run_into_workspace=True,
            to_instance=True,
        )
        # Git add
        if is_new_module:
            lst_default_file = [module_name]
        else:
            lst_default_file = [
                f"{module_name}/__manifest__.py",
                f"{module_name}/security/ir.model.access.csv",
                f"{module_name}/views/menu.xml",
            ]
            if self.model_ids:
                lst_default_file.append(f"{module_name}/models/__init__.py")
                for cg_model_id in self.model_ids:
                    model_file_name = cg_model_id.name.replace(".", "_")
                    lst_default_file.append(
                        f"{module_name}/models/{model_file_name}.py"
                    )
                    lst_default_file.append(
                        f"{module_name}/views/{model_file_name}.xml"
                    )
        cmd_git_add = ";".join([f"git add '{a}'" for a in lst_default_file])
        # Git remove
        lst_default_file_rm = []
        if self.model_to_remove_ids:
            for cg_model_id in self.model_to_remove_ids:
                model_file_name = cg_model_id.name.replace(".", "_")
                lst_default_file_rm.append(
                    f"{module_name}/models/{model_file_name}.py"
                )
                lst_default_file_rm.append(
                    f"{module_name}/views/{model_file_name}.xml"
                )
        cmd_git_rm = ";".join([f"git rm '{a}'" for a in lst_default_file_rm])
        if cmd_git_add and cmd_git_rm:
            cmd_git = f"{cmd_git_add};{cmd_git_rm}"
        elif cmd_git_add:
            cmd_git = cmd_git_add
        elif cmd_git_rm:
            cmd_git = cmd_git_rm
        else:
            cmd_git = ""
        if cmd_git:
            wp_id.execute(
                cmd=cmd_git,
                folder=relative_path_module,
                run_into_workspace=True,
                to_instance=True,
            )
        # finally
        self.state = "final"

    @api.multi
    def action_git_commit(self):
        for rec in self:
            if rec.plan_cg_id:
                rec.plan_cg_id.action_git_commit()
        return self._reopen_self()
