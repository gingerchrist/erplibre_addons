import logging
import os

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class DevopsIdeBreakpoint(models.Model):
    _name = "devops.ide.breakpoint"
    _description = "Breakpoint IDE. It's not associate to a workspace."

    name = fields.Char()

    description = fields.Char()

    filename = fields.Char()

    filename_is_code_generator_demo_hooks_py = fields.Boolean()

    filename_is_template_hooks_py = fields.Boolean()

    filename_is_cg_hooks_py = fields.Boolean()

    no_line = fields.Integer(default=-1, help="Will be compute")

    keyword = fields.Char()

    ignore_test = fields.Boolean(
        help=(
            "Will ignore this breakpoint when do test, because it will fail"
            " for some reason."
        )
    )

    @staticmethod
    def get_no_line_breakpoint(key, file, ws):
        with ws.devops_create_exec_bundle("Get no line breakpoint") as rec:
            key = key.replace('"', '\\"')
            cmd = f'grep -n "{key}" {file}'
            cmd += " | awk -F: '{print $1}'"
            result = rec.execute(to_instance=True, cmd=cmd, engine="sh")
            try:
                lst_no_line = [
                    int(a) for a in result.log_all.strip().split("\n")
                ]
            except:
                raise Exception(
                    f"Wrong output command : {cmd}\n{result.log_all.strip()}"
                )
            return lst_no_line

    @api.multi
    def get_breakpoint_info(self, ws, new_project_id=None):
        with ws.devops_create_exec_bundle("Get breakpoint info") as rec_ws:
            lst_all_no_line = []
            for rec in self:
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
                lst_all_no_line.append((filename, lst_no_line))
        return lst_all_no_line

    @api.multi
    def open_file_ide(self):
        ws_id = self.env["devops.workspace"].search(
            [("is_me", "=", True)], limit=1
        )
        if not ws_id:
            return
        for o_rec in self:
            with ws_id.devops_create_exec_bundle(
                "Get breakpoint info"
            ) as rec_ws:
                rec_ws.with_context(
                    breakpoint_id=o_rec.id
                ).ide_pycharm.action_start_pycharm()
