#!/usr/bin/env python
# coding=utf-8

import os
import subprocess
import datetime
import re

import config.common
try:
    import config.user
except ImportError:
    config = None
    print "Lege bitte die Datei config/user.py an. " \
          "Du kannst die Datei config/user.default.py als Vorlage nehmen."
    exit(1)

os.chdir(config.user.working_dir)

ova_name = "Attraktor_Vereinsverwaltung.ova"
vm_name = "Attraktor Vereinsverwaltung"

remote_lockfile_path = \
    "{}/lockfile".format(config.common.remote_path).replace("//", "/")
remote_ova_path = \
    "{}/{}".format(config.common.remote_path, ova_name).replace("//", "/")


def get_uuid_by_name(name):
    ps = subprocess.Popen([config.user.paths.vboxmanage, "list", "vms"],
                          shell=False, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    output = ps.communicate()[0]

    valid = re.compile(r"\"(.*)\" {(.*)}")

    for l in output.split("\n"):
        l = l.strip()
        if len(l) > 0:
            match = valid.match(l)
            if match.groups()[0] == name:
                return match.groups()[1]

    return None


def is_locked(local_file):
    with open(local_file) as f:
        lock_user = f.readline().strip()
        lock_email = f.readline().strip()
        lock_datetime = f.readline().strip()

    if not lock_user:
        print "Lock-Status: Entsperrt. Du kannst loslegen!"
        return False
    else:
        print "Lock-Status: Gesperrt"
        print "   von {} <{}>".format(lock_user, lock_email)
        print "   am {}".format(lock_datetime)
        return True


def check_lock_status():
    exit_status = subprocess.call([config.user.paths.rsync,
                                   "-ptgo",
                                   "{}:{}".format(config.common.remote_host,
                                                  remote_lockfile_path),
                                   "lockfile"])

    if exit_status != 0:
        print "FEHLER: Herunterladen des Lockfiles felhgeschlagen."
        return True

    return is_locked("lockfile")


print "Name:         {} <{}>".format(config.user.name, config.user.email)
print "Verzeichnis:  {}".format(config.user.working_dir)
print ""


def lock():
    # write local file
    print "Generiere Lockfile..."
    with open("lockfile", "w") as f:
        now = datetime.datetime.now()
        f.write("\n".join([
            config.user.name,
            config.user.email,
            "{}.{}.{} {}:{}:{}".format(now.day, now.month, now.year,
                                       now.hour, now.minute, now.second)
        ]) + "\n")

    # upload lock file
    print "Lade Lockfile hoch..."
    exit_status = subprocess.call([config.user.paths.rsync,
                                   "-ptgo",
                                   "lockfile",
                                   "{}:{}".format(config.common.remote_host,
                                                  remote_lockfile_path)
                                   ])

    if exit_status != 0:
        print "FEHLER: Hochladen des Lockfiles felhgeschlagen."
        return False

    return True


def unlock():
    # write local file
    print "Generiere Lockfile..."
    with open("lockfile", "w") as f:
        f.write("")

    # upload lock file
    print "Lade Lockfile hoch..."
    exit_status = subprocess.call([config.user.paths.rsync,
                                   "-ptgo",
                                   "lockfile",
                                   "{}:{}".format(config.common.remote_host,
                                                  remote_lockfile_path)
                                   ])

    if exit_status != 0:
        print "FEHLER: Hochladen des Lockfiles felhgeschlagen."
        return False

    return True


def pull():
    print "Lade VM herunter..."
    exit_status = subprocess.call([config.user.paths.rsync,
                                   "-v", "--progress", "-ptgo",
                                   "{}:{}".format(config.common.remote_host,
                                                  remote_ova_path),
                                   ova_name])

    if exit_status != 0:
        print "FEHLER: Herunterladen der VM felhgeschlagen."
        return False

    return True


def start():
    print "VM wird gestartet..."

    # prüfen, ob schon eine VM mit dem Namen vorhanden
    if get_uuid_by_name(vm_name) is not None:
        print "FEHLER: Es existiert bereits eine VM mit dem Namen '{}'!".format(vm_name)
        print "        Bitte löschen oder umbenennen."
        exit(1)

    # importieren
    print "Importiere VM..."
    exit_status = subprocess.call([config.user.paths.vboxmanage,
                                   "import", ova_name, "--vsys", "0",
                                   "--vmname", vm_name
                                   ])
    if exit_status != 0:
        print "FEHLER: Importieren der VM felhgeschlagen."
        exit(1)

    # starten
    print "Starte VM..."
    uuid = get_uuid_by_name(vm_name)
    exit_status = subprocess.call([config.user.paths.vboxmanage,
                                   "startvm", uuid
                                   ])
    if exit_status != 0:
        print "FEHLER: Starten der VM felhgeschlagen."
        exit(1)


def lock_pull_and_start():
    if check_lock_status():
        print "Fehler: VM ist schon gesperrt. Kann nicht 2"
        return

    lock() or exit(1)
    pull() or exit(1)
    start()


def push_and_unlock():
    # export
    print "Exportiere VM..."
    uuid = get_uuid_by_name(vm_name)
    if uuid is None:
        print "Fehler: Die VM mit dem Namen '{}' existiert nicht!".format(vm_name)
    os.unlink(ova_name) # remove previous ova
    exit_status = subprocess.call([config.user.paths.vboxmanage,
                                   "export", uuid, "--output", ova_name
                                   ])
    if exit_status != 0:
        print "FEHLER: Exportieren der VM felhgeschlagen."
        exit(1)

    # push
    print "Lade VM hoch..."
    exit_status = subprocess.call([config.user.paths.rsync,
                                   "-v", "--progress", "-ptgo",
                                   ova_name,
                                   "{}:{}".format(config.common.remote_host,
                                                  remote_ova_path),
                                   ])
    if exit_status != 0:
        print "FEHLER: Hochladen der VM felhgeschlagen."
        exit(1)

    # unlock
    print "Gebe VM wieder frei..."
    unlock() or exit(1)


def menu():
    """
    :return: start menu again
    :rtype: bool
    """
    print "Bitte wähle eine der folgenden Optionen:"
    print "1) Lock-Status prüfen"
    print "2) VM sperren, herunterladen und starten"
    print "3) VM hochladen und freigeben"
    print "q) Abbruch."
    print ""

    option = raw_input("[1/2/3/q] ")

    print ""

    if option == "1":
        return not check_lock_status()
    elif option == "2":
        lock_pull_and_start()
        return False
    elif option == "3":
        push_and_unlock()
        return False
    elif option == "q":
        exit(0)
        return False
    else:
        print "Fehler: Ungültige Eingabe"
        return True

while menu():
    print ""