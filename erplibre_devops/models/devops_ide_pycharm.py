# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
import os
import re

import xmltodict

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class DevopsIdePycharm(models.Model):
    _name = "devops.ide.pycharm"
    _description = "Pycharm management for a workspace"

    name = fields.Char()

    devops_workspace = fields.Many2one(
        comodel_name="devops.workspace",
        required=True,
    )

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
        ) as rec:
            cmd = "~/.local/share/JetBrains/Toolbox/scripts/pycharm"
            rec.execute(cmd=cmd, force_open_terminal=True)

    @api.multi
    def action_cg_setup_pycharm_debug(self, ctx=None, log=None):
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
                )
                for exception in lst_exception:
                    index_error = log.rfind(exception)
                    if index_error >= 0:
                        break
                else:
                    _logger.info("Not exception found from log.")
                    continue
                search_path = (
                    "File"
                    f' "{os.path.normpath(os.path.join(rec_ws.folder, "./addons"))}'
                )
                no_last_file_error = log.rfind(search_path, 0, index_error)
                no_end_line_error = log.find("\n", no_last_file_error)
                error_line = log[no_last_file_error:no_end_line_error]
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
                line = str(line_breakpoint - 1)
                rec.add_breakpoint(filepath_breakpoint, line)

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
                _logger.error(
                    f"Cannot find <project> into {workspace_xml_path}"
                )
                return
            component = project.get("component")
            if not component:
                _logger.error(
                    f"Cannot find <component> into {workspace_xml_path}"
                )
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
