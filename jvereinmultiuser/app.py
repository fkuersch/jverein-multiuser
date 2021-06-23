#!/usr/bin/env python3

import os
import sys
import json
import pkgutil
import logging
import argparse
import requests
import textwrap
import traceback
import configparser
from typing import Optional
from getpass import getpass
import jvereinmultiuser.hooks as hooks
from jvereinmultiuser.gitlocker import GitLocker, GitError, IsLockedError
from jvereinmultiuser.jvereinmanager import (
    JVereinManager, JameicaVersionDiffersError, DecryptionError,
    DEFAULT_JAMEICA_EXEC_PATH, DEFAULT_PLUGIN_XML_PATH, DEFAULT_JAVA_PATH, DEFAULT_H2_DIR)


VERSION = "1.1.0"

_VERSION_URL = "https://github.com/fkuersch/jverein-multiuser/releases/latest/download/VERSION"
_RELEASE_URL = "https://github.com/fkuersch/jverein-multiuser/releases/latest"

_DEFAULT_USER_CONFIG = textwrap.dedent(f"""\
    [Author]
    #name = Max Mustermann
    #email = maxmustermann@example.org
    #computer = Maxis Laptop
    
    [Repository]
    #remote = ssh://user@git.example.org:~/jverein.git
    
    # Wenn Jameica mit Hibiscus-Mashup installiert wurde,
    # kann Folgendes ignoriert werden:
    #[Paths]
    #jameica_exec = {DEFAULT_JAMEICA_EXEC_PATH}
    #plugin_xml = {DEFAULT_PLUGIN_XML_PATH}
    #java = {DEFAULT_JAVA_PATH}
    #h2_dir = {DEFAULT_H2_DIR}
""")

if sys.platform.startswith("win32") or sys.platform.startswith("cygwin"):
    # Windows
    _DEFAULT_GIT_CMD = r"C:\Program Files\Git\bin\git.exe"
elif sys.platform.startswith("darwin"):
    # macOS
    _DEFAULT_GIT_CMD = "/usr/bin/git"
else:
    # Linux
    _DEFAULT_GIT_CMD = "/usr/bin/git"

_GITIGNORE_RESOURCE = os.path.join("resources", "jverein.gitignore")


class CancelAppException(Exception):
    """ App cancelled """


class App:

    def __init__(self, working_dir: str, check_for_updates: bool = True):
        self._working_dir = working_dir
        self._allow_check_for_updates = check_for_updates
        self._user_config_path = os.path.join(self._working_dir, "user_config.ini")
        self._jameica_config_path = os.path.join(self._working_dir, "jameica_config.json")
        self._local_repo_dir = os.path.join(self._working_dir, "repo")
        self._repo_config_path = os.path.join(self._local_repo_dir, "config.ini")

        self._user_config = configparser.ConfigParser()
        self._author_name = ""
        self._author_email = ""
        self._author_computer = ""
        self._remote_repo = ""

        self._jameica_user_properties = {}

        self._gitlocker: Optional[GitLocker] = None
        self._jverein_manager: Optional[JVereinManager] = None

        self._repo_config = configparser.ConfigParser()

    def _check_for_updates(self):
        if not self._allow_check_for_updates:
            return
        print("Suche nach Updates")
        try:
            r = requests.get(_VERSION_URL, timeout=5.0)
            update_version = r.text.strip()
            if update_version != VERSION:
                print(f"Es ist ein Update für jverein-multiuser verfügbar: {update_version}")
                print(f"Installiert ist: {VERSION}")
                print(f"Jetzt herunterladen: {_RELEASE_URL}")
            else:
                print("jverein-multiuser ist auf dem aktuellen Stand")
        except Exception as e:
            print(f"Suche nach Updates fehlgeschlagen: {e}")

    def _check_expected_jvereinmultiuser_version(self):
        if not self._expected_jvereinmultiuser_version:
            print("Repo setzt keine bestimmte Version von jverein-multiuser voraus.")
            return

        if self._expected_jvereinmultiuser_version == VERSION:
            return

        print("Die Version von jverein-multiuser hat sich geändert!")
        print(f"Erwartet:           {self._expected_jvereinmultiuser_version}")
        print(f"Auf deinem System:  {VERSION}")
        print("")
        print("Wenn du ein Update von jverein-multiuser durchgeführt hast, kannst du")
        print("das Update jetzt bestätigen. Die anderen Nutzer müssen dann")
        print("ebenfalls ein Update durchführen.")
        print("")
        print("Du hast folgende Optionen:")
        print("")
        print("   (u) Update bestätigen")
        print(f"          andere Nutzer müssen auf deine Version updaten ({VERSION})")
        print("   (q) Abbruch")
        print("          und selbst Update durchführen")

        response = self._user_input(["u", "q"])
        if response == "u":
            self._expected_jvereinmultiuser_version = VERSION
            # don't write config file since we don't have the lock (yet)
            # the config file will be written before the next commit
        else:
            raise CancelAppException()

    def _setup_working_dir(self):
        if not os.path.exists(self._working_dir):
            print(f"Neues Arbeitsverzeichnis wird angelegt: {self._working_dir}")
            os.makedirs(self._working_dir)

        if not os.path.exists(self._local_repo_dir):
            os.makedirs(self._local_repo_dir)

        if not os.path.exists(self._user_config_path):
            print(f"Beispiel-Konfigurationsdatei wird geschrieben: {self._user_config_path}")
            with open(self._user_config_path, "w") as f:
                f.write(_DEFAULT_USER_CONFIG)
            print("Bitte anpassen.")
            raise CancelAppException()

    def _read_user_config_file(self):
        self._user_config.read(self._user_config_path)
        expected_values = {
            "Author": ["name", "email", "computer"],
            "Repository": ["remote"],
        }
        for section, keys in expected_values.items():
            for key in keys:
                try:
                    assert self._user_config[section][key]
                except (KeyError, AssertionError):
                    print(f"Konfiguration nicht vollständig: '{section}.{key}' fehlt")
                    print(f"in Datei: {self._user_config_path}")
                    raise CancelAppException()

        self._author_name = self._user_config["Author"]["name"]
        self._author_email = self._user_config["Author"]["email"]
        self._author_computer = self._user_config["Author"]["computer"]
        self._remote_repo = self._user_config["Repository"]["remote"]

        self._path_jameica_exec = self._user_config.get("Paths", "jameica_exec", fallback=None)
        self._path_plugin_xml = self._user_config.get("Paths", "plugin_xml", fallback=None)
        self._path_java = self._user_config.get("Paths", "java", fallback=None)
        self._path_h2_dir = self._user_config.get("Paths", "h2_dir", fallback=None)

    def _read_repo_config_file(self):
        self._repo_config.read(self._repo_config_path)

    @property
    def _expected_jameica_version(self):
        return self._repo_config.get("Jameica", "expectedversion", fallback=None)

    @_expected_jameica_version.setter
    def _expected_jameica_version(self, value):
        self._repo_config.set("Jameica", "expectedversion", value)

    @property
    def _expected_jvereinmultiuser_version(self):
        return self._repo_config.get("JvereinMultiuser", "expectedversion", fallback=None)

    @_expected_jvereinmultiuser_version.setter
    def _expected_jvereinmultiuser_version(self, value):
        if not self._repo_config.has_section("JvereinMultiuser"):
            self._repo_config.add_section("JvereinMultiuser")
        self._repo_config.set("JvereinMultiuser", "expectedversion", value)

    def _write_repo_config_file(self):
        if (not self._expected_jameica_version
                and self._jverein_manager and self._jverein_manager.current_jameica_version):
            self._expected_jameica_version = self._jverein_manager.current_jameica_version
        if not self._expected_jvereinmultiuser_version:
            self._expected_jvereinmultiuser_version = VERSION
        with open(self._repo_config_path, "w") as f:
            self._repo_config.write(f)

    def _read_jameica_config_file(self):
        try:
            with open(self._jameica_config_path, "r") as f:
                self._jameica_user_properties = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            print("Benutzerspezifische Jameica-Einstellungen konnten nicht gelesen werden und werden zurückgesetzt.")
            self._jameica_user_properties = {}

    def _clone_repo_if_necessarry(self):
        if not self._gitlocker.is_local_repo_available():
            print(textwrap.dedent("""\
                Das Repository ist noch nicht eingerichtet.
                Soll das remote repository jetzt heruntergeladen werden?

                    (j)     Ja
                    (n)     Nein
            """))

            response = self._user_input(["j", "n"])
            if response == "j":
                print("Git-Repository wird heruntergeladen...")
                self._gitlocker.do_initial_setup(
                    initial_commit_data=pkgutil.get_data("jvereinmultiuser", _GITIGNORE_RESOURCE),
                    initial_commit_file_dst_path=".gitignore"
                )
                print("Herunterladen war erfolgreich.")
                if not self._gitlocker.is_synced_with_remote_repo():
                    print("Änderungen werden hochgeladen...")
                    self._gitlocker.push()
                    print("Hochladen war erfolgreich.")
            else:
                raise CancelAppException()

    def _create_gitignore_if_necessarry(self):
        repo_gitignore_path = os.path.join(self._local_repo_dir, ".gitignore")
        if not os.path.exists(repo_gitignore_path):
            print("Lege .gitignore-Datei an.")
            gitignore_data = pkgutil.get_data("jvereinmultiuser", _GITIGNORE_RESOURCE)
            with open(repo_gitignore_path, "wb") as f:
                f.write(gitignore_data)

    def run(self):
        try:
            self._check_for_updates()
            self._setup_working_dir()
            self._read_user_config_file()
            self._read_jameica_config_file()

            print("Du arbeitest als")
            print(f"Name/E-Mail:        {self._author_name} <{self._author_email}>")
            print(f"Computer-Name:      {self._author_computer}")
            print(f"Arbeitsverzeichnis: {self._working_dir}")
            print(f"Remote Repository:  {self._remote_repo}")
            print("")

            self._gitlocker = GitLocker(
                git_cmd=_DEFAULT_GIT_CMD,
                local_repo=self._local_repo_dir,
                remote_repo=self._remote_repo,
                author_name=self._author_name,
                author_email=self._author_email,
                instance_name=self._author_computer
            )

            self._jverein_manager = JVereinManager(
                local_repo_dir=self._local_repo_dir,
                user_properties=self._jameica_user_properties,
                jameica_exec_path=self._path_jameica_exec,
                plugin_xml_path=self._path_plugin_xml,
                java_path=self._path_java,
                h2_jar_dir=self._path_h2_dir
            )

            self._clone_repo_if_necessarry()

            # now, the repo exists
            self._read_repo_config_file()
            self._check_expected_jvereinmultiuser_version()
            self._jverein_manager.expected_jameica_version = self._expected_jameica_version

            locked_by_me = self._gitlocker.is_locked_by_me()
            clean = self._gitlocker.is_synced_with_remote_repo()
            if clean and not locked_by_me:
                self._gitlocker.pull()  # get current state

            locked_by_me = self._gitlocker.is_locked_by_me()
            locked = self._gitlocker.get_lock_info() is not None
            clean = self._gitlocker.is_synced_with_remote_repo()

            if not locked and clean:
                self._manage_unlocked_and_clean()
            elif locked_by_me and clean:
                self._manage_locked_by_me_and_clean()
            elif locked_by_me and not clean:
                self._manage_locked_by_me_and_not_clean()
            elif locked and clean:
                self._manage_locked_by_others_and_clean()
            # errors:
            elif locked and not clean:
                self._manage_locked_by_others_and_not_clean()
            elif not locked and not clean:
                self._manage_unlocked_and_not_clean()
            else:
                raise RuntimeError("Ungültiger Git-Status")
        except GitError as e:
            print("FEHLER! Bitte Log prüfen.")
            print(e)
            raise CancelAppException()
        except IsLockedError as e:
            print("FEHLER!")
            print(e)
            raise CancelAppException()

    def _user_input(self, options):
        response = ""
        while response not in options:
            response = input(f"[{'/'.join(options)}] ").lower()
        print("")
        return response

    def _pull_and_lock(self):
        print("Lade Änderungen herunter und fordere exklusiven Zugriff an.")
        self._gitlocker.pull_and_lock()
        self._create_gitignore_if_necessarry()

    def _upload_changes(self):
        self._write_repo_config_file()

        if self._gitlocker.need_to_commit():
            commit_message = ""
            while len(commit_message) <= 0:
                commit_message = input("Was hast du getan? (kurze commit-Message): ")
            self._gitlocker.stage_and_commit(commit_message)

        print("Lokale Änderungen werden hochgeladen")
        self._gitlocker.push()

        hooks.run_hook(hooks.PostUploadHook, self._local_repo_dir)

    def _ask_and_upload(self):
        print("    Möchtest Du jetzt die Änderungen hochladen?")
        response = self._user_input(["j", "n"])
        if response == "j":
            self._upload_changes()
            self._unlock()
            return True
        else:
            print("    Du  hast immer noch den exklusiven Zugriff!")
            print("    Bitte starte das Programm zeitnah neu, um ggf. weitere")
            print("    Änderungen vorzunehmen und den exklusiven Zugriff")
            print("    freizugeben.")
            return False

    def _unlock(self):
        print("Exklusiver Zugriff wird freigegeben")
        self._gitlocker.unlock()

    def _discard_changes(self):
        print("Lokale Änderungen werden gelöscht")
        self._gitlocker.delete_local_changes()

    def _handle_different_jameica_version(self, expected_version, current_version):
        print("Die Jameica-Version hat sich geändert!")
        print(f"Erwartet:           {expected_version}")
        print(f"Auf deinem System:  {current_version}")
        print("")
        print("Wenn du ein Jameica-Update durchgeführt hast, kannst du")
        print("das Update jetzt bestätigen. Die anderen Nutzer müssen dann")
        print("ebenfalls ein Update durchführen.")
        print("")
        print("Du hast folgende Optionen:")
        print("")
        print("   (u) Update bestätigen")
        print(f"          andere Nutzer müssen auf deine Version updaten ({current_version})")
        print("   (q) Abbruch")
        print("          und selbst Update durchführen")

        response = self._user_input(["u", "q"])
        if response == "u":
            self._expected_jameica_version = current_version
            self._jverein_manager.expected_jameica_version = current_version
            self._write_repo_config_file()
            # we can write the config file: when jameica needs to be started, we own the lock
        raise CancelAppException()

    def _ask_for_master_password(self) -> str:
        master_password = ""
        while len(master_password) <= 0:
            master_password = getpass(prompt="Master-Passwort für Jameica: ")
        return master_password

    def _run_jverein(self):
        master_password = self._ask_for_master_password()

        print("jVerein wird für Dich eingerichtet")
        try:
            self._jverein_manager.setup(master_password)
        except JameicaVersionDiffersError as e:
            self._handle_different_jameica_version(
                e.expected_version, e.current_version)
        except DecryptionError:
            print("FEHLER!")
            print("Master-Passwort falsch?")
            raise CancelAppException()

        running = True
        while running:
            print("jVerein wird gestartet")
            self._jverein_manager.run_jameica(master_password)

            print("jVerein wurde beendet.")
            print("")
            print("Du hast folgende Optionen:")
            print("")
            print("   (s) Erneut starten")
            print("   (f) Fertig")

            response = self._user_input(["s", "f"])
            if response == "s":
                master_password = self._ask_for_master_password()
            elif response == "f":
                running = False

        print("jVerein wird für den Upload vorbereitet")
        self._jverein_manager.teardown()

    def _manage_locked_by_me_and_clean(self):
        if self._gitlocker.is_locked_by_me():
            print("    Du hast noch den exklusiven Zugriff, es gibt aber")
            print("    keine lokalen Änderungen.")
            print("")
            print("    Du hast folgende Optionen:")
            print("")
            print("    (u) Unlock")
            print("          Exklusiven Zugriff freigeben")
            print("    (s) Starten")
            print("          jVerein starten, um Änderungen vorzunehmen")
            print("    (q) Abbruch")

            response = self._user_input(["u", "s", "q"])
            if response == "u":
                self._unlock()
            if response == "s":
                self._run_jverein()
                self._ask_and_upload()
            else:
                return

    def _manage_locked_by_others_and_clean(self):
        print("    Das Arbeitsverzeichnis ist derzeit gesperrt von:")
        print("")
        print(f"    {self._gitlocker.get_lock_info()}")
        print("")
        print("    Bitte versuche es später noch einmal.")
        print("")

    def _manage_unlocked_and_clean(self):
        print("    Arbeitsverzeichnis sauber, kein exklusiver Zugriff angefordert.")
        print("")
        print("    Du hast folgende Optionen:")
        print("")
        print("    (l) Lock")
        print("          Änderungen herunterladen, exklusiven Zugriff anfordern")
        print("          und jVerein starten")
        print("    (q) Abbruch")
        print("")

        response = self._user_input(["l", "q"])
        if response == "l":
            self._pull_and_lock()
            self._run_jverein()
            self._ask_and_upload()
        return

    def _manage_locked_by_me_and_not_clean(self):
        print("    Du hast noch den exklusiven Zugriff und es gibt ")
        print("    lokale Änderungen, die hochgeladen werden wollen.")
        print("")
        print("    Du hast folgende Optionen:")
        print("")
        print("   (p) Push")
        print("         Änderungen hochladen und exklusiven Zugriff freigeben")
        print("   (s) Starten")
        print("          jVerein starten, um weitere Änderungen vorzunehmen")
        print("   (verwerfen)")
        print("         Lokale Änderungen verwerfen und exklusvien Zugriff freigeben")
        print("   (q) Abbruch")
        print("")

        response = self._user_input(["p", "s", "verwerfen", "q"])
        if response == "p":
            self._upload_changes()
            self._unlock()
            print("Erfolg: Änderungen hochgeladen, exklusiver Zugriff freigegeben")
        elif response == "s":
            self._run_jverein()
            self._ask_and_upload()
        elif response == "verwerfen":
            self._discard_changes()
            self._unlock()
        return

    def _manage_locked_by_others_and_not_clean(self):
        print("ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG!")
        print("")
        print("    Es gibt Änderungen in dem Arbeitsverzeichnis, obwohl")
        print("    jemand anderes den exklusiven Zugriff hat!")
        print("    Wie auch immer dieser Zustand zustandegekommen ist,")
        print("    versuche bitte, ihn in Zukunft zu vermeiden!")
        print("")
        print("    Du hast folgende Optionen:")
        print("")
        print("    (verwerfen)")
        print("          Änderungen verwerfen")
        print("    (q) Abbruch")
        print("          (und Problem manuell beheben)")
        print("")

        response = self._user_input(["verwerfen", "q"])
        if response == "verwerfen":
            self._discard_changes()
        return

    def _manage_unlocked_and_not_clean(self):
        print("ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG!")
        print("")
        print("    Es gibt Änderungen in dem Arbeitsverzeichnis, obwohl Du")
        print("    nicht den exklusiven Zugriff auf das Verzeichnis hast!")
        print("    Wie auch immer dieser Zustand zustandegekommen ist,")
        print("    versuche bitte, ihn in Zukunft zu vermeiden!")
        print("")
        print("    Du hast folgende Optionen:")
        print("")
        print("    (p) Push")
        print("          Versuchen, die Änderungen hochzuladen.")
        print("          Das kann funktionieren, muss es aber nicht.")
        print("          Ggf. musst du danach das Git von Hand zurücksetzen.")
        print("    (verwerfen)")
        print("          Änderungen verwerfen")
        print("    (q) Abbruch")
        print("          (und Problem manuell beheben)")
        print("")

        response = self._user_input(["p", "verwerfen", "q"])
        if response == "p":
            self._upload_changes()
        elif response == "verwerfen":
            self._discard_changes()
        return


def run():
    default_working_dir = os.path.join(os.path.expanduser("~"), ".jverein-multiuser")
    parser = argparse.ArgumentParser(
        description="Multiuser-Unterstützung für jVerein",
        prog="jverein-multiuser"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("-d", "--working-dir",
                        dest="working_dir",
                        default=default_working_dir,
                        help=f"Arbeitsverzeichnis für Repository und Konfiguration (default: {default_working_dir})")
    parser.add_argument("-n", "--no-update", dest="check_for_updates", action="store_false",
                        help="Nicht nach Updates von jverein-multiuser suchen")
    parser.add_argument('-v', '--verbose', dest="verbose", action='count', default=0,
                        help="Log-Level; -v: INFO, -vv: DEBUG")
    args = parser.parse_args()

    if args.verbose == 0:
        log_level = logging.WARNING
    elif args.verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        level=log_level)

    try:
        app = App(working_dir=args.working_dir,
                  check_for_updates=args.check_for_updates)
        app.run()
    except CancelAppException:
        print("Abbruch.")
    except:
        traceback.print_exc(file=sys.stdout)

    input("Ende. Mit Enter bestätigen.")


if __name__ == '__main__':
    run()
