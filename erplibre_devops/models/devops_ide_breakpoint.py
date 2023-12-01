import logging
import os

from odoo import _, api, exceptions, fields, models

_logger = logging.getLogger(__name__)


class DevopsIdeBreakpoint(models.Model):
    _name = "devops.ide.breakpoint"
    _description = "Breakpoint IDE. It's not associate to a workspace."

    name = fields.Char()

    description = fields.Char()

    method = fields.Char()

    filename = fields.Char()

    filename_is_code_generator_demo_hooks_py = fields.Boolean()

    filename_is_template_hooks_py = fields.Boolean()

    filename_is_cg_hooks_py = fields.Boolean()

    no_line = fields.Integer(
        default=-1,
        help="Will be compute",
    )

    keyword = fields.Char()

    condition_var_model_name = fields.Char(
        string="Variable model name",
        help=(
            "Will be a condition in the breakpoint, it contains the variable"
            " name about the model name."
        ),
    )

    condition_var_field_name = fields.Char(
        string="Variable field name",
        help=(
            "Will be a condition in the breakpoint, it contains the variable"
            " name about the field name."
        ),
    )

    condition_var_field_attr_name = fields.Char(
        string="Variable field attribute name",
        help=(
            "Will be a condition in the breakpoint, it contains the variable"
            " name about the field attribute."
        ),
    )

    condition_var_method_name = fields.Char(
        string="Variable method name",
        help=(
            "Will be a condition in the breakpoint, it contains the variable"
            " name about the method name."
        ),
    )

    condition_var_module_name = fields.Char(
        string="Variable module name",
        help=(
            "Will be a condition in the breakpoint, it contains the variable"
            " name about the module name."
        ),
    )

    condition_var_xml_id = fields.Char(
        string="Variable xml_id",
        help=(
            "Will be a condition in the breakpoint, it contains the variable"
            " name about the xml_id."
        ),
    )

    condition_var_short_xml_id = fields.Char(
        string="Variable short xml_id",
        help=(
            "Will be a condition in the breakpoint, it contains the variable"
            " name about the xml_id without the module name."
        ),
    )

    ignore_test = fields.Boolean(
        help=(
            "Will ignore this breakpoint when do test, because it will fail"
            " for some reason."
        )
    )

    is_multiple = fields.Boolean(
        help="Support multiple breakpoint for this file and key."
    )

    generated_by_execution = fields.Boolean(
        help=(
            "This breakpoint is generated by the software and not the"
            " developer."
        )
    )

    @staticmethod
    def get_no_line_breakpoint(key, file, ws):
        with ws.devops_create_exec_bundle("Get no line breakpoint") as rec:
            key = key.replace('"', '\\"').replace("[", "\[").replace("]", "\]")
            cmd = f'grep -n "{key}" {file}'
            cmd += " | awk -F: '{print $1}'"
            result = rec.execute(to_instance=True, cmd=cmd, engine="sh")
            log_all = result.log_all.strip()
            if not log_all:
                raise Exception(
                    f"Cannot find breakpoint into file '{file}' with key"
                    f" '{key}'. Command : {cmd}"
                )
            if "No such file or directory" in log_all:
                raise exceptions.Warning(f"No such file '{file}'")
            if log_all:
                try:
                    return [int(a) for a in log_all.split("\n")]
                except:
                    raise Exception(f"Wrong output command : {cmd}\n{log_all}")

    @api.multi
    def get_breakpoint_info(self, ws, new_project_id=None, condition=None):
        for rec in self:
            with ws.devops_create_exec_bundle("Get breakpoint info") as rec_ws:
                rec = rec.with_context(rec_ws._context)
                lst_all_no_line = []
                if rec.filename_is_code_generator_demo_hooks_py:
                    if not new_project_id:
                        continue
                    filename = new_project_id.code_generator_demo_hooks_py
                elif rec.filename_is_template_hooks_py:
                    if not new_project_id:
                        continue
                    filename = new_project_id.template_hooks_py
                elif rec.filename_is_cg_hooks_py:
                    if not new_project_id:
                        continue
                    filename = new_project_id.cg_hooks_py
                else:
                    if not rec.filename:
                        _logger.warning(
                            "Missing filename for breakpoint name"
                            f" '{rec.name}'"
                        )
                        continue
                    filename = rec.filename

                filename = os.path.normpath(
                    os.path.join(rec_ws.folder, filename)
                )
                lst_no_line = rec.get_no_line_breakpoint(
                    rec.keyword, filename, rec_ws
                )
                if lst_no_line:
                    s_cond = None
                    if condition:
                        s_cond = condition
                    elif new_project_id:
                        s_cond = rec.get_condition_str(
                            value_model=new_project_id.breakpoint_condition_model_name,
                            value_field=new_project_id.breakpoint_condition_field_name,
                            value_field_attr=new_project_id.breakpoint_condition_field_attribute_name,
                            value_method_name=new_project_id.breakpoint_condition_method_name,
                            value_module_name=new_project_id.breakpoint_condition_module_name,
                            value_xml_id=new_project_id.breakpoint_condition_xml_id,
                            value_short_xml_id=new_project_id.breakpoint_condition_short_xml_id,
                        )
                    tpl_info = (filename, lst_no_line, s_cond)
                    lst_all_no_line.append(tpl_info)
        return lst_all_no_line

    @api.multi
    def open_file_ide(self):
        ws_id = self.env["devops.workspace"].search(
            [("is_me", "=", True)], limit=1
        )
        if not ws_id:
            return
        for o_rec in self:
            with ws_id.devops_create_exec_bundle("Open file IDE") as rec_ws:
                rec_ws.with_context(
                    breakpoint_id=o_rec.id
                ).ide_pycharm.action_start_pycharm()

    @api.multi
    def get_condition_str(
        self,
        value_model=None,
        value_field=None,
        value_field_attr=None,
        value_method_name=None,
        value_module_name=None,
        value_xml_id=None,
        value_short_xml_id=None,
    ):
        lst_condition = []
        for rec in self:
            if rec.condition_var_model_name and value_model is not None:
                lst_condition.append(
                    f'{rec.condition_var_model_name}=="{value_model}"'
                )
            if rec.condition_var_field_name and value_field is not None:
                lst_condition.append(
                    f'{rec.condition_var_field_name}=="{value_field}"'
                )
            if (
                rec.condition_var_field_attr_name
                and value_field_attr is not None
            ):
                lst_condition.append(
                    f'{rec.condition_var_field_attr_name}=="{value_field_attr}"'
                )
            if rec.condition_var_method_name and value_method_name is not None:
                lst_condition.append(
                    f'{rec.condition_var_method_name}=="{value_method_name}"'
                )
            if rec.condition_var_module_name and value_module_name is not None:
                lst_condition.append(
                    f'{rec.condition_var_module_name}=="{value_module_name}"'
                )
            if rec.condition_var_xml_id and value_xml_id is not None:
                lst_condition.append(
                    f'{rec.condition_var_xml_id}=="{value_xml_id}"'
                )
            if rec.condition_var_short_xml_id and value_short_xml_id is not None:
                lst_condition.append(
                    f'{rec.condition_var_short_xml_id}=="{value_short_xml_id}"'
                )
        return " and ".join(lst_condition)
