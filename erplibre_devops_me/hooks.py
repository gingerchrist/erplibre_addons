# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import os
import subprocess
import time

from odoo import SUPERUSER_ID, _, api

_logger = logging.getLogger(__name__)


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # Trick to attach a running process live
        # ok = False
        # first_print = False
        # while ok is False:
        #     time.sleep(1)
        #     if not first_print:
        #         first_print = True
        #         print(
        #             "Use PyCharm and do «Menu/Run/Attach to Process...»"
        #             " Ctrl+alt+5, and choose «./odoo/odoo-bin». I am waiting"
        #             " for ever! Add to watch «ok = True» + «Ctrl+Shift+Enter»."
        #         )

        # Generate system local
        if not os.environ.get("IS_ONLY_ME", False):
            env.ref(
                "erplibre_devops.devops_system_local"
            ).action_search_workspace()
        # select Selenium
        if os.environ.get("IS_ME_AUTO", False):
            subprocess.Popen(
                f"cd {os.getcwd()};./.venv/bin/python"
                " ./script/selenium/web_login_open_me_devops_auto.py",
                shell=True,
            )
        elif os.environ.get("IS_ME_AUTO_FORCE", False):
            subprocess.Popen(
                f"cd {os.getcwd()};./.venv/bin/python"
                " ./script/selenium/web_login_open_me_devops_auto_force.py",
                shell=True,
            )
        else:
            subprocess.Popen(
                f"cd {os.getcwd()};./.venv/bin/python"
                " ./script/selenium/web_login_open_me_devops.py",
                shell=True,
            )
