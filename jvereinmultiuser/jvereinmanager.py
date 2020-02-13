import os.path
import logging
import subprocess
import re
from time import sleep
from tempfile import NamedTemporaryFile


class JvereinManager:

    def __init__(self, working_dir):
        self._logger = logging.getLogger(__name__)

        self._working_dir = working_dir

    def setup_jverein_paths(self):
        # config.user.working_dir
        # jameica_properties_file

        # Dateien, die das Arbeitsverzeichnis enthalten:
        # Platzhalter "JAMEICA_DIR" durch das Arbeitsverzeichnis ersetzen
        file_path = os.path.join(
            self._working_dir, "jameica", "cfg",
            "de.willuhn.jameica.services.ScriptingService.properties")
        with open(file_path, "r") as f:
            content = f.read()

        content = content.replace("JAMEICA_DIR",
                                  os.path.join(self._working_dir, "jameica"))
        if "\\" in os.path.join("a", "b"):  # windows-Pfade sind escaped
            content = content.replace("\\", "\\\\")
            content = content.replace("/", "\\\\")

        with open(file_path, "w") as f:
            f.write(content)

    def teardown_jverein_paths(self):
        # Arbeitsverzeichnis durch Platzhalter "JAMEICA_DIR" ersetzen
        file_path = os.path.join(
            self._working_dir, "jameica", "cfg",
            "de.willuhn.jameica.services.ScriptingService.properties")
        with open(file_path, "r") as f:
            content = f.read()

        content = content.replace("\\\\", "\\")
        content = content.replace(os.path.join(self._working_dir, "jameica"),
                                  "JAMEICA_DIR")
        content = content.replace("\\", "/")

        with open(file_path, "w") as f:
            f.write(content)

        # lastdir ausleeren (hier speichert jVerein den letzten aufgerufenen
        # Ordner im Datei-Öffnen-Dialog, um beim Nächsten Öffnen den Ordner direkt
        # parat zu haben)
        valid = re.compile(r"^(lastdir(\.sepa)?=).*$")  # r"\"(.*)\" {(.*)}")
        for filename in ["de.jost_net.JVerein.gui.control.AbrechnungSEPAControl.properties",
                         "de.jost_net.JVerein.gui.dialogs.ImportDialog.properties",
                         "de.jost_net.JVerein.gui.view.ImportView.properties"]:
            file_path = os.path.join(
                self._working_dir, "jameica", "cfg", filename)
            with open(file_path, "r") as f:
                newcontent = ""
                for line in f:
                    newline = line
                    if len(newline) > 0:
                        match = valid.match(newline)
                        if match is not None:
                            newline = match.groups()[0] + "\n"
                    newcontent += newline

            with open(file_path, "w") as f:
                f.write(newcontent)

    def dump_database(self, java_path, h2_jar_name):
        # mysqldump für h2
        sqldump_path = os.path.join(self._working_dir, "dump", "jverein.sql")
        h2_path = os.path.join(
            self._working_dir, "jameica", "jverein", "h2db", "jverein")
        jar_path = os.path.join(self._working_dir, "h2", h2_jar_name)
        dumpproc = subprocess.Popen([java_path,
                                     "-cp", jar_path,
                                     "org.h2.tools.Script",
                                     "-url", "jdbc:h2:" + h2_path,
                                     "-user", "jverein",
                                     "-password", "jverein",
                                     "-script", sqldump_path],
                                    shell=False, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        dumpproc.communicate()

        if dumpproc.returncode != 0:
            raise Exception("Konnte H2-Datenbank nicht dumpen.")

    def dump_emails(self, java_path, h2_jar_name):
        """ E-Mail-Liste in dump/mitglieder-emails.csv speichern """

        with NamedTemporaryFile(delete=False) as f:
            # tempfile mit SQL
            temp_path = f.name
            f.write(r"""CALL CSVWRITE('mitglieder-emails.csv', 'SELECT LOWER(EMAIL) FROM MITGLIED WHERE EINTRITT <= CURDATE() AND (AUSTRITT IS NULL OR AUSTRITT > CURDATE()) ORDER BY LOWER(EMAIL)', STRINGDECODE('charset=UTF-8 escape=\" fieldDelimiter= lineSeparator=\n null= writeColumnHeader=false'));""")

        try:
            # SQL starten
            sqldump_dir = os.path.join(self._working_dir, "dump")
            h2_path = os.path.join(
                self._working_dir, "jameica", "jverein", "h2db", "jverein")
            jar_path = os.path.join(self._working_dir, "h2", h2_jar_name)
            dumpproc = subprocess.Popen([java_path,
                                         "-cp", jar_path,
                                         "org.h2.tools.RunScript",
                                         "-url", "jdbc:h2:" + h2_path,
                                         "-user", "jverein",
                                         "-password", "jverein",
                                         "-script", f.name],
                                        shell=False, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        cwd=sqldump_dir)
            dumpproc.communicate()

            if dumpproc.returncode != 0:
                raise Exception("Konnte H2-Datenbank nicht dumpen.")
        except Exception as e:
            raise e
        finally:
            os.unlink(temp_path)

    def run_jverein(self, jameica_path):
        """
        blocking
        """
        subprocess.run(
            [jameica_path, "-f", self._working_dir],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=".")  # TODO: need to verify: cd to jameica executable directory. may be important for windows

        sleep(2)
