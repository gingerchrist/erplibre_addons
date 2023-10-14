# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
import os
import re

import xmltodict

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class ItIDEPycharm(models.Model):
    _name = "it.ide.pycharm"
    _description = "Pycharm management for a workspace"

    name = fields.Char()

    it_workspace = fields.Many2one("it.workspace", required=True)

    @api.multi
    def action_cg_setup_pycharm_debug(self):
        for rec in self:
            index_error = rec.it_workspace.it_cg_erplibre_it_log.rfind(
                "odoo.exceptions.ValidationError"
            )
            search_path = (
                "File"
                f' "{os.path.normpath(os.path.join(rec.folder, "./addons"))}'
            )
            no_last_file_error = rec.it_workspace.it_cg_erplibre_it_log.rfind(
                search_path, 0, index_error
            )
            no_end_line_error = rec.it_workspace.it_cg_erplibre_it_log.find(
                "\n", no_last_file_error
            )
            error_line = rec.it_workspace.it_cg_erplibre_it_log[
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
                    rec.it_workspace.folder, "file://$PROJECT_DIR$/"
                ),
                "line": str(line_breakpoint - 1),
                # "option": {"@name": "timeStamp", "@value": "104"},
            }
            self._add_breakpoint(
                rec.it_workspace.folder, dct_config_breakpoint
            )

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
