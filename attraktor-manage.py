#!/usr/bin/env python
# coding=utf-8

import config.common
from lib.gitlocker import GitLocker, GitError, IsLockedError
from lib.jvereinmanager import JvereinManager
import sys
import traceback

try:
    import config.user
except ImportError:
    config = None
    print "Lege bitte die Datei config/user.py an. " \
          "Du kannst die Datei config/user.default.py als Vorlage nehmen."
    exit(1)


class AttraktorManage(object):

    def __init__(self):
        self._gitlocker = GitLocker(config.user.paths.git,
                                    config.user.working_dir,
                                    config.common.remote_host,
                                    config.common.remote_path,
                                    config.user.name,
                                    config.user.email)

        self._jverein_manager = JvereinManager(
            config.user.working_dir, config.user.paths.jameica_properties)

    def run(self):
        print "Du arbeitest als"
        print "Name/E-Mail:  {} <{}>".format(config.user.name, config.user.email)
        print "Verzeichnis:  {}".format(config.user.working_dir)
        print ""

        # updaten, wenn Arbeitsverzeichnis sauber und wir nicht den Lock haben
        locked_by_me = self._gitlocker.is_locked_by_me()
        clean = self._gitlocker.is_clean()
        if clean and not locked_by_me:
            self._gitlocker.pull()

        locked_by_me = self._gitlocker.is_locked_by_me()
        locked = self._gitlocker.get_lock_status() is not None
        clean = self._gitlocker.is_clean()

        if locked_by_me and clean:
            self._manage_locked_by_me_and_clean()
        elif locked and clean:
            self._manage_locked_by_others_and_clean()
        elif not locked and clean:
            self._manage_unlocked_and_clean()
        elif locked_by_me and not clean:
            self._manage_locked_by_me_and_not_clean()
        elif locked and not clean:
            self._manage_locked_by_others_and_not_clean()
        elif not locked and not clean:
            self._manage_unlocked_and_not_clean()
        else:
            raise Exception("Programm-Fehler")

    def _user_input(self, options):
        response = ""
        while response not in options:
            response = raw_input("[{}] ".format("/".join(options))).lower()
        print ""
        return response

    def _pull_and_lock(self):
        print "Lade Änderungen herunter und fordere exklusiven Zugriff an."
        try:
            self._gitlocker.pull_and_lock()
        except IsLockedError as e:
            print e.message
        except GitError as e:
            print "FEHLER! Bitte Log prüfen."
            print e.message

    def _upload_changes(self):
        commit_message = None

        if self._gitlocker.need_to_commit():
            commit_message = ""
            while len(commit_message) <= 0:
                commit_message = raw_input("Was hast du getan? (kurze commit-Message): ")

        print "Lokale Änderungen werden hochgeladen"
        self._gitlocker.push(commit_message)

    def _ask_and_upload(self):
        print "    Möchtest Du jetzt die Änderungen hochladen?"
        response = self._user_input(["j", "n"])
        if response == "j":
            self._upload_changes()
            self._unlock()
            return True
        else:
            print "    Du  hast immer noch den exklusiven Zugriff!"
            print "    Bitte starte das Programm zeitnah neu, um ggf. weitere"
            print "    Änderungen vorzunehmen und den exklusiven Zugriff"
            print "    freizugeben."
            return False

    def _unlock(self):
        print "Exklusiver Zugriff wird freigegeben"
        self._gitlocker.unlock()

    def _discard_changes(self):
        print "Lokale Änderungen werden gelöscht"
        self._gitlocker.delete_local_changes()

    def _run_jverein(self):
        print "jVerein-Pfade werden für Dein System eingerichtet"
        self._jverein_manager.setup_jverein_paths()

        print "jVerein wird gestartet"
        self._jverein_manager.run_jverein(config.user.paths.jameica_cmd,
                                          config.user.paths.jameica_cwd)
        raw_input("jVerein wurde beendet. Bitte mit Enter bestätigen.")

        print "jVerein-Pfade werden wieder normalisiert"
        self._jverein_manager.teardown_jverein_paths()

        print "jVerein-Datenbank wird in Datei geschrieben"
        self._jverein_manager.dump_database(config.user.paths.java,
                                            config.common.h2_jar_name)

    def _manage_locked_by_me_and_clean(self):
        if self._gitlocker.is_locked_by_me():
            print "    Du hast noch den exklusiven Zugriff, es gibt aber"
            print "    keine lokalen Änderungen."
            print ""
            print "    Du hast folgende Optionen:"
            print ""
            print "    (u) Unlock"
            print "          Exklusiven Zugriff freigeben"
            print "    (s) Starten"
            print "          jVerein starten, um Änderungen vorzunehmen"
            print "    (q) Abbruch"

            response = self._user_input(["u", "s", "q"])
            if response == "u":
                self._unlock()
            if response == "s":
                self._run_jverein()
            else:
                return

    def _manage_locked_by_others_and_clean(self):
        print "    Das Arbeitsverzeichnis ist derzeit gesperrt."
        print "    Bitte versuche es später noch einmal."
        print ""
        print "    {}".format(self._gitlocker.get_lock_status())
        print ""

    def _manage_unlocked_and_clean(self):
        print "    Arbeitsverzeichnis sauber, kein exklusiver Zugriff angefordert."
        print ""
        print "    Du hast folgende Optionen:"
        print ""
        print "    (l) Lock"
        print "          Änderungen herunterladen, exklusiven Zugriff anfordern"
        print "          und jVerein starten"
        print "    (q) Abbruch"

        response = self._user_input(["l", "q"])
        if response == "l":
            self._pull_and_lock()
            self._run_jverein()
            self._ask_and_upload()
        return

    def _manage_locked_by_me_and_not_clean(self):
        print "    Du hast noch den exklusiven Zugriff und es gibt "
        print "    lokale Änderungen, die hochgeladen werden wollen."
        print ""
        print "    Du hast folgende Optionen:"
        print ""
        print "   (p) Push"
        print "         Änderungen hochladen und exklusiven Zugriff freigeben"
        print "   (s) Starten"
        print "          jVerein starten, um weitere Änderungen vorzunehmen"
        print "   (verwerfen)"
        print "         Lokale Änderungen verwerfen und exklusvien Zugriff freigeben"
        print "   (q) Abbruch"

        response = self._user_input(["p", "s", "verwerfen", "q"])
        if response == "p":
            self._upload_changes()
            self._unlock()
            print "Erfolg: Änderungen hochgeladen, exklusiver Zugriff freigegeben"
        elif response == "s":
            self._run_jverein()
        elif response == "verwerfen":
            self._discard_changes()
            self._unlock()
        return

    def _manage_locked_by_others_and_not_clean(self):
        print "ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG!"
        print ""
        print "    Es gibt Änderungen in dem Arbeitsverzeichnis, obwohl"
        print "    jemand anderes den exklusiven Zugriff hat!"
        print "    Wie auch immer dieser Zustand zustandegekommen ist,"
        print "    versuche bitte, ihn in Zukunft zu vermeiden!"
        print ""
        print "    Du hast folgende Optionen:"
        print ""
        print "    (verwerfen)"
        print "          Änderungen verwerfen."
        print "    (q) Abbruch"

        response = self._user_input(["verwerfen", "q"])
        if response == "verwerfen":
            self._discard_changes()
        return

    def _manage_unlocked_and_not_clean(self):
        print "ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG! ACHTUNG!"
        print ""
        print "    Es gibt Änderungen in dem Arbeitsverzeichnis, obwohl Du"
        print "    nicht den exklusiven Zugriff auf das Verzeichnis hast!"
        print "    Wie auch immer dieser Zustand zustandegekommen ist,"
        print "    versuche bitte, ihn in Zukunft zu vermeiden!"
        print ""
        print "    Du hast folgende Optionen:"
        print ""
        print "    (p) Push"
        print "          Versuchen, die Änderungen hochzuladen."
        print "          Das kann funktionieren, muss es aber nicht."
        print "          Ggf. musst du danach das Git von Hand zurücksetzen."
        print "    (verwerfen)"
        print "          Änderungen verwerfen."
        print "    (q) Abbruch"

        response = self._user_input(["p", "verwerfen", "q"])
        if response == "p":
            self._upload_changes()
        elif response == "verwerfen":
            self._discard_changes()
        return

if __name__ == '__main__':
    try:
        am = AttraktorManage()
        am.run()
    except:
        traceback.print_exc(file=sys.stdout)

    raw_input("Ende. Mit Enter bestätigen.")
