import os.path
import logging
import subprocess
import re
from time import sleep
from tempfile import NamedTemporaryFile


class JvereinManager:

    def __init__(self, working_dir, jameica_properties_file):
        self._logger = logging.getLogger(__name__)

        self._working_dir = working_dir
        self._jameica_properties_file = jameica_properties_file

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

        # backup original ~/.jameica.properties file
        if os.path.exists(self._jameica_properties_file):
            # delete existing backup if there is one
            if os.path.exists(self._jameica_properties_file + ".bak"):
                os.unlink(self._jameica_properties_file + ".bak")
            # move
            os.rename(self._jameica_properties_file,
                      self._jameica_properties_file + ".bak")

        # create new .jameica.properties file
        # this allows us to start jameica without asking for the working directory
        with open(self._jameica_properties_file, "w") as f:
            jameica_path = os.path.join(self._working_dir, "jameica")
            if "\\" in os.path.join("a", "b"):
                # windows-Pfade sind escaped
                jameica_path = jameica_path.replace("\\", "\\\\")
                # der Doppelpunkt in dieser Datei auch
                jameica_path = jameica_path.replace(":", "\\:")
            f.write(f"dir={jameica_path}\n")
            f.write("ask=false")

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

        # remove our .jameica.properties file
        if os.path.exists(self._jameica_properties_file):
            os.unlink(self._jameica_properties_file)

        # restore backup of original file (if it exists)
        if os.path.exists(self._jameica_properties_file + ".bak"):
            os.rename(self._jameica_properties_file + ".bak",
                      self._jameica_properties_file)

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

    def run_jverein(self, jameica_path, jameica_cwd):
        """
        blocking
        """
        FNULL = open(os.devnull, "w")
        p = subprocess.Popen(jameica_path,
                             cwd=jameica_cwd,
                             shell=True,
                             stdin=None, stdout=FNULL, stderr=FNULL)
        p.wait()
        sleep(2)
