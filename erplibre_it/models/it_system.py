from odoo import _, api, exceptions, fields, models
import json
import logging
import os

_logger = logging.getLogger(__name__)
try:
    import paramiko
except ImportError:  # pragma: no cover
    _logger.debug("Cannot import paramiko")


class ItSystem(models.Model):
    _name = "it.system"
    _description = "it_system"

    name = fields.Char()

    it_workspace_ids = fields.One2many(
        comodel_name="it.workspace",
        inverse_name="system_id",
        string="It Workspace",
    )

    method = fields.Selection(
        selection=[("local", "Local disk"), ("ssh", "SSH remote server")],
        default="local",
        help="Choose the communication method.",
    )

    ssh_host = fields.Char(
        string="SSH Server",
        help=(
            "The host name or IP address from your remote server. For example"
            " 192.168.0.1"
        ),
    )

    ssh_password = fields.Char(
        string="SSH Password",
        help=(
            "The password for the SSH connection. If you specify a private"
            " key file, then this is the password to decrypt it."
        ),
    )

    ssh_port = fields.Integer(
        string="SSH Port",
        default=22,
        help="The port on the FTP server that accepts SSH calls.",
    )

    ssh_use_sshpass = fields.Boolean(
        string="SSH use SSHPass",
        default=False,
        help="This tool automatic add password to ssh connexion.",
    )

    keep_terminal_open = fields.Boolean(
        default=True,
        help="This will keep terminal open when close command.",
    )

    debug_command = fields.Boolean(
        default=False,
        help="This will show in log the command when execute it.",
    )

    ssh_private_key = fields.Char(
        string="Private key location",
        help=(
            "Path to the private key file. Only the Odoo user should have read"
            " permissions for that file."
        ),
    )

    ssh_public_host_key = fields.Char(
        string="Public host key",
        help=(
            "Verify SSH server's identity using its public rsa-key. The host"
            " key verification protects you from man-in-the-middle attacks."
            " Can be generated with command 'ssh-keyscan -p PORT -H HOST/IP'"
            " and the right key is immediately after the words 'ssh-rsa'."
        ),
    )

    ssh_user = fields.Char(
        string="Username in the SSH Server",
        help=(
            "The username where the SSH connection should be made with. This"
            " is the user on the external server."
        ),
    )

    @api.multi
    @api.depends("ssh_host", "ssh_port", "ssh_user")
    def _compute_name(self):
        """Get the right summary for this job."""
        for rec in self:
            if rec.method == "local":
                # rec.name = "%s @ localhost" % rec.name
                rec.name = "localhost"
            elif rec.method == "ssh":
                rec.name = "ssh://%s@%s:%d%s" % (
                    rec.ssh_user,
                    rec.ssh_host,
                    rec.ssh_port,
                )

    def execute_with_result(self, cmd):
        lst_result = []
        for rec in self.filtered(lambda r: r.method == "local"):
            result = os.popen(cmd).read()
            if len(self) == 1:
                return result
            lst_result.append(result)
        for rec in self.filtered(lambda r: r.method == "ssh"):
            with rec.ssh_connection() as ssh_client:
                stdin, stdout, stderr = ssh_client.exec_command(cmd)
                result = stdout.read().decode("utf-8")
                if len(self) == 1:
                    return result
                lst_result.append(result)
        return lst_result

    def execute_gnome_terminal(self, folder, cmd="", docker=False):
        for rec in self.filtered(lambda r: r.method == "local"):
            str_keep_open = ""
            if rec.keep_terminal_open:
                str_keep_open = ";bash"
            if cmd:
                docker_wrap_cmd = f"{cmd}{str_keep_open}"
            else:
                docker_wrap_cmd = ""
            if docker:
                workspace = os.path.basename(folder)
                docker_name = f"{workspace}-ERPLibre-1"
                docker_wrap_cmd = (
                    f"docker exec -u root -ti {docker_name} /bin/bash"
                )
                if cmd:
                    docker_wrap_cmd += f' -c "{cmd}{str_keep_open}"'
            if docker_wrap_cmd:
                cmd_output = (
                    f"cd {folder};gnome-terminal --window -- bash -c"
                    f" '{docker_wrap_cmd}'"
                )
                os.popen(cmd_output)
            else:
                cmd_output = f"cd {folder};gnome-terminal --window -- bash"
                os.popen(cmd_output)
            if rec.debug_command:
                print(cmd_output)
        for rec in self.filtered(lambda r: r.method == "ssh"):
            str_keep_open = ""
            if rec.keep_terminal_open:
                str_keep_open = ";bash"
            sshpass = ""
            if rec.ssh_use_sshpass:
                # TODO validate it exist before use it
                sshpass = f"sshpass -p {rec.ssh_password} "
            if cmd:
                docker_wrap_cmd = f"{cmd}{str_keep_open}"
            else:
                docker_wrap_cmd = ""
            if docker:
                workspace = os.path.basename(folder)
                docker_name = f"{workspace}-ERPLibre-1"
                docker_wrap_cmd = (
                    f"docker exec -u root -ti {docker_name} /bin/bash"
                )
                if cmd:
                    docker_wrap_cmd += f' -c \\"{cmd}{str_keep_open}\\"'
            if docker_wrap_cmd:
                cmd_output = (
                    f"gnome-terminal --window -- bash -c '{sshpass}ssh -t"
                    f' {rec.ssh_user}@{rec.ssh_host} "cd {folder};'
                    f" {docker_wrap_cmd}\"'"
                )
                os.popen(cmd_output)
            else:
                cmd_output = (
                    f"gnome-terminal --window -- bash -c '{sshpass}ssh -t"
                    f' {rec.ssh_user}@{rec.ssh_host} "cd {folder}; bash'
                    " --login\"'"
                )
                os.popen(cmd_output)
            if rec.debug_command:
                print(cmd_output)

    def exec_docker(self, cmd, folder):
        workspace = os.path.basename(folder)
        docker_name = f"{workspace}-ERPLibre-1"
        # for "docker exec", command line need "-ti", but "popen" no need
        # TODO catch error, stderr with stdout
        return self.execute_with_result(
            f"cd {folder};docker exec -u root {docker_name}"
            f' /bin/bash -c "{cmd}"'
        )

    @api.multi
    def action_ssh_test_connection(self):
        """Check if the SSH settings are correct."""
        try:
            # Just open and close the connection
            with self.ssh_connection():
                raise exceptions.Warning(_("Connection Test Succeeded!"))
        except (
            paramiko.AuthenticationException,
            paramiko.PasswordRequiredException,
            paramiko.BadAuthenticationType,
            paramiko.SSHException,
        ):
            _logger.info("Connection Test Failed!", exc_info=True)
            raise exceptions.Warning(_("Connection Test Failed!"))

    @api.multi
    def ssh_connection(self):
        """Return a new SSH connection with found parameters."""
        self.ensure_one()

        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=self.ssh_host,
            port=self.ssh_port,
            username=self.ssh_user,
            password=self.ssh_password,
        )
        # params = {
        #     "host": self.ssh_host,
        #     "username": self.ssh_user,
        #     "port": self.ssh_port,
        # }
        #
        # # not empty sftp_public_key means that we should verify sftp server with it
        # cnopts = pysftp.CnOpts()
        # if self.sftp_public_host_key:
        #     key = paramiko.RSAKey(
        #         data=base64.b64decode(self.sftp_public_host_key)
        #     )
        #     cnopts.hostkeys.add(self.sftp_host, "ssh-rsa", key)
        # else:
        #     cnopts.hostkeys = None
        #
        # _logger.debug(
        #     "Trying to connect to sftp://%(username)s@%(host)s:%(port)d",
        #     extra=params,
        # )
        # if self.sftp_private_key:
        #     params["private_key"] = self.sftp_private_key
        #     if self.sftp_password:
        #         params["private_key_pass"] = self.sftp_password
        # else:
        #     params["password"] = self.sftp_password
        #
        # return pysftp.Connection(**params, cnopts=cnopts)

        return ssh_client

    @api.multi
    def action_refresh_db_image(self):
        path_image_db = os.path.join(os.getcwd(), "image_db")
        for file_name in os.listdir(path_image_db):
            if file_name.endswith(".zip"):
                file_path = os.path.join(path_image_db, file_name)
                image_name = file_name[:-4]
                image_db_id = self.env["it.db.image"].search(
                    [("name", "=", image_name)]
                )
                if not image_db_id:
                    self.env["it.db.image"].create(
                        {"name": image_name, "path": file_path}
                    )
