#!/usr/bin/env python
# coding=utf-8

import os
import subprocess
import datetime
import re
from threading import Thread, Event
from lib.nbstreamreader import NonBlockingStreamReader as NBSR
import config.common
from time import sleep

try:
    import config.user
except ImportError:
    config = None
    print "Lege bitte die Datei config/user.py an. " \
          "Du kannst die Datei config/user.default.py als Vorlage nehmen."
    exit(1)


def msg_debug(msg):
    print msg


def git_status_is_clean():

    # git status is clean if there's no git
    if not os.path.exists(os.path.join(config.user.working_dir, ".git")):
        return True

    # git status is not clean if the lockfile exists
    if os.path.exists(os.path.join(config.user.working_dir, "lockfile")):
        return False

    # else check git status
    git_env = os.environ.copy()
    git_env["LANGUAGE"] = "en_US.UTF-8"
    ps = subprocess.Popen([config.user.paths.git,
                           "-C", config.user.working_dir,
                           "status"],
                          shell=False, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          env=git_env)
    output = ps.communicate()[0]

    for l in output.split("\n"):
        l = l.strip()
        if len(l) > 0:
            msg_debug(l)
            if "nothing to commit" in l:
                return True
    return False


def setup():
    print "Für die Versionshistorie ist es wichtig, dass die Systemzeit richtig eingestellt ist. Bitte prüfe, ob das bei dir der Fall ist und ob die folgenden Angaben stimmen:"
    print ""
    print "Name:         {} <{}>".format(config.user.name, config.user.email)
    print "Verzeichnis:  {}".format(config.user.working_dir)
    print ""

    response = raw_input(
        "Bitte bestätige, dass die o. g. Angaben richtig sind. [j/N] ")
    if response.lower() != "j":
        print "Bitte korrigiere die Konfigurationsdateien bzw. stelle die Systemzeit richtig ein."
        print "Abbruch."
        exit(1)

    setup_git()


def setup_git():
    if not os.path.exists(os.path.join(config.user.working_dir, ".git")):
        return

    # git config --local user.name
    confnameproc = subprocess.Popen([config.user.paths.git,
                                     "-C", config.user.working_dir,
                                     "config", "--local",
                                     "user.name", config.user.name],
                                    shell=False, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
    output = confnameproc.communicate()[0]

    if confnameproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    # git config --local user.email
    confemailproc = subprocess.Popen([config.user.paths.git,
                                      "-C", config.user.working_dir,
                                      "config", "--local",
                                      "user.email", config.user.email],
                                     shell=False, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
    output = confemailproc.communicate()[0]

    if confemailproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)


def delete_local_changes():
    print "Lokale Änderungen werden gelöscht."

    resetproc = subprocess.Popen([config.user.paths.git,
                                  "-C", config.user.working_dir,
                                  "reset", "--hard", "origin/master"],
                                 shell=False, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
    output = resetproc.communicate()[0]

    if resetproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    cleanproc = subprocess.Popen([config.user.paths.git,
                                  "-C", config.user.working_dir,
                                  "clean", "-d", "-f"],
                                 shell=False, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
    output = cleanproc.communicate()[0]

    if cleanproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    lockfile_path = os.path.join(config.user.working_dir, "lockfile")
    if os.path.exists(lockfile_path):
        push_and_unlock("unlock without change")


def is_locked(local_file):
    if os.path.exists(local_file):
        with open(local_file) as f:
            lock_user = f.readline().strip()
            lock_email = f.readline().strip()
            lock_datetime = f.readline().strip()

            print "Gesperrt"
            print "   von {} <{}>".format(lock_user, lock_email)
            print "   am {}".format(lock_datetime)
            print ""
            print "Bitte versuche es später erneut."
        return True
    else:
        return False


def pull_and_lock():
    print "Änderungen herunterladen und sperren"

    if not os.path.exists(os.path.join(config.user.working_dir, ".git")):
        print "git clone"
        # git clone
        cloneproc = subprocess.Popen(
            [config.user.paths.git, "clone", "{}:{}".format(
                config.common.remote_host, config.common.remote_path),
             config.user.working_dir],
            shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = cloneproc.communicate()
        print output
        print err

        if cloneproc.returncode != 0:
            print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
            exit(1)

        setup_git()  # name / email festlegen
    else:
        print "git pull"
        # git pull
        pullproc = subprocess.Popen([config.user.paths.git,
                                     "-C", config.user.working_dir,
                                     "pull", "origin"],
                                    shell=False, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
        output, err = pullproc.communicate()
        print output
        print err

        if pullproc.returncode != 0:
            print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
            exit(1)

    lockfile_path = os.path.join(config.user.working_dir, "lockfile")

    if is_locked(lockfile_path):  # gesperrt
        exit(0)

    # write local file
    with open(lockfile_path, "w") as f:
        now = datetime.datetime.now()
        f.write("\n".join([
            config.user.name,
            config.user.email,
            "{}.{}.{} {}:{}:{}".format(now.day, now.month, now.year,
                                       now.hour, now.minute, now.second)
        ]) + "\n")

    # git add lockfile
    addproc = subprocess.Popen([config.user.paths.git,
                                "-C", config.user.working_dir,
                                "add", "lockfile"],
                               shell=False, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    output = addproc.communicate()[0]

    if addproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    # git commit
    commitproc = subprocess.Popen([config.user.paths.git,
                                   "-C", config.user.working_dir,
                                   "commit",
                                   "-m", "locked by {} <{}>"
                                  .format(config.user.name,
                                          config.user.email)],
                                  shell=False, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
    output = commitproc.communicate()[0]

    if commitproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    # git push
    pushproc = subprocess.Popen([config.user.paths.git,
                                 "-C", config.user.working_dir,
                                 "push", "origin", "master"],
                                shell=False, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    output = pushproc.communicate()[0]

    # pushen fehlgeschlagen
    if pushproc.returncode != 0:
        print "Oh, da war in der Zwischenzeit einer schneller. Brechen wir lieber ab."
        # unseren commit rückgängig machen
        # git reset head ~1
        # letzten commit laden
        # git pull
        if not is_locked(lockfile_path):
            print "Seltsam, nicht mehr gesperrt, probier noch mal."
        exit(0)

    # wir haben jetzt den lock
    return True


mysqlproc = None


def dump_database():
    print "H2-Datenbank wird in Datei geschrieben (mysqldump)"
    # mysqldump für h2
    sqldump_path = os.path.join(config.user.working_dir, "jverein.sql")
    h2_path = os.path.join(
        config.user.working_dir, "jameica", "jverein", "h2db", "jverein")
    jar_path = os.path.join(config.user.working_dir, "h2",
                            config.common.h2_jar_name)
    dumpproc = subprocess.Popen([config.user.paths.java,
                                 "-cp", jar_path,
                                 "org.h2.tools.Script",
                                 "-url", "jdbc:h2:" + h2_path,
                                 "-user", "jverein",
                                 "-password", "jverein",
                                 "-script", sqldump_path],
                                shell=False, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    output = dumpproc.communicate()[0]

    if dumpproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)


def setup_jverein_paths():
    print "Die Pfade in jVerein werden für Dein System eingerichtet"
    file_path = os.path.join(config.user.working_dir, "jameica", "cfg", "de.willuhn.jameica.services.ScriptingService.properties")
    with open(file_path, "r") as f:
        content = f.read()

    content = content.replace("JAMEICA_DIR", os.path.join(config.user.working_dir, "jameica"))
    if "\\" in os.path.join("a", "b"):  # windows-Pfade sind escaped
        content = content.replace("\\", "\\\\")
        content = content.replace("/", "\\\\")

    with open(file_path, "w") as f:
        f.write(content)

    # backup original ~/.jameica.properties file
    if os.path.exists(config.user.paths.jameica_properties):
        # delete existing backup if there is one
        if os.path.exists(config.user.paths.jameica_properties + ".bak"):
            os.unlink(config.user.paths.jameica_properties + ".bak")
        os.rename(config.user.paths.jameica_properties,
                  config.user.paths.jameica_properties + ".bak")
    # create new file for starting jameica without asking for the path
    with open(config.user.paths.jameica_properties, "w") as f:
        jameica_path = os.path.join(config.user.working_dir, "jameica")
        if "\\" in os.path.join("a", "b"):  # windows-Pfade sind escaped
            jameica_path = jameica_path.replace("\\", "\\\\")
            jameica_path = jameica_path.replace(":", "\\:")  # der Doppelpunkt in dieser Datei auch
        f.write("dir={}\n".format(jameica_path))
        f.write("ask=false")


def teardown_jverein_paths():
    print "jVerein-Pfade normalisieren"

    # JAMEICA_DIR
    file_path = os.path.join(config.user.working_dir, "jameica", "cfg", "de.willuhn.jameica.services.ScriptingService.properties")
    with open(file_path, "r") as f:
        content = f.read()

    content = content.replace("\\\\", "\\")
    content = content.replace(os.path.join(config.user.working_dir, "jameica"), "JAMEICA_DIR")
    content = content.replace("\\", "/")

    with open(file_path, "w") as f:
        f.write(content)

    # lastdir ausleeren
    valid = re.compile(r"^(lastdir(\.sepa)?=).*$")  # r"\"(.*)\" {(.*)}")
    for filename in ["de.jost_net.JVerein.gui.control.AbrechnungSEPAControl.properties",
                     "de.jost_net.JVerein.gui.dialogs.ImportDialog.properties",
                     "de.jost_net.JVerein.gui.view.ImportView.properties"]:
        file_path = os.path.join(config.user.working_dir, "jameica", "cfg", filename)
        with open(file_path, "r") as f:
            newcontent = ""
            for l in f:
                newline = l
                if len(newline) > 0:
                    match = valid.match(newline)
                    if match is not None:
                        newline = match.groups()[0] + "\n"
                newcontent += newline

        with open(file_path, "w") as f:
            f.write(newcontent)

    # remove ~/jameica.properties
    if os.path.exists(config.user.paths.jameica_properties):
        os.unlink(config.user.paths.jameica_properties)
    # restore backup of original file
    if os.path.exists(config.user.paths.jameica_properties + ".bak"):
        os.rename(config.user.paths.jameica_properties + ".bak",
                  config.user.paths.jameica_properties)


def run_jverein():
    print "jVerein starten"
    p = subprocess.Popen(config.user.paths.jameica_cmd,
                         cwd=config.user.paths.jameica_cwd,
                         shell=False, stdin=None, stdout=None, stderr=None)
    p.wait()
    sleep(1)
    print "jVerein wurde beendet"


def push_and_unlock(commit_message=""):

    print "Änderungen hochladen und freigeben"

    while len(commit_message) <= 0:
        commit_message = raw_input("Was hast du getan? (commit-Message, nicht zu lang): ")

    # lockfile entfernen
    os.unlink(os.path.join(config.user.working_dir, "lockfile"))

    # git add --all
    addproc = subprocess.Popen([config.user.paths.git,
                                "-C", config.user.working_dir,
                                "add", "--all"],
                               shell=False, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    output = addproc.communicate()[0]

    if addproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    # git commit
    commitproc = subprocess.Popen([config.user.paths.git,
                                   "-C", config.user.working_dir,
                                   "commit",
                                   "-m", commit_message],
                                  shell=False, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
    output = commitproc.communicate()[0]

    if commitproc.returncode != 0:
        print "Autsch. Da ist was gewaltig schiefgelaufen. Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    # git push
    print "Änderungen hochladen"
    pushproc = subprocess.Popen([config.user.paths.git,
                                 "-C", config.user.working_dir,
                                 "push", "origin", "master"],
                                shell=False, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    output = pushproc.communicate()[0]

    # pushen fehlgeschlagen
    if pushproc.returncode != 0:
        print "Ach du Scheiße! Pushen ging schief! Starte dieses Script nicht neu, sondern reparier' das vorher von Hand!."
        exit(1)

    print "Änderungen erfolgreich hochgeladen."


def setup_and_start_jverein():
    setup_jverein_paths()
    run_jverein()
    raw_input("jVerein wurde beendet. Bitte Enter drücken.")
    teardown_jverein_paths()
    dump_database()

    response = ""
    while response not in ["j", "n"]:
        response = raw_input(
            "Möchtest du jetzt die Änderungen pushen? [j/n] ").lower()
        if response == "j":
            push_and_unlock()
        elif response == "n":
            print "Bitte starte das Programm zeitnah erneut. Denn solange du nicht pushst, bleiben die Dateien für die Anderen gesperrt."
            print "Abbruch."
            exit(0)
        else:
            print "Fehlerhafte Eingabe. Bitte erneut versuchen."
            print ""


setup()

if git_status_is_clean():
    print "Bitte wähle eine der folgenden Optionen:"
    print "    (l)         Download der Änderungen und locken (exklusiven"
    print "                Zugriff anfordern). Danach MySQL einrichten und"
    print "                jVerein starten."
    print "    (q)         Abbruch."
    print ""

    response = ""
    while response not in ["l", "q"]:
        response = raw_input("[l/q] ").lower()
        print ""
        if response == "l":
            pull_and_lock()
            setup_and_start_jverein()
        elif response == "q":
            print "Abbruch."
            exit(0)
        else:
            print "Fehlerhafte Eingabe. Bitte erneut versuchen."
            print ""

else:
    print "Oha! Dein git ist nicht sauber! Du hast noch lokale Änderungen, die nicht gepusht wurden. Solange du nicht pushst, bleiben die Daten für die Anderen gesperrt."
    print ""
    print "Bitte wähle eine der folgenden Optionen:"
    print "    (p)         pushe die Änderungen"
    print "    (s)         starte jVerein, um weiter Änderungen vorzunehmen"
    print "    (verwerfen) lösche die lokalen Änderungen (zurücksetzen)"
    print "    (q)         Abbruch."
    print ""

    response = ""
    while response not in ["p", "s", "q", "verwerfen"]:
        response = raw_input("[p/s/verwerfen/q] ").lower()
        print ""

        if response == "p":
            push_and_unlock()
        elif response == "s":
            setup_and_start_jverein()
        elif response == "verwerfen":
            delete_local_changes()
        elif response == "q":
            print "Abbruch."
            exit(0)
        else:
            print "Fehlerhafte Eingabe. Bitte erneut versuchen."
            print ""
