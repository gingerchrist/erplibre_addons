# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import logging
import os
import shutil
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from glob import iglob

import paramiko

from odoo import _, api, exceptions, fields, models, tools
from odoo.service import db

_logger = logging.getLogger(__name__)
try:
    import pysftp
except ImportError:  # pragma: no cover
    _logger.debug("Cannot import pysftp")

class ITWorkspace(models.Model):
    _name = "it.workspace"
    _inherit = "mail.thread"
    _description = "ERPLibre IT Workspace"

    # _sql_constraints = [
    #     ("name_unique", "UNIQUE(name)", "Cannot duplicate a configuration."),
    #     (
    #         "days_to_keep_positive",
    #         "CHECK(days_to_keep >= 0)",
    #         "I cannot remove it_workspaces from the future. Ask Doc for that.",
    #     ),
    # ]

    name = fields.Char(
        compute="_compute_name",
        store=True,
        help="Summary of this it_workspace process",
    )

    it_workspace_format = fields.Selection(
        selection=[
            ("zip", "zip (includes filestore)"),
            ("dump", "pg_dump custom format (without filestore)"),
        ],
        default="zip",
        help="Choose the format for this it_workspace.",
    )

    log_workspace = fields.Text(
    )

    docker_compose_ps = fields.Text(
    )

    folder = fields.Char(
        required=True,
        default=lambda self: self._default_folder(),
        help="Absolute path for storing the it_workspaces",
    )

    method = fields.Selection(
        selection=[("local", "Local disk"), ("sftp", "Remote SFTP server")],
        default="local",
        help="Choose the storage method for this it_workspace.",
    )

    sftp_host = fields.Char(
        string="SFTP Server",
        help=(
            "The host name or IP address from your remote server. For example"
            " 192.168.0.1"
        ),
    )

    sftp_password = fields.Char(
        string="SFTP Password",
        help=(
            "The password for the SFTP connection. If you specify a private"
            " key file, then this is the password to decrypt it."
        ),
    )

    sftp_port = fields.Integer(
        string="SFTP Port",
        default=22,
        help="The port on the FTP server that accepts SSH/SFTP calls.",
    )

    port_http = fields.Integer(
        string="port http",
        default=8069,
        help="The port of http odoo.",
    )

    port_longpolling = fields.Integer(
        string="port longpolling",
        default=8071,
        help="The port of longpolling odoo.",
    )

    url_instance = fields.Char()

    url_instance_database_manager = fields.Char()

    force_create_docker_compose = fields.Boolean(
        default=True,
        help="Recreate docker-compose from configuration.",
    )

    sftp_private_key = fields.Char(
        string="Private key location",
        help=(
            "Path to the private key file. Only the Odoo user should have read"
            " permissions for that file."
        ),
    )

    sftp_public_host_key = fields.Char(
        string="Public host key",
        help=(
            "Verify SFTP server's identity using its public rsa-key. The host"
            " key verification protects you from man-in-the-middle attacks."
            " Can be generated with command 'ssh-keyscan -p PORT -H HOST/IP'"
            " and the right key is immediately after the words 'ssh-rsa'."
        ),
    )

    sftp_user = fields.Char(
        string="Username in the SFTP Server",
        help=(
            "The username where the SFTP connection should be made with. This"
            " is the user on the external server."
        ),
    )

    @api.model
    def _default_folder(self):
        """Default to ``it_workspaces`` folder inside current server datadir."""
        return os.path.join(
            tools.config["data_dir"], "backups", self.env.cr.dbname
        )

    @api.multi
    @api.depends("folder", "method", "sftp_host", "sftp_port", "sftp_user")
    def _compute_name(self):
        """Get the right summary for this job."""
        for rec in self:
            if rec.method == "local":
                rec.name = "%s @ localhost" % rec.folder
            elif rec.method == "sftp":
                rec.name = "sftp://%s@%s:%d%s" % (
                    rec.sftp_user,
                    rec.sftp_host,
                    rec.sftp_port,
                    rec.folder,
                )

    @api.multi
    @api.constrains("folder", "method")
    def _check_folder(self):
        """Do not use the filestore or you will backup your it_workspaces."""
        for record in self:
            if record.method == "local" and record.folder.startswith(
                tools.config.filestore(self.env.cr.dbname)
            ):
                raise exceptions.ValidationError(
                    _(
                        "Do not save it_workspaces on your filestore, or you will "
                        "it_workspace your it_workspaces too!"
                    )
                )

    @api.multi
    def action_sftp_test_connection(self):
        """Check if the SFTP settings are correct."""
        try:
            # Just open and close the connection
            with self.sftp_connection():
                raise exceptions.Warning(_("Connection Test Succeeded!"))
        except (
            pysftp.CredentialException,
            pysftp.ConnectionException,
            pysftp.SSHException,
        ):
            _logger.info("Connection Test Failed!", exc_info=True)
            raise exceptions.Warning(_("Connection Test Failed!"))

    def update_docker_compose_ps(self, rec):
        result = os.popen(f"cd {rec.folder};docker compose ps").read()
        rec.docker_compose_ps = f"\n{result}"

    @api.multi
    def action_stop_docker_compose(self):
        # Start with local storage
        for rec in self.filtered(lambda r: r.method == "local"):
            result = os.popen(f"cd {rec.folder};docker-compose down").read()
            self.update_docker_compose_ps(rec)

    @api.multi
    def action_docker_status(self):
        # Start with local storage
        for rec in self.filtered(lambda r: r.method == "local"):
            result = os.popen(f"cd {rec.folder};docker compose ps").read()
            rec.docker_compose_ps = f"\n{result}"
    @api.multi
    def action_open_terminal(self):
        # Start with local storage
        for rec in self.filtered(lambda r: r.method == "local"):
            os.popen(f"cd {rec.folder};gnome-terminal --window -- bash")

    # @api.multi
    def action_open_terminal_docker(self):
        # Start with local storage
        for rec in self.filtered(lambda r: r.method == "local"):
            workspace = os.path.basename(rec.folder)
            os.popen(f"cd {rec.folder};gnome-terminal --window -- bash -c 'docker exec -u root -ti {workspace}_ERPLibre_1 /bin/bash;bash'")

    def _exec_docker(self, rec, cmd):
        workspace = os.path.basename(rec.folder)
        # for "docker exec", command line need "-ti", but "popen" no need
        result = os.popen(f"""cd {rec.folder};docker exec -u root {workspace}_ERPLibre_1 /bin/bash -c \"{cmd}\"""").read()
        # time make doc_markdown
        # time make db_list
        # ./.venv/bin/python3 ./odoo/odoo-bin db --list --user_password mysecretpassword --user_login odoo
        # psycopg2.OperationalError: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: No such file or directory
        # 	Is the server running locally and accepting connections on that socket
        return result

    @api.multi
    def action_docker_restore_db_image(self):
        # Start with local storage
        for rec in self.filtered(lambda r: r.method == "local"):
            # TODO not working
            # maybe send by network REST web/database/restore
            # result = self._exec_docker(rec, "cd /ERPLibre;time ./script/database/db_restore.py --database test;")
            # rec.log_workspace = f"\n{result}"
            url_list = f"{rec.url_instance}/web/database/list"
            url_restore = f"{rec.url_instance}/web/database/restore"
            url_drop = f"{rec.url_instance}/web/database/drop"
            backup_file_path = "/home/mathben/git/erplibre_it/image_db/erplibre_base.zip"
            # backup_file_path = "/home/mathben/git/erplibre_it/image_db/erplibre_demo_full.zip"
            session = requests.Session()
            response = requests.get(url_list, data=json.dumps({}), headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
            if response.status_code == 200:
                database_list = response.json()
                print(database_list)
            else:
                print("une erreur")
                continue

            # Delete first
            result_db_list = database_list.get("result")
            if result_db_list:
                result_db_list = result_db_list[0]
                if result_db_list:
                    files = {'master_pwd': (None, 'admin'), 'name': (None, result_db_list)}
                    response = session.post(url_drop, files=files)
                    if response.status_code == 200:
                        print("Le drop a été envoyé avec succès.")
                    else:
                        print("Une erreur s'est produite lors du drop.")
                        # Strange, retry for test
                        time.sleep(1)
                        response = requests.get(url_list, data=json.dumps({}),
                                                headers={'Content-Type': 'application/json',
                                                         'Accept': 'application/json'})
                        if response.status_code == 200:
                            database_list = response.json()
                            print(database_list)

            with open(backup_file_path, 'rb') as backup_file:
                files = {'backup_file': (backup_file.name, backup_file, 'application/octet-stream'), 'master_pwd': (None, 'admin'), 'name':(None, 'test')}
                response = session.post(url_restore, files=files)
            if response.status_code == 200:
                print("Le fichier de restauration a été envoyé avec succès.")
            else:
                print("Une erreur s'est produite lors de l'envoi du fichier de restauration.")

            # f = {'file data': open('./image_db/erplibre_base.zip', 'rb')}
            # res = requests.post(url_restore, files=f)
            # print(res.text)

    @api.multi
    def action_it_check_workspace(self):
        """Run selected it_workspaces."""
        it_workspace = None
        successful = self.browse()

        # Start with local storage
        for rec in self.filtered(lambda r: r.method == "local"):
            filename = self.filename(datetime.now(), ext=rec.it_workspace_format)
            with rec.it_workspace_log():
                # Directory must exist
                try:
                    os.makedirs(rec.folder, exist_ok=True)
                except OSError:
                    pass

                rec.url_instance = f"http://127.0.0.1:{rec.port_http}"
                rec.url_instance_database_manager = f"{rec.url_instance}/web/database/manager"

                file_docker_compose = os.path.join(rec.folder, "docker-compose.yml")
                docker_compose_content = f"""
version: "3.3"
services:
  ERPLibre:
    image: technolibre/erplibre:1.5.0
    ports:
      - {rec.port_http}:8069
      - {rec.port_longpolling}:8072
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
    #command: odoo --workers 2
    command: odoo
    volumes:
      # See the volume section at the end of the file
      - erplibre_data_dir:/home/odoo/.local/share/Odoo
      - ./addons/addons:/ERPLibre/addons/addons
      - erplibre_conf:/etc/odoo
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
  erplibre-db-data:
"""
                if rec.force_create_docker_compose or not os.path.exists(file_docker_compose):
                    with open(file_docker_compose, "w") as destiny:
                        destiny.write(docker_compose_content)

                result = os.popen(f"cd {rec.folder};cat docker-compose.yml").read()
                rec.docker_compose_ps = result
                result = os.popen(f"cd {rec.folder};docker-compose up -d").read()
                rec.log_workspace = f"\n{result}"
                result = os.popen(f"cd {rec.folder};docker-compose ps").read()
                rec.log_workspace += f"\n{result}"
                self.update_docker_compose_ps(rec)

                result = self._exec_docker(rec, "cat /etc/odoo/odoo.conf;")
                has_change = False
                if "db_host" not in result:
                    result += "db_host = db\ndb_port = 5432\ndb_user = odoo\ndb_password = mysecretpassword\n"
                if "admin_passwd" not in result:
                    result += "admin_passwd = admin\n"
                str_to_replace = ",/ERPLibre/addons/OCA_connector-jira"
                if str_to_replace in result:
                    result = result.replace(str_to_replace, "")
                    has_change = True
                if has_change:
                    # TODO rewrite conf file and reformat
                    self._exec_docker(rec, f"echo -e '{result}' > /etc/odoo/odoo.conf")

        # Ensure a local it_workspace exists if we are going to write it remotely
        sftp = self.filtered(lambda r: r.method == "sftp")
        if sftp:
            for rec in sftp:
                filename = self.filename(datetime.now(), ext=rec.it_workspace_format)
                with rec.it_workspace_log():

                    cached = db.dump_db(
                        self.env.cr.dbname,
                        None,
                        it_workspace_format=rec.it_workspace_format,
                    )

                    with cached:
                        with rec.sftp_connection() as remote:
                            # Directory must exist
                            try:
                                remote.makedirs(rec.folder)
                            except pysftp.ConnectionException:
                                pass

                            # Copy cached it_workspace to remote server
                            with remote.open(
                                os.path.join(rec.folder, filename), "wb"
                            ) as destiny:
                                shutil.copyfileobj(cached, destiny)
                        successful |= rec

        # Remove old files for successful it_workspaces
        # successful.cleanup()

    @api.model
    def action_it_check_workspace_all(self):
        """Run all scheduled it_workspaces."""
        return self.search([]).action_it_check_workspace()

    @api.multi
    @contextmanager
    def it_workspace_log(self):
        """Log a it_workspace result."""
        try:
            _logger.info("Starting database it_workspace: %s", self.name)
            yield
        except Exception:
            _logger.exception("Database it_workspace failed: %s", self.name)
            escaped_tb = tools.html_escape(traceback.format_exc())
            self.message_post(  # pylint: disable=translation-required
                body="<p>%s</p><pre>%s</pre>"
                % (_("Database it_workspace failed."), escaped_tb),
                subtype=self.env.ref(
                    "erplibre_it_workspace.mail_message_subtype_failure"
                ),
            )
        else:
            _logger.info("Database it_workspace succeeded: %s", self.name)
            self.message_post(body=_("Database it_workspace succeeded."))

    @api.multi
    def cleanup(self):
        """Clean up old it_workspaces."""
        now = datetime.now()
        # for rec in self.filtered("days_to_keep"):
        #     with rec.cleanup_log():
        #         oldest = self.filename(now - timedelta(days=rec.days_to_keep))
        #
        #         if rec.method == "local":
        #             for name in iglob(os.path.join(rec.folder, "*.dump.zip")):
        #                 if os.path.basename(name) < oldest:
        #                     os.unlink(name)
        #
        #         elif rec.method == "sftp":
        #             with rec.sftp_connection() as remote:
        #                 for name in remote.listdir(rec.folder):
        #                     if (
        #                         name.endswith(".dump.zip")
        #                         and os.path.basename(name) < oldest
        #                     ):
        #                         remote.unlink("%s/%s" % (rec.folder, name))

    @api.multi
    @contextmanager
    def cleanup_log(self):
        """Log a possible cleanup failure."""
        self.ensure_one()
        try:
            _logger.info(
                "Starting cleanup process after database it_workspace: %s", self.name
            )
            yield
        except Exception:
            _logger.exception("Cleanup of old database it_workspaces failed: %s")
            escaped_tb = tools.html_escape(traceback.format_exc())
            self.message_post(  # pylint: disable=translation-required
                body="<p>%s</p><pre>%s</pre>"
                % (_("Cleanup of old database it_workspaces failed."), escaped_tb),
                subtype=self.env.ref("erplibre_it_workspace.failure"),
            )
        else:
            _logger.info(
                "Cleanup of old database it_workspaces succeeded: %s", self.name
            )

    @staticmethod
    def filename(when, ext="zip"):
        """Generate a file name for a it_workspace.

        :param datetime.datetime when:
            Use this datetime instead of :meth:`datetime.datetime.now`.
        :param str ext: Extension of the file. Default: dump.zip
        """
        return "{:%Y_%m_%d_%H_%M_%S}.{ext}".format(
            when, ext="dump.zip" if ext == "zip" else ext
        )

    @api.multi
    def sftp_connection(self):
        """Return a new SFTP connection with found parameters."""
        self.ensure_one()
        params = {
            "host": self.sftp_host,
            "username": self.sftp_user,
            "port": self.sftp_port,
        }

        # not empty sftp_public_key means that we should verify sftp server with it
        cnopts = pysftp.CnOpts()
        if self.sftp_public_host_key:
            key = paramiko.RSAKey(
                data=base64.b64decode(self.sftp_public_host_key)
            )
            cnopts.hostkeys.add(self.sftp_host, "ssh-rsa", key)
        else:
            cnopts.hostkeys = None

        _logger.debug(
            "Trying to connect to sftp://%(username)s@%(host)s:%(port)d",
            extra=params,
        )
        if self.sftp_private_key:
            params["private_key"] = self.sftp_private_key
            if self.sftp_password:
                params["private_key_pass"] = self.sftp_password
        else:
            params["password"] = self.sftp_password

        return pysftp.Connection(**params, cnopts=cnopts)
