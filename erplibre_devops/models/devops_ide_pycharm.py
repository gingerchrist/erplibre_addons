# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
import os
import re
import time

import xmltodict

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class DevopsIdePycharm(models.Model):
    _name = "devops.ide.pycharm"
    _description = "Pycharm management for a workspace"

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )

    is_installed = fields.Boolean(help="Will be true if project contain .idea")

    devops_workspace = fields.Many2one(
        comodel_name="devops.workspace",
        required=True,
    )

    line_file_tb_detected = fields.Text(
        help="Detected line to add breakpoint."
    )

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        result.action_pycharm_check()
        return result

    @api.depends(
        "devops_workspace.name",
    )
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.devops_workspace.name}"

    @api.multi
    def action_kill_pycharm(self):
        self.ensure_one()
        with self.devops_workspace.devops_create_exec_bundle(
            "Kill PyCharm"
        ) as rec:
            cmd = (
                "pkill -f $(ps aux | grep pycharm | grep -v grep | grep"
                " bin/java | awk '{print $11}')"
            )
            rec.execute(cmd=cmd, engine="")

    @api.multi
    def action_start_pycharm(self):
        self.ensure_one()
        with self.devops_workspace.devops_create_exec_bundle(
            "Start PyCharm"
        ) as rec_ws:
            cmd = (
                "~/.local/share/JetBrains/Toolbox/scripts/pycharm"
                f" {rec_ws.folder}"
            )
            rec_ws.execute(cmd=cmd, force_open_terminal=True, force_exit=True)

    @api.multi
    def action_pycharm_conf_init(self, ctx=None):
        for rec in self:
            with rec.devops_workspace.devops_create_exec_bundle(
                "Pycharm configuration init"
            ) as rec_ws:
                rec = rec.with_context(rec_ws._context)
                if not rec.is_installed:
                    rec.action_start_pycharm()
                    while not rec.is_installed:
                        time.sleep(3)
                        rec.action_pycharm_check()
                cmd = (
                    "source"
                    " ./.venv/bin/activate;./script/ide/pycharm_configuration.py"
                    " --init"
                )
                rec_ws.execute(cmd=cmd, run_into_workspace=True)

    @api.multi
    def action_pycharm_check(self, ctx=None):
        for rec in self:
            with rec.devops_workspace.devops_create_exec_bundle(
                "Pycharm check"
            ) as rec_ws:
                path_idea = os.path.join(rec_ws.folder, ".idea", "misc.xml")
                rec.is_installed = rec_ws.os_path_exists(path_idea)

    @api.multi
    def action_cg_setup_pycharm_debug(
        self, ctx=None, log=None, exec_error_id=None
    ):
        for rec in self:
            with rec.devops_workspace.devops_create_exec_bundle(
                "Setup PyCharm debug"
            ) as rec_ws:
                if not log:
                    log = rec_ws.devops_cg_erplibre_devops_log
                lst_exception = (
                    "odoo.exceptions.ValidationError:",
                    "Exception:",
                    "NameError:",
                    "AttributeError:",
                    "ValueError:",
                    "FileNotFoundError:",
                    "raise ValidationError",
                    "odoo.exceptions.CacheMiss:",
                    "Traceback (most recent call last):",
                )
                for exception in lst_exception:
                    index_error = log.rfind(exception)
                    if index_error >= 0:
                        break
                else:
                    _logger.info("Not exception found from log.")
                    continue
                # TODO search multiple path
                search_path = (
                    "File"
                    f' "{os.path.normpath(os.path.join(rec_ws.folder, "./addons"))}'
                )
                no_last_file_error = log.rfind(search_path, 0, index_error)
                no_end_line_error = log.find("\n", no_last_file_error)
                error_line = log[no_last_file_error:no_end_line_error]
                rec.line_file_tb_detected = error_line
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
                    exec_error_id.find_resolution = "error"
                    rec.try_find_why(log, exception, rec_ws, exec_error_id)
                    raise Exception("Cannot find breakpoint information")
                # -1 to line because start 0, but show 1
                line = str(line_breakpoint - 1)
                rec.line_file_tb_detected = error_line
                if exec_error_id:
                    exec_error_id.line_file_tb_detected = error_line
                    exec_error_id.find_resolution = "find"
                rec.add_breakpoint(filepath_breakpoint, line)

    def try_find_why(self, log, exception, ws, exec_error_id):
        id_devops_cg_new_project = self._context.get("devops_cg_new_project")
        if not id_devops_cg_new_project:
            return False
        devops_cg_new_project_id = (
            self.env["devops.cg.new_project"]
            .browse(id_devops_cg_new_project)
            .exists()
        )
        if not devops_cg_new_project_id:
            return False
        work_dir = os.path.normpath(
            os.path.join(
                ws.folder,
                devops_cg_new_project_id.directory,
                devops_cg_new_project_id.module,
            )
        )
        if exception == "NameError:":
            # Check 1, is not defined
            result = re.search(r"NameError: name '(\w+)' is not defined", log)
            if result:
                name_error = result.group(1)
                result = ws.execute(
                    to_instance=True,
                    folder=work_dir,
                    cmd=f'grep -nr "{name_error}" --include=\*.{{py,xml,js}}',
                )
                if exec_error_id and result.log_all:
                    exec_error_id.diagnostic_idea = result.log_all
                    exec_error_id.line_file_tb_detected = result.log_all
                    exec_error_id.find_resolution = "diagnostic"
                    return True
        elif exception == "ValueError:":
            # Check 1, while evaluating
            if 'while evaluating\n"' in log:
                value_error = log.split('while evaluating\n"')[1][:-1]
                if value_error:
                    s_value_error = value_error
                    if value_error[0] == "[":
                        s_value_error = f"\\{value_error}"
                    result = ws.execute(
                        to_instance=True,
                        folder=work_dir,
                        cmd=(
                            f'grep -nr \\"{s_value_error}\\"'
                            " --include=\*.{py,xml,js}"
                        ),
                        delimiter_bash='"',
                    )
                    if exec_error_id and result.log_all:
                        exec_error_id.diagnostic_idea = result.log_all
                        exec_error_id.line_file_tb_detected = result.log_all
                        exec_error_id.find_resolution = "diagnostic"
                        return True

        return False

    @api.model
    def add_breakpoint(self, file_path, line):
        with self.devops_workspace.devops_create_exec_bundle(
            "PyCharm add breakpoint"
        ) as rec_ws:
            url = file_path.replace(rec_ws.folder, "file://$PROJECT_DIR$/")
            dct_config_breakpoint = {
                "@enabled": "true",
                "@suspend": "THREAD",
                "@type": "python-line",
                "url": url,
                "line": line,
                # "option": {"@name": "timeStamp", "@value": "104"},
            }
            workspace_xml_path = os.path.join(
                rec_ws.folder, ".idea", "workspace.xml"
            )
            with open(workspace_xml_path) as xml:
                xml_as_string = xml.read()
                dct_project_xml = xmltodict.parse(xml_as_string)

            # Add a line-breakpoint
            project = dct_project_xml.get("project")
            if not project:
                raise Exception(
                    f"Cannot find <project> into {workspace_xml_path}"
                )
            component = project.get("component")
            if not component:
                raise Exception(
                    f"Cannot find <component> into {workspace_xml_path}"
                )
            for x_debug_manager in component:
                if x_debug_manager.get("@name") == "XDebuggerManager":
                    break
            else:
                raise Exception(
                    f"Cannot find <XDebuggerManager> into {workspace_xml_path}"
                )

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
                        ) and a_line_bp.get(
                            "line"
                        ) == dct_config_breakpoint.get(
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
    def action_reboot_force_os_workspace(self):
        self.ensure_one()
        self.devops_workspace.with_context(
            default_exec_reboot_process=True
        ).action_reboot()

    @api.multi
    def action_kill_workspace(self):
        self.ensure_one()
        self.devops_workspace.action_stop()
