# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ----------------------------------------------------------
    # Selections
    # ----------------------------------------------------------

    def _system_terminal_selection(self):
        selections = self.env["it.system"]._fields["terminal"].selection
        return selections

    # ----------------------------------------------------------
    # Database
    # ----------------------------------------------------------

    default_terminal = fields.Selection(
        selection=lambda self: self._system_terminal_selection(),
        default="gnome-terminal",
        default_model="it.system",
        string="Default terminal system",
        help="Default terminal for new system.",
    )

    # ----------------------------------------------------------
    # Functions
    # ----------------------------------------------------------

    @api.multi
    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("erplibre_it.default_terminal", self.default_terminal)
        return res

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env["ir.config_parameter"].sudo()
        res.update(
            default_terminal=params.get_param(
                "erplibre_it.default_terminal", "gnome-terminal"
            )
        )
        return res

    def auto_select_terminal(self):
        params = self.env["ir.config_parameter"].sudo()
        default_value = False
        for key, value in self._system_terminal_selection():
            result = self.env["it.system"].execute_process(f"which {key}")
            if result:
                default_value = key
                break
        if default_value:
            params.set_param("erplibre_it.default_terminal", default_value)
            for rec in self.env["it.system"].search(
                [("terminal", "=", False)]
            ):
                rec.terminal = default_value
