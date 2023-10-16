# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging
import os
import time

import requests

from odoo import _, api, exceptions, fields, models, tools

_logger = logging.getLogger(__name__)


class ItWorkspaceDocker(models.Model):
    _name = "it.workspace.docker"
    _description = "ERPLibre IT Workspace Docker"

    name = fields.Char(readonly=True, compute="_compute_name", store=True)

    workspace_id = fields.Many2one("it.workspace")

    docker_is_running = fields.Boolean(
        readonly=True,
        help="When false, it's because not running docker.",
        default=True,
    )

    force_create_docker_compose = fields.Boolean(
        default=True,
        help="Recreate docker-compose from configuration.",
    )

    docker_compose_ps = fields.Text()

    docker_version = fields.Char(default="technolibre/erplibre:1.5.0_c0c6f23")

    docker_cmd_extra = fields.Char(
        help="Extra command to share to odoo executable", default=""
    )

    docker_nb_proc = fields.Integer(
        help=(
            "Number of processor/thread, 0 if not behind a proxy, else 2 or"
            " more."
        ),
        default=0,
    )

    docker_config_gen_cg = fields.Boolean(
        default=False,
        help="Will reduce config path to improve speed to code generator",
    )

    docker_config_cache = fields.Char(
        help="Fill when docker_config_gen_cg is True, will be erase after",
    )

    docker_is_behind_proxy = fields.Boolean(
        help="Longpolling need a proxy when workers > 1", default=False
    )

    docker_initiate_succeed = fields.Boolean(
        help="Docker is ready to run", default=False
    )

    has_error_restore_db = fields.Boolean()

    @api.multi
    @api.depends("workspace_id", "docker_is_running")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.workspace_id.name} - {rec.docker_is_running}"

    @api.multi
    def action_start_docker_compose(self):
        for rec in self:
            rec.docker_is_running = False

            file_docker_compose = os.path.join(
                rec.workspace_id.folder, "docker-compose.yml"
            )
            if rec.docker_cmd_extra:
                docker_cmd_extra = f" {rec.docker_cmd_extra}"
            else:
                docker_cmd_extra = ""
            if rec.docker_is_behind_proxy:
                docker_behind_proxy = f" --proxy-mode"
                workers = f"--workers {max(2, rec.docker_nb_proc)}"
            else:
                docker_behind_proxy = ""
                workers = f"--workers {rec.docker_nb_proc}"
            docker_compose_content = f"""version: "3.3"
services:
  ERPLibre:
    image: {rec.docker_version}
    ports:
      - {rec.workspace_id.port_http}:8069
      - {rec.workspace_id.port_longpolling}:8072
    environment:
      HOST: db
      PASSWORD: mysecretpassword
      USER: odoo
      POSTGRES_DB: postgres
      STOP_BEFORE_INIT: "False"
      DB_NAME: ""
      UPDATE_ALL_DB: "False"
    depends_on:
      - db
    # not behind a proxy
    #command: odoo --workers 0
    # behind a proxy
    #command: odoo --workers 2 --proxy-mode
    command: odoo {workers}{docker_behind_proxy}{docker_cmd_extra}
    volumes:
      # See the volume section at the end of the file
      - erplibre_data_dir:/home/odoo/.local/share/Odoo
      - erplibre_conf:/etc/odoo
{'      - ' + '''
- '''.join([f'./{path}:{rec.workspace_id.path_working_erplibre}/{path}' for path in rec.workspace_id.path_code_generator_to_generate.split(";")]) if rec.workspace_id.path_code_generator_to_generate else ''}
    restart: always

  db:
    image: postgis/postgis:12-3.1-alpine
    environment:
      POSTGRES_PASSWORD: mysecretpassword
      POSTGRES_USER: odoo
      POSTGRES_DB: postgres
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - erplibre-db-data:/var/lib/postgresql/data/pgdata
    restart: always

# We configure volume without specific destination to let docker manage it. To configure it through docker use (read related documentation before continuing) :
# - docker volume --help
# - docker-compose down --help
volumes:
  erplibre_data_dir:
  erplibre_conf:
  erplibre-db-data:"""
            if rec.force_create_docker_compose or not os.path.exists(
                file_docker_compose
            ):
                rec.workspace_id.system_id.execute_with_result(
                    f"echo '{docker_compose_content}' > {file_docker_compose}",
                    engine="sh",
                )

            result = rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};cat docker-compose.yml"
            )
            rec.docker_compose_ps = result
            result = rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};docker compose up -d"
            )

            if (
                "Cannot connect to the Docker daemon at"
                " unix:///var/run/docker.sock. Is the docker daemon"
                " running?"
                in result
            ):
                rec.docker_initiate_succeed = False

            rec.log_workspace = f"\n{result}"
            result = rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};docker compose ps"
            )
            rec.log_workspace += f"\n{result}"
            rec.update_docker_compose_ps()

            result = rec.workspace_id.system_id.exec_docker(
                "cat /etc/odoo/odoo.conf;", rec.workspace_id.folder
            )
            has_change = False
            if "db_host" not in result:
                # TODO remove this information from executable of docker
                result += (
                    "db_host = db\ndb_port = 5432\ndb_user ="
                    " odoo\ndb_password = mysecretpassword\n"
                )
            if "admin_passwd" not in result:
                result += "admin_passwd = admin\n"
            # TODO remove repo OCA_connector-jira
            str_to_replace = f",{rec.workspace_id.path_working_erplibre}/addons/OCA_connector-jira"
            if str_to_replace in result:
                result = result.replace(str_to_replace, "")
                has_change = True

            if (
                rec.docker_config_gen_cg
                or not rec.docker_config_gen_cg
                and rec.docker_config_cache
            ):
                addons_path = None
                # TODO this is not good, need a script from manifest to rebuild this path
                if rec.docker_config_gen_cg:
                    addons_path = (
                        "addons_path ="
                        f" {rec.workspace_id.path_working_erplibre}/odoo/addons,"
                        f"{rec.workspace_id.path_working_erplibre}/{rec.workspace_id.path_code_generator_to_generate},"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_web,"
                        f"{rec.workspace_id.path_working_erplibre}/addons{rec.workspace_id.path_working_erplibre}_erplibre_addons,"
                        f"{rec.workspace_id.path_working_erplibre}/addons{rec.workspace_id.path_working_erplibre}_erplibre_theme_addons,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/MathBenTech_development,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/MathBenTech_erplibre-family-management,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/MathBenTech_odoo-business-spending-management-quebec-canada,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/MathBenTech_scrummer,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/Numigi_odoo-partner-addons,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/Numigi_odoo-web-addons,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_contract,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_geospatial,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_helpdesk,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_server-auth,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_server-brand,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_server-tools,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_server-ux,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_social,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/OCA_website,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/TechnoLibre_odoo-code-generator,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/TechnoLibre_odoo-code-generator-template,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/ajepe_odoo-addons,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/muk-it_muk_base,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/muk-it_muk_misc,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/muk-it_muk_web,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/muk-it_muk_website,"
                        f"{rec.workspace_id.path_working_erplibre}/addons/odoo_design-themes"
                    )
                elif not rec.docker_config_gen_cg and rec.docker_config_cache:
                    addons_path = rec.docker_config_cache
                    rec.docker_config_cache = ""

                # TODO use configparser instead of string parsing
                if addons_path:
                    lst_result = result.split("\n")
                    for i, a_result in enumerate(lst_result):
                        if a_result.startswith("addons_path = "):
                            if (
                                rec.docker_config_gen_cg
                                and not rec.docker_config_cache
                            ):
                                rec.docker_config_cache = a_result
                            lst_result[i] = addons_path
                            break
                    result = "\n".join(lst_result)
                    has_change = True

            if has_change:
                # TODO rewrite conf file and reformat
                rec.workspace_id.system_id.exec_docker(
                    f"echo -e '{result}' > /etc/odoo/odoo.conf",
                    rec.workspace_id.folder,
                )
            # TODO support only one file, and remove /odoo.conf
            rec.workspace_id.system_id.exec_docker(
                f"cd {rec.workspace_id.path_working_erplibre};cp"
                " /etc/odoo/odoo.conf ./config.conf;",
                rec.workspace_id.folder,
            )
            rec.action_docker_check_docker_ps()

    @api.multi
    def action_stop_docker_compose(self):
        for rec in self:
            rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};docker compose down"
            )
        self.update_docker_compose_ps()
        self.action_docker_check_docker_ps()

    def update_docker_compose_ps(self):
        for rec in self:
            result = rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};docker compose ps"
            )
            rec.docker_compose_ps = f"\n{result}"

    @api.multi
    def action_docker_status(self):
        for rec in self:
            result = rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};docker compose ps"
            )
            rec.docker_compose_ps = f"\n{result}"

    @api.multi
    def action_docker_check_docker_ps(self):
        for rec in self:
            result = rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};docker compose ps --format json"
            )
            # rec.docker_compose_ps = f"\n{result}"
            rec.docker_is_running = result

    @api.multi
    def action_docker_check_docker_tree_addons(self):
        for rec in self:
            result = rec.workspace_id.system_id.execute_with_result(
                f"cd {rec.workspace_id.folder};tree"
            )
            rec.workspace_id.it_code_generator_tree_addons = result

    @api.multi
    def docker_remove_module(self, module_id):
        for rec in self:
            rec.workspace_id.system_id.exec_docker(
                f"cd {rec.workspace_id.path_working_erplibre}/{rec.workspace_id.path_code_generator_to_generate};rm"
                f" -rf ./{module_id.name};",
                rec.workspace_id.folder,
            )
            rec.workspace_id.system_id.exec_docker(
                f"cd {rec.workspace_id.path_working_erplibre}/{rec.workspace_id.path_code_generator_to_generate};rm"
                f" -rf ./code_generator_template_{module_id.name};",
                rec.workspace_id.folder,
            )
            rec.workspace_id.system_id.exec_docker(
                f"cd {rec.workspace_id.path_working_erplibre}/{rec.workspace_id.path_code_generator_to_generate};rm"
                f" -rf ./code_generator_{module_id.name};",
                rec.workspace_id.folder,
            )

    @api.multi
    def action_docker_logs(self):
        for rec in self:
            rec.workspace_id.system_id.execute_gnome_terminal(
                rec.workspace_id.folder, cmd="docker compose logs -f"
            )

    @api.multi
    def action_open_terminal_docker(self):
        for rec in self:
            workspace = os.path.basename(rec.workspace_id.folder)
            docker_name = f"{workspace}-ERPLibre-1"
            rec.workspace_id.system_id.execute_gnome_terminal(
                rec.workspace_id.folder,
                cmd=f"docker exec -u root -ti {docker_name} /bin/bash",
            )

    @api.multi
    def action_docker_install_dev_soft(self):
        for rec in self:
            rec.workspace_id.system_id.exec_docker(
                f"apt update;apt install -y tig vim htop tree watch",
                rec.workspace_id.folder,
            )

    @api.multi
    def action_os_user_permission_docker(self):
        for rec in self:
            rec.workspace_id.system_id.execute_gnome_terminal(
                rec.workspace_id.folder,
                cmd=(
                    "sudo groupadd docker;sudo usermod -aG docker"
                    f" {rec.workspace_id.system_id.ssh_user}"
                ),
            )
            rec.workspace_id.system_id.execute_gnome_terminal(
                rec.workspace_id.folder,
                cmd="sudo systemctl start docker.service",
            )
            # TODO check if all good
        self.docker_initiate_succeed = True

    @api.multi
    def action_analyse_docker_image(self):
        for rec in self:
            rec.workspace_id.system_id.execute_gnome_terminal(
                rec.workspace_id.folder,
                cmd=f"dive {rec.docker_version}",
            )

    @api.multi
    def action_docker_restore_db_image(self):
        for rec in self:
            rec.has_error_restore_db = False
            # TODO not working
            # maybe send by network REST web/database/restore
            # result = rec.workspace_id.system_id.exec_docker(f"cd {rec.workspace_id.path_working_erplibre};time ./script/database/db_restore.py --database test;", rec.workspace_id.folder)
            # rec.log_workspace = f"\n{result}"
            url_list = f"{rec.workspace_id.url_instance}/web/database/list"
            url_restore = (
                f"{rec.workspace_id.url_instance}/web/database/restore"
            )
            url_drop = f"{rec.workspace_id.url_instance}/web/database/drop"
            if not rec.workspace_id.image_db_selection:
                # TODO create stage, need a stage ready to restore
                raise exceptions.Warning(_("Error, need field db_selection"))
            rec.workspace_id.db_is_restored = False
            backup_file_path = rec.workspace_id.image_db_selection.path
            session = requests.Session()
            response = requests.get(
                url_list,
                data=json.dumps({}),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            if response.status_code == 200:
                database_list = response.json()
                print(database_list)
            else:
                # TODO remove print
                print("une erreur")
                continue

            # Delete first
            # TODO cannot delete database if '-d database' argument -d is set
            result_db_list = database_list.get("result")
            if rec.workspace_id.db_name in result_db_list:
                print(result_db_list)
                files = {
                    "master_pwd": (None, "admin"),
                    "name": (None, rec.workspace_id.db_name),
                }
                response = session.post(url_drop, files=files)
                if response.status_code == 200:
                    print("Le drop a été envoyé avec succès.")
                else:
                    rec.docker_cmd_extra = ""
                    # TODO detect "-d" in execution instead of force action_reboot
                    rec.workspace_id.action_reboot()
                    next_second = 5
                    print(
                        "Une erreur s'est produite lors du drop, code"
                        f" '{response.status_code}'. Retry in"
                        f" {next_second} seconds"
                    )
                    # Strange, retry for test
                    time.sleep(next_second)
                    # response = requests.get(
                    #     url_list,
                    #     data=json.dumps({}),
                    #     headers={
                    #         "Content-Type": "application/json",
                    #         "Accept": "application/json",
                    #     },
                    # )
                    response = session.post(url_drop, files=files)
                    if response.status_code == 200:
                        # database_list = response.json()
                        # print(database_list)
                        print(
                            "Seconde essaie, le drop a été envoyé avec succès."
                        )
                    else:
                        print(
                            "Seconde essaie, une erreur s'est produite"
                            " lors du drop, code"
                            f" '{response.status_code}'."
                        )
                        rec.has_error_restore_db = True
                if not rec.has_error_restore_db:
                    response = requests.get(
                        url_list,
                        data=json.dumps({}),
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                        },
                    )
                    if response.status_code == 200:
                        database_list = response.json()
                        print(database_list)

            if not rec.has_error_restore_db:
                with open(backup_file_path, "rb") as backup_file:
                    files = {
                        "backup_file": (
                            backup_file.name,
                            backup_file,
                            "application/octet-stream",
                        ),
                        "master_pwd": (None, "admin"),
                        "name": (None, rec.workspace_id.db_name),
                    }
                    response = session.post(url_restore, files=files)
                if response.status_code == 200:
                    print(
                        "Le fichier de restauration a été envoyé avec succès."
                    )
                    rec.workspace_id.db_is_restored = True
                else:
                    print(
                        "Une erreur s'est produite lors de l'envoi du fichier"
                        " de restauration."
                    )

            # f = {'file data': open(f'./image_db{rec.workspace_id.path_working_erplibre}_base.zip', 'rb')}
            # res = requests.post(url_restore, files=f)
            # print(res.text)

    @api.multi
    def action_check_all(self):
        self.action_docker_status()
        self.action_docker_check_docker_ps()
        self.action_docker_check_docker_tree_addons()
