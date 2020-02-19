import os
import jks
import time
import base64
import logging
import textwrap
import subprocess
from time import sleep
from typing import Dict
from Crypto.PublicKey import RSA
from tempfile import NamedTemporaryFile

# Attention!
# Jameica uses raw RSA encryption without padding (textbook RSA).
# pyca/cryptography doesn't support that:
# https://github.com/pyca/cryptography/issues/3604
# PyCyptodome also doesn't seem to support that (removed 'decrypt()'):
# https://pycryptodome.readthedocs.io/en/latest/src/vs_pycrypto.html
# -> so we need to use legacy PyCrypto

# monkey-patch for PyCrypto & Python 3.8,
# see https://github.com/dlitz/pycrypto/issues/283
time.clock = time.process_time


_USER_PROPERTIES_TEMPLATE = {
    "cfg/de.jost_net.JVerein.gui.action.FreiesFormularAction.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.action.PersonalbogenAction.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.action.SpendenbescheinigungPrintAction.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.AbrechnungSEPAControl.properties": {
        "lastdir.pdf": "",
        "lastdir.sepa": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.AbrechnungslaufBuchungenControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.BuchungsControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.BuchungsklasseSaldoControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.JahressaldoControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.MitgliedControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.MitgliedskontoControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.PreNotificationControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.control.SpendenbescheinigungControl.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.dialogs.ExportDialog.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.gui.view.MailDetailView$2.properties": {
        "lastdir": ""
    },
    "cfg/de.jost_net.JVerein.io.Kontoauszug.properties": {
        "lastdir": ""
    },
    "cfg/de.willuhn.jameica.gui.GUI.properties": {
        "main.width.0": "",
        "snapin.height.1": "",
        "snapin.height.0": "",
        "window.maximized": "",
        "main.width.1": "",
        "navi.height.1": "",
        "navi.height.0": "",
        "window.width": "",
        "window.height": "",
        "window.x": "",
        "window.y": ""
    },
}

"""
The file 'cfg/de.willuhn.jameica.services.ScriptingService.properties'
used to contain absolute paths. Since commit #5fc223f on Mar 23, 2015,
(probably Jameica 2.6.3) the paths are saved as relative paths, 
so no need to change this file anymore.
https://github.com/willuhn/jameica/commit/5fc223f9d0f240b4a8d5428a22ac98d529c59344
"""


class JVereinManager:

    def __init__(self,
                 local_repo_dir: str,
                 user_properties: Dict[str, Dict[str, str]],
                 java_path: str,
                 h2_jar_path: str):
        self._logger = logging.getLogger(__name__)

        self._local_repo_dir = os.path.expanduser(local_repo_dir)
        self._user_properties = user_properties
        self._java_path = java_path
        self._h2_jar_path = h2_jar_path

        self._jameica_dir = os.path.join(self._local_repo_dir, "jameica")
        self._dump_dir = os.path.join(self._local_repo_dir, "dump")
        self._keystore_path = os.path.join(self._jameica_dir, "cfg", "jameica.keystore")

        self._databases = [
            os.path.join(self._jameica_dir, "jverein", "h2db", "jverein"),
            os.path.join(self._jameica_dir, "hibiscus", "h2db", "hibiscus"),
            os.path.join(self._jameica_dir, "hibiscus.mashup", "h2db", "mashup"),
        ]

    @property
    def user_properties(self):
        return self._user_properties

    def _insert_user_properties_into_properties_files(self):
        """
        Replace user specific values in the .properties files with
        the values provided by self._user_properties
        """
        for config_path, properties in _USER_PROPERTIES_TEMPLATE.items():
            full_config_path = os.path.join(self._jameica_dir, *config_path.split("/"))
            content = ""
            try:
                with open(full_config_path, "r") as f:
                    for line in f:
                        out_line = line
                        for prop, template_value in properties.items():
                            if line.startswith(f"{prop}="):
                                try:
                                    user_value = self._user_properties[config_path][prop]
                                except KeyError:
                                    pass
                                else:
                                    self._logger.debug(f"set user value {prop}={user_value} for file {config_path}")
                                    out_line = f"{prop}={user_value}\n"
                        content += f"{out_line}"

                with open(full_config_path, "w") as f:
                    f.write(content)
            except FileNotFoundError:
                self._logger.warning(f"Unable to set user properties (file not found): {full_config_path}")
                continue

    def _reset_user_properties_in_properties_files(self):
        """
        Load the user specific values in the .properties files into self._user_properties
        and replace the values in the file with default values provided by _USER_PROPERTIES_TEMPLATE
        """
        new_user_properties = {}
        for config_path, properties in _USER_PROPERTIES_TEMPLATE.items():
            full_config_path = os.path.join(self._jameica_dir, *config_path.split("/"))
            content = ""
            try:
                with open(full_config_path, "r") as f:
                    for line in f:
                        out_line = line
                        for prop, template_value in properties.items():
                            if line.startswith(f"{prop}="):
                                new_user_value = line.lstrip(f"{prop}=").rstrip()
                                new_user_properties.setdefault(config_path, {})[prop] = new_user_value
                                out_line = f"{prop}={template_value}\n"
                        content += f"{out_line}"

                with open(full_config_path, "w") as f:
                    f.write(content)
            except FileNotFoundError:
                continue

        self._user_properties = new_user_properties

    def _decrypt_passphrase(self, encrypted_base64_passphrase: str, keystore_password: str) -> str:
        encrypted_bytes = base64.b64decode(encrypted_base64_passphrase.encode('ascii'))

        keystore = jks.KeyStore.load(self._keystore_path, keystore_password)
        try:
            pk_entry = keystore.private_keys["jameica"]
        except KeyError:
            raise KeyError(f"the keystore at '{self._keystore_path}' doesn't contain a private key named 'jameica'")

        private_key = "\n".join(
            [f"-----BEGIN RSA PRIVATE KEY-----"]
            + textwrap.wrap(base64.b64encode(pk_entry.pkey).decode('ascii'), 64)
            + [f"-----END RSA PRIVATE KEY-----"]
        ).encode()

        private_key_object = RSA.importKey(private_key)
        decrypted_bytes = private_key_object.decrypt(encrypted_bytes)

        # The passphrase for the hibiscus database (for both user and encryption)
        # is the base64 representation of the decrypted bytes, see:
        # https://github.com/willuhn/hibiscus/blob/a85117bc381f2f16937a95ceb72d9df9ca9261b2/src/de/willuhn/jameica/hbci/server/DBSupportH2Impl.java#L88
        # https://www.willuhn.de/wiki/doku.php?id=support:faq#wie_werden_meine_persoenlichen_daten_geschuetzt
        passphrase = base64.b64encode(decrypted_bytes).decode()

        return f"{passphrase} {passphrase}"

    def _dump_and_delete_h2_database(self, db_path: str):
        """
        Args:
            db_path: absolute database path without extension
        """

        full_db_path = f"{db_path}.mv.db"
        if not os.path.exists(full_db_path):
            self._logger.warning(f"unable to dump database (file not found): {full_db_path}")
            return

        # http://h2database.com/html/tutorial.html#upgrade_backup_restore

        sql_file_path = f"{db_path}.sql"
        proc = subprocess.run([self._java_path,
                               "-cp", self._h2_jar_path,
                               "org.h2.tools.Script",
                               "-url", f"jdbc:h2:{db_path}",
                               "-user", "jverein",
                               "-password", "jverein",
                               "-script", sql_file_path])

        if proc.returncode != 0:
            raise Exception("Konnte Datenbank nicht dumpen.")

        os.unlink(full_db_path)

    def _dump_and_delete_all_databases(self):
        for db in self._databases:
            self._dump_and_delete_h2_database(db)

    def _restore_h2_database(self, db_path: str):
        """
        Args:
            db_path: absolute database path without extension
        """

        full_sql_path = f"{db_path}.sql"
        if not os.path.exists(full_sql_path):
            self._logger.warning(f"unable to restore database (file not found): {full_sql_path}")
            return

        # http://h2database.com/html/tutorial.html#upgrade_backup_restore

        proc = subprocess.run([self._java_path,
                               "-cp", self._h2_jar_path,
                               "org.h2.tools.RunScript",
                               "-url", f"jdbc:h2:{db_path}",
                               "-user", "jverein",
                               "-password", "jverein",
                               "-script", full_sql_path])

        if proc.returncode != 0:
            raise Exception("Konnte Datenbank nicht wiederherstellen.")

        os.unlink(full_sql_path)

    def _restore_all_databases(self):
        for db in self._databases:
            self._restore_h2_database(db)

    def _export_emails(self):
        """
        Export email addresses of all current members to dump/mitglieder-emails.csv

        Made for use with mailman's sync_members
        http://manpages.org/sync_members/8
        """

        try:
            with NamedTemporaryFile(delete=False) as temp_file:
                """
                The H2 script needs to re-open the file to execute it, but: 
                
                Whether the name can be used to open the file a second time, 
                while the named temporary file is still open,  varies across 
                platforms (it can be so used on Unix; it cannot on Windows NT or later).
                https://docs.python.org/3/library/tempfile.html
                
                -> To maintain compatibility with Windows, we need to delete the file
                manually in the 'finally' block.
                """

                # http://www.h2database.com/html/functions.html#csvwrite
                temp_file.write(textwrap.dedent(r"""
                    CALL CSVWRITE(
                        'mitglieder-emails.csv', 
                        'SELECT LOWER(email) FROM mitglied 
                            WHERE eintritt <= CURDATE() 
                                AND (austritt IS NULL OR austritt > CURDATE()) 
                            ORDER BY LOWER(email)', 
                        STRINGDECODE(
                            'charset=UTF-8 escape=\" fieldDelimiter= lineSeparator=\n null= writeColumnHeader=false')
                    );
                """.strip()).encode())

            dump_dir = os.path.join(self._local_repo_dir, "dump")
            try:
                os.makedirs(dump_dir)
            except FileExistsError:
                pass
            jverein_db_path = os.path.join(
                self._jameica_dir, "jverein", "h2db", "jverein")
            proc = subprocess.run([self._java_path,
                                   "-cp", self._h2_jar_path,
                                   "org.h2.tools.RunScript",
                                   "-url", f"jdbc:h2:{jverein_db_path}",
                                   "-user", "jverein",
                                   "-password", "jverein",
                                   "-script", temp_file.name],
                                  cwd=dump_dir)

            if proc.returncode != 0:
                raise Exception("Konnte E-Mails nicht exportieren.")
        except Exception as e:
            raise e
        finally:
            os.unlink(temp_file.name)

    def run_jverein(self, jameica_path):
        """
        blocking
        """
        subprocess.run(
            [jameica_path, "-f", self._local_repo_dir],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=".")  # cd to jameica_path (may be important for windows, needs verification)

        sleep(1)
