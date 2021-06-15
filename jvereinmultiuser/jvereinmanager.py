import os
import jks
import sys
import time
import base64
import logging
import textwrap
import traceback
import subprocess
from time import sleep
from Crypto.PublicKey import RSA
import xml.etree.ElementTree as ET
from typing import Dict, Optional, List
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

_DEFAULT_PATHS = {
    "windows": {
        "JAMEICA_EXEC": r"C:\Program Files\Jameica\jameica-start.bat",
        "PLUGIN_XML": r"C:\Program Files\Jameica\plugin.xml",
        "JAVA": r"C:\Program Files\Jameica\javaruntime\bin\java.exe",
        "H2_DIR": r"C:\Program Files\Jameica\lib\h2",
    },
    "linux": {
        "JAMEICA_EXEC": "/opt/jameica/jameica.sh",
        "PLUGIN_XML": "/opt/jameica/plugin.xml",
        "JAVA": "/opt/jameica/javaruntime/bin/java",
        "H2_DIR": "/opt/jameica/lib/h2",
    },
    "macos": {
        "JAMEICA_EXEC": "/Applications/Jameica.app/jameica-macos64.sh",
        "PLUGIN_XML": "/Applications/Jameica.app/plugin.xml",
        "JAVA": "/Applications/Jameica.app/javaruntime/bin/java",
        "H2_DIR": "/Applications/Jameica.app/lib/h2",
    }
}

platform = "linux"
if sys.platform.startswith("win32") or sys.platform.startswith("cygwin"):
    platform = "windows"
elif sys.platform.startswith("darwin"):
    platform = "macos"


DEFAULT_JAMEICA_EXEC_PATH = _DEFAULT_PATHS[platform]["JAMEICA_EXEC"]
DEFAULT_PLUGIN_XML_PATH = _DEFAULT_PATHS[platform]["PLUGIN_XML"]
DEFAULT_JAVA_PATH = _DEFAULT_PATHS[platform]["JAVA"]
DEFAULT_H2_DIR = _DEFAULT_PATHS[platform]["H2_DIR"]


class JameicaVersionDiffersError(Exception):
    """ The current Jameica version is different than the expected one """

    def __init__(self, expected_version, current_version, *args: object) -> None:
        super().__init__(*args)
        self.expected_version = expected_version
        self.current_version = current_version


class DecryptionError(Exception):
    """ Decryption failed """


class JVereinManager:

    def __init__(self,
                 local_repo_dir: str,
                 user_properties: Optional[Dict[str, Dict[str, str]]] = None,
                 jameica_exec_path: Optional[str] = None,
                 plugin_xml_path: Optional[str] = None,
                 java_path: Optional[str] = None,
                 h2_jar_dir: Optional[str] = None):

        self._logger = logging.getLogger(__name__)

        self._local_repo_dir = os.path.expanduser(local_repo_dir)
        self.user_properties = user_properties if user_properties else {}

        self._jameica_path = (jameica_exec_path if jameica_exec_path
                              else DEFAULT_JAMEICA_EXEC_PATH)
        self._plugin_xml_path = (plugin_xml_path if plugin_xml_path
                                 else DEFAULT_PLUGIN_XML_PATH)
        self._java_path = (java_path if java_path
                           else DEFAULT_JAVA_PATH)
        self._h2_jar_path = self._get_h2_jar_path(
            h2_jar_dir if h2_jar_dir
            else DEFAULT_H2_DIR)

        self._jameica_dir = os.path.join(self._local_repo_dir, "jameica")
        self._dump_dir = os.path.join(self._local_repo_dir, "dump")
        self._keystore_path = os.path.join(self._jameica_dir, "cfg", "jameica.keystore")

        self._databases = []

        self.expected_jameica_version = None
        self._current_jameica_version = None

    @staticmethod
    def _get_h2_jar_path(h2_dir: str) -> str:
        # reversed: if there are multiple .jar files, we use the newest one
        for filename in sorted(os.listdir(h2_dir), reverse=True):
            if filename.startswith("h2-") and filename.endswith(".jar"):
                return os.path.join(h2_dir, filename)
        return ""

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
                                    user_value = self.user_properties[config_path][prop]
                                except KeyError:
                                    pass
                                else:
                                    self._logger.debug(f"set user value {prop}={user_value} for file {config_path}")
                                    out_line = f"{prop}={user_value}\n"
                        content += f"{out_line}"

                with open(full_config_path, "w") as f:
                    f.write(content)
            except FileNotFoundError:
                self._logger.info(f"Unable to set user properties (file not found): {full_config_path}")
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

        self.user_properties = new_user_properties

    def _decrypt_passphrase(self, encrypted_base64_passphrase: str, keystore_password: str) -> str:
        encrypted_bytes = base64.b64decode(encrypted_base64_passphrase.encode('ascii'))

        try:
            keystore = jks.KeyStore.load(self._keystore_path, keystore_password)
        except jks.KeystoreSignatureException:
            self._logger.error(f"unable to load the keystore. incorrect password?")
            self._logger.info(f"keystore file: {self._keystore_path}")
            raise DecryptionError()
        try:
            pk_entry = keystore.private_keys["jameica"]
        except KeyError:
            self._logger.error(f"the keystore at '{self._keystore_path}' doesn't contain a private key named 'jameica'")
            raise DecryptionError()

        try:
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
        except:
            traceback.print_exc(file=sys.stdout)
            raise DecryptionError()

        return f"{passphrase} {passphrase}"

    def _load_properties_file(self, filepath, sep='=', comment_char='#'):
        """
        Read the file passed as parameter as a properties file.

        based on https://stackoverflow.com/a/31852401
        https://docs.oracle.com/javase/6/docs/api/java/util/Properties.html#load(java.io.Reader)
        """
        props = {}
        try:
            with open(filepath, "rt") as f:
                for line in f:
                    l = line.strip()
                    if l and not l.startswith(comment_char):
                        key_value = l.split(sep)
                        key = key_value[0].strip()
                        value = sep.join(key_value[1:]).strip().strip('"')
                        value = value.replace(r"\r", "\r")
                        value = value.replace(r"\n", "\n")
                        props[key] = value
        except FileNotFoundError:
            self._logger.warning(f"unable to read properties file (file not found): '{filepath}'")
        return props

    def _register_database(self, db_path: str, username: str, passphrase: str):
        self._databases.append((db_path, "", username, passphrase))

    def _register_encrypted_database(self,
                                     db_path: str,
                                     username: str,
                                     properties_file_path: str,
                                     property_name: str,
                                     master_password: str):

        properties = self._load_properties_file(properties_file_path)
        try:
            encrypted_passphrase = properties[property_name]
        except KeyError:
            self._logger.warning(
                f"unable to register database '{db_path}': "
                f"No such property named '{property_name} in '{properties_file_path}'")
            return
        passphrase = self._decrypt_passphrase(encrypted_passphrase, master_password)
        self._databases.append((f"{db_path}", ";CIPHER=XTEA", username, passphrase))

    def _register_all_databases(self, master_password: str):
        self._register_database(
            db_path=os.path.join(self._jameica_dir, "jverein", "h2db", "jverein"),
            username="jverein",
            passphrase="jverein"
        )
        self._register_encrypted_database(
            db_path=os.path.join(self._jameica_dir, "hibiscus", "h2db", "hibiscus"),
            username="hibiscus",
            properties_file_path=os.path.join(
                self._jameica_dir, "cfg", "de.willuhn.jameica.hbci.rmi.HBCIDBService.properties"),
            property_name="database.driver.h2.encryption.encryptedpassword",
            master_password=master_password
        )
        self._register_encrypted_database(
            db_path=os.path.join(self._jameica_dir, "hibiscus.mashup", "h2db", "mashup"),
            username="mashup",
            properties_file_path=os.path.join(
                self._jameica_dir, "cfg", "de.derrichter.hibiscus.mashup.rmi.MashupDBService.properties"),
            property_name="database.driver.h2.encryption.encryptedpassword",
            master_password=master_password
        )

    def _dump_and_delete_h2_database(self, db_path: str, db_options: str, username: str, passphrase: str):
        """
        Args:
            db_path: absolute database path without extension
        """

        possible_paths = [
            f"{db_path}.mv.db",
            f"{db_path}.h2.db"
        ]
        full_db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                full_db_path = path
                self._logger.debug(f"found database file at '{full_db_path}'")
                break
        if full_db_path is None:
            self._logger.warning(f"unable to dump database (file not found): {possible_paths}")
            return

        # http://h2database.com/html/tutorial.html#upgrade_backup_restore

        sql_file_path = f"{db_path}.sql"
        ret, stdout, stderr = self._execute_subprocess([
            self._java_path,
            "-cp", self._h2_jar_path,
            "org.h2.tools.Script",
            "-url", f"jdbc:h2:{db_path}{db_options}",
            "-user", username,
            "-password", passphrase,
            "-script", sql_file_path
        ])

        if ret != 0:
            raise Exception("Konnte Datenbank nicht dumpen.")

        os.unlink(full_db_path)

    def _execute_subprocess(self, args: List[str], cwd: Optional[str] = None, ignore_err: Optional[str] = None):
        self._logger.info(f"executing: '{' '.join(args)}'")

        proc = subprocess.run(args, capture_output=True, cwd=cwd)
        stdout_str = proc.stdout.decode()
        stderr_str = proc.stderr.decode()

        ret = proc.returncode
        if ignore_err and ignore_err in stderr_str:
            ret = 0

        log_level = logging.INFO if ret == 0 else logging.ERROR
        self._logger.log(log_level, f"RETURNCODE: {proc.returncode}")
        self._logger.log(log_level, f"STDOUT: {stdout_str}")
        self._logger.log(log_level, f"STDERR: {stderr_str}")

        return ret, stdout_str, stderr_str

    def _dump_and_delete_all_databases(self):
        for db, options, username, passphrase in self._databases:
            self._dump_and_delete_h2_database(db, options, username, passphrase)

    def _restore_h2_database(self, db_path: str, db_options: str, username: str, passphrase: str):
        """
        Args:
            db_path: absolute database path without extension
        """

        full_sql_path = f"{db_path}.sql"
        if not os.path.exists(full_sql_path):
            self._logger.warning(f"unable to restore database (file not found): {full_sql_path}")
            return

        # http://h2database.com/html/tutorial.html#upgrade_backup_restore

        ret, stdout, stderr = self._execute_subprocess([
            self._java_path,
            "-cp", self._h2_jar_path,
            "org.h2.tools.RunScript",
            "-url", f"jdbc:h2:{db_path}{db_options}",
            "-user", username,
            "-password", passphrase,
            "-script", full_sql_path
        ])

        if ret != 0:
            raise Exception("Konnte Datenbank nicht wiederherstellen.")

        os.unlink(full_sql_path)

    def _restore_all_databases(self):
        for db, options, username, passphrase in self._databases:
            self._restore_h2_database(db, options, username, passphrase)

    def _write_temporary_file(self, content: str) -> str:
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
            # http://www.h2database.com/html/grammar.html#csv_options
            temp_file.write(content.encode())
        return temp_file.name

    def _execute_sql(self, sql_statement: str, table_name: str, error_str: str):
        temp_file_path = None
        try:
            temp_file_path = self._write_temporary_file(content=sql_statement)

            dump_dir = os.path.join(self._local_repo_dir, "dump")
            try:
                os.makedirs(dump_dir)
            except FileExistsError:
                pass
            jverein_db_path = os.path.join(
                self._jameica_dir, "jverein", "h2db", "jverein")
            table_err_str = f"Table \"{table_name.upper()}\" not found"
            ret, stdout, stderr = self._execute_subprocess(
                [
                    self._java_path,
                    "-cp", self._h2_jar_path,
                    "org.h2.tools.RunScript",
                    "-url", f"jdbc:h2:{jverein_db_path}",
                    "-user", "jverein",
                    "-password", "jverein",
                    "-script", temp_file_path
                ],
                cwd=dump_dir,
                ignore_err=table_err_str
            )

            if ret != 0:
                self._logger.error(error_str)

            if table_err_str in stderr:
                self._logger.warning(f"{error_str}: Mitglieder-Tabelle existiert nicht")
        except Exception as e:
            raise e
        finally:
            os.unlink(temp_file_path)

    def _export_emails(self):
        """
        Export email addresses of all current members to dump/mitglieder-emails.csv

        Made for use with mailman's sync_members
        http://manpages.org/sync_members/8
        """

        sql_statement = textwrap.dedent(r"""
            CALL CSVWRITE(
                'mitglieder-emails.csv', 
                'SELECT LOWER(email) FROM mitglied 
                    WHERE eintritt <= CURDATE() 
                        AND (austritt IS NULL OR austritt >= CURDATE())
                    ORDER BY LOWER(email)', 
                STRINGDECODE(
                    'charset=UTF-8 escape=\" fieldDelimiter= lineSeparator=\n null= writeColumnHeader=false')
            );
        """.strip())

        self._execute_sql(sql_statement=sql_statement,
                          table_name="mitglied",
                          error_str="Konnte E-Mails nicht exportieren")

    def _export_emails_with_expiry_date(self):
        """
        Export email addresses and resignation date of all current members to dump/mitglieder-emails-austritt.csv

        Made for use with custom sync members script
        """

        sql_statement = textwrap.dedent(r"""
            CALL CSVWRITE(
                'mitglieder-emails-austritt.csv', 
                'SELECT LOWER(email), austritt FROM mitglied 
                    WHERE eintritt <= CURDATE() 
                        AND (austritt IS NULL OR austritt >= CURDATE()) 
                    ORDER BY LOWER(email)', 
                STRINGDECODE(
                    'charset=UTF-8 lineSeparator=\n null= writeColumnHeader=false')
            );
        """.strip())

        self._execute_sql(sql_statement=sql_statement,
                          table_name="mitglied",
                          error_str="Konnte E-Mails und Austrittsdaten nicht exportieren")

    @property
    def current_jameica_version(self):
        if self._current_jameica_version is None:
            self._current_jameica_version = self._get_jameica_version()
        return self._current_jameica_version

    def _get_jameica_version(self) -> str:
        tree = ET.parse(self._plugin_xml_path)
        root = tree.getroot()
        version = root.attrib["version"]
        self._logger.debug(f"current jameica version: {version}")
        return version

    def _check_expected_jameica_version(self):
        if not self.expected_jameica_version:
            self._logger.info(f"Ignoring Jameica version check")
            self.expected_jameica_version = self.current_jameica_version
            return

        if self.expected_jameica_version != self.current_jameica_version:
            raise JameicaVersionDiffersError(
                expected_version=self.expected_jameica_version,
                current_version=self.current_jameica_version)

    def setup(self, master_password: str):
        """
        Raises:
            JameicaVersionDiffersError: if the current Jameica version differs from the expected one
        """
        self._check_expected_jameica_version()
        self._insert_user_properties_into_properties_files()
        self._register_all_databases(master_password)
        self._restore_all_databases()

    def run_jameica(self, master_password: str):
        """
        blocking
        """

        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
        if self._logger.getEffectiveLevel() in [logging.DEBUG, logging.INFO]:
            stdout = None
            stderr = None

        # startup arguments:
        # https://github.com/willuhn/jameica/blob/master/src/de/willuhn/jameica/system/StartupParams.java#L80
        # -f: https://www.willuhn.de/wiki/doku.php?id=support:faq#abweichendes_benutzerverzeichnis_nutzen
        # -p: https://www.willuhn.de/wiki/doku.php?id=support:faq#wie_werden_meine_persoenlichen_daten_geschuetzt
        args = [
            self._jameica_path,
            "-f", self._jameica_dir,
            "-p", master_password
        ]
        self._logger.info(f"executing: {' '.join(args)}")
        env = os.environ.copy()
        try:
            del env["LD_LIBRARY_PATH"]
            # if LD_LIBRARY_PATH is set, java will fail with java.lang.UnsatisfiedLinkError
        except KeyError:
            pass
        subprocess.run(
            args,
            stdout=stdout,
            stderr=stderr,
            env=env,
            cwd=os.path.dirname(self._jameica_path))
        # cd to jameica_path (may be important for windows, needs verification)

        sleep(1)

    def teardown(self):
        self._reset_user_properties_in_properties_files()
        self._export_emails()
        self._export_emails_with_expiry_date()
        self._dump_and_delete_all_databases()
