# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import os
import subprocess

from odoo import SUPERUSER_ID, _, api

_logger = logging.getLogger(__name__)


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        env.ref(
            "erplibre_devops.devops_system_local"
        ).action_search_workspace()

        subprocess.Popen(
            f"cd {os.getcwd()};./.venv/bin/python"
            " ./script/selenium/web_login_open_me_devops.py",
            shell=True,
        )
