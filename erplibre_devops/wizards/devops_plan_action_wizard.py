from odoo import _, api, fields, models


class DevopsPlanActionWizard(models.TransientModel):
    _name = "devops.plan.action.wizard"
    _description = "Devops planification do an action with a specific workflow"
    _inherit = ["multi.step.wizard.mixin"]

    name = fields.Char()

    root_workspace_id = fields.Many2one(
        comodel_name="devops.workspace",
        string="Root workspace",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
        ondelete="cascade",
        help="Workspace where to execute the action.",
    )

    root_workspace_id_is_me = fields.Boolean(related="root_workspace_id.is_me")

    generated_new_project_id = fields.Many2one(
        comodel_name="devops.cg.new_project",
        string="Generated project",
    )

    state = fields.Selection(default="init")

    has_next = fields.Boolean(compute="_compute_has_next")

    model_name = fields.Char(string="Model")

    # option_adding = fields.Selection([
    #     ('inherit', 'Inherit Model'),
    #     ('nomenclator', 'Nomenclator'),
    # ], required=True, default='nomenclator', help="Inherit to inherit a new model.\nNomenclator to export data.")

    # option_blacklist = fields.Selection([
    #     ('blacklist', 'Blacklist'),
    #     ('whitelist', 'Whitelist'),
    # ], required=True, default='whitelist', help="When whitelist, all selected fields will be added.\n"
    #                                             "When blacklist, all selected fields will be ignored.")

    # field_ids = fields.Many2many(
    #     comodel_name="ir.model.fields",
    #     string="Fields",
    #     help="Select the field you want to inherit or import data.",
    # )
    #
    # model_ids = fields.Many2many(
    #     comodel_name="ir.model",
    #     string="Models",
    #     help="Select the model you want to inherit or import data.",
    # )

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

    @api.model
    def _selection_state(self):
        return [
            ("init", "Init"),
            ("a_autopoiesis_devops", "Autopoiesis DevOps"),
            ("a_a_model", "Model"),
            ("a_b_field", "Field"),
            ("a_c_action", "Action"),
            ("a_d_view", "View"),
            ("b_new_module", "New module"),
            ("c_existing_module", "Existing module"),
            ("d_import_data", "Import data"),
            ("e_migrate_from_external_ddb", "Migrate from external database"),
            ("not_supported", "Not supported"),
            ("final", "Final"),
        ]

    def state_goto_a_autopoiesis_devops(self):
        self.state = "a_autopoiesis_devops"
        return self._reopen_self()

    def state_goto_a_a_model(self):
        self.state = "a_a_model"
        return self._reopen_self()

    def state_goto_a_b_field(self):
        self.state = "a_b_field"
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

    def state_previous_a_c_action(self):
        self.state = "a_autopoiesis_devops"

    def state_previous_a_d_view(self):
        self.state = "a_autopoiesis_devops"

    def state_exit_a_a_model(self):
        wp_id = self.root_workspace_id
        # Project
        cg_id = self.env["devops.code_generator"].create(
            {
                "name": "Autopoiesis",
                "devops_workspace_ids": [(6, 0, wp_id.ids)],
                "force_clean_before_generate": False,
            }
        )
        # Module
        cg_module_id = self.env["devops.code_generator.module"].create(
            {
                "name": "erplibre_devops",
                "code_generator": cg_id.id,
                "devops_workspace_ids": [(6, 0, wp_id.ids)],
            }
        )
        # Model
        cg_model_id = self.env["devops.code_generator.module.model"].create(
            {
                "name": self.model_name,
                "description": "Example feature to add to devops",
                "module_id": cg_module_id.id,
                "devops_workspace_ids": [(6, 0, wp_id.ids)],
            }
        )
        # Field
        # cg_field_id = self.env[
        #     "devops.code_generator.module.model.field"
        # ].create(
        #     {
        #         "name": "size",
        #         "help": "Size of this example.",
        #         "type": "integer",
        #         "model_id": cg_model_id.id,
        #         "devops_workspace_ids": [(6, 0, wp_id.ids)],
        #     }
        # )
        # Overwrite information
        wp_id.devops_code_generator_ids = [(6, 0, cg_id.ids)]
        wp_id.devops_code_generator_module_ids = [(6, 0, cg_module_id.ids)]
        wp_id.devops_code_generator_model_ids = [(6, 0, [cg_model_id.id])]
        wp_id.devops_code_generator_field_ids = [(6, 0, [])]
        # Update configuration self-gen
        wp_id.cg_self_add_config_cg = True
        wp_id.mode_view = "new_view"
        # Generate
        wp_id.action_cg_erplibre_devops()
        self.generated_new_project_id = wp_id.last_new_project_self.id
        # finally
        self.state = "final"
