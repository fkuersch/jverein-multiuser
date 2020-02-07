import subprocess
import os.path
import logging
from datetime import datetime


class IsLockedError(Exception):
    """ Is already locked """


class GitError(Exception):
    """ Git problem """


class GitLocker:

    def __init__(self, git_path, working_dir, remote_host, remote_dir, name, email):
        self._logger = logging.getLogger(__name__)

        self._git_path = git_path
        self._working_dir = working_dir
        self._remote_host = remote_host
        self._remote_dir = remote_dir
        self._name = name
        self._email = email
        self._is_set_up = False

        self._sanitized_name = self._sanitize_name()

    def _sanitize_name(self):
        allowed_chars = "abcdefghijklmnopqrstuvwxyz-"
        allowed_chars += allowed_chars.upper()

        sanitized_name = self._name.strip().replace(" ", "-")
        sanitized_name = sanitized_name.replace("ß", "ss")
        sanitized_name = sanitized_name.replace("ä", "ae")
        sanitized_name = sanitized_name.replace("ö", "oe")
        sanitized_name = sanitized_name.replace("ü", "ue")

        sanitized_name = "".join([c for c in sanitized_name if c in allowed_chars])
        return sanitized_name

    def _create_lock_name(self):
        sanitized_datetime = datetime.now().isoformat("_").split(".")[0].replace(":", "-")
        return "lock_" + self._sanitized_name + "_" + sanitized_datetime

    def _execute_git(self, args, check_setup=True):

        # make sure the name and email are set
        if check_setup and not self._is_set_up:
            self._setup()

        git_env = os.environ.copy()
        git_env["LANGUAGE"] = "en_US.UTF-8"

        args = [self._git_path,
                "-C", self._working_dir,
                ] + args
        self._logger.info(f"executing: '{' '.join(args)}'")
        gitproc = subprocess.Popen(args,
                                   shell=False, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   env=git_env)
        output, err = gitproc.communicate()

        if gitproc.returncode != 0:
            self._logger.error(f"RETURNCODE: {gitproc.returncode}")
            self._logger.error(f"STDOUT: {output}")
            self._logger.error(f"STDERR: {err}")

        return gitproc.returncode, output.decode(), err.decode()

    def _setup(self):
        """
        Set the Git username and email
        :raises GitError
        """

        self._ensure_git_available()

        ret = self._execute_git(
            ["config", "--local", "user.name", self._name],
            check_setup=False)[0]
        if ret != 0:
            raise GitError("Konnte den Git-Usernamen nicht setzen!")

        ret = self._execute_git(
            ["config", "--local", "user.email", self._email],
            check_setup=False)[0]
        if ret != 0:
            raise GitError("Konnte die Git-E-Mail-Adresse nicht setzen!")

        self._is_set_up = True

    def get_lock_status(self):
        ret, output = self._execute_git(["tag", "-l", "lock*"])[:2]
        if ret != 0:
            raise GitError("Konnte nicht Tag prüfen. Bitte Log prüfen.")

        num_locks = output.count("\n")
        if num_locks > 1:
            raise GitError(
                "Achtung! Mehr als ein Lock! Das darf nicht passieren!")
        elif num_locks == 1:
            lock_status = output.strip().split("_")[1:]  # delete lock_
            lock_status[0] = lock_status[0].replace("-", " ")  # name
            lock_status[2] = lock_status[2].replace("-", ":")  # time
            return " ".join(lock_status)

        return None

    def is_locked_by_me(self):
        ret, output = self._execute_git(["tag", "-l", "lock*"])[:2]
        if ret != 0:
            raise GitError("Konnte nicht Tag prüfen. Bitte Log prüfen.")

        num_locks = output.count("\n")
        if num_locks > 1:
            raise GitError(
                "Achtung! Mehr als ein Lock! Das darf nicht passieren!")
        elif num_locks == 1:
            return output.strip().startswith("lock_" + self._sanitized_name)

        return False

    def is_clean(self):

        self._ensure_git_available()

        ret, out, err = self._execute_git(["status"])
        if ret != 0:
            raise GitError("Konnte den Git-Status nicht abrufen.")

        for line in out.split("\n"):
            line = line.strip()
            if len(line) > 0:
                self._logger.debug(line)
                if "branch is ahead of" in line:
                    return False
                if "nothing to commit" in line:
                    return True
        return False

    def need_to_commit(self):

        self._ensure_git_available()

        ret, out, err = self._execute_git(["status"])
        if ret != 0:
            raise GitError("Konnte den Git-Status nicht abrufen.")

        for line in out.split("\n"):
            line = line.strip()
            if len(line) > 0:
                self._logger.debug(line)
                if "nothing to commit" in line:
                    return False
        return True

    def _ensure_git_available(self):
        # clone or pull from remote
        if not os.path.exists(os.path.join(self._working_dir, ".git")):
            ret = self._execute_git(
                ["clone",
                 ":".join([self._remote_host, self._remote_dir]),
                 "."],
                check_setup=False)[0]
            if ret != 0:
                raise GitError("Konnte nicht clonen. Bitte Log prüfen.")

    def pull(self):
        self._ensure_git_available()

        ret = self._execute_git(["pull"])[0]
        if ret != 0:
            raise GitError("Konnte nicht updaten. Bitte Log prüfen.")

        ret, out, err = self._execute_git(
            ["pull",
             "--prune", "origin", "+refs/tags/*:refs/tags/*"])
        if ret == 1 and "no candidates for merging among the refs" in err:
            ret = 0

        if ret != 0:
            raise GitError("Konnte nicht updaten. Bitte Log prüfen.")

    def pull_and_lock(self):
        self.pull()

        # check lock after updating
        lock_status = self.get_lock_status()
        is_locked_by_me = self.is_locked_by_me()
        if lock_status is not None and not is_locked_by_me:
            raise IsLockedError(
                f"Ist bereits gelockt: von {lock_status}")

        if lock_status is not None and is_locked_by_me:
            raise IsLockedError(
                f"Ist bereits von Dir gelockt: {lock_status}")

        # no Lock acquired, create and push tag
        lock_name = self._create_lock_name()
        ret = self._execute_git(["tag", lock_name])[0]
        if ret != 0:
            raise GitError("Konnte kein Tag anlegen! Bitte Log prüfen")

        ret = self._execute_git(["push", "origin", lock_name])[0]
        if ret != 0:
            raise GitError("Konnte Tag nicht pushen! Bitte Log prüfen")

    def _commit(self, commit_message):
        ret = self._execute_git(["add", "--all"])[0]
        if ret != 0:
            raise GitError("Konnte die Änderungen nicht stagen.")

        ret = self._execute_git(["commit", "-m", commit_message])[0]
        if ret != 0:
            raise GitError("Konnte die Änderungen nicht commiten.")

    def push(self, commit_message=None):
        if commit_message is not None:
            self._commit(commit_message)

        if self.need_to_commit():
            raise GitError("Working directory ist nicht clean!")

        ret = self._execute_git(["push", "origin", "master"])[0]
        if ret != 0:
            raise GitError("Konnte nicht pushen!")

    def unlock(self):
        ret, output = self._execute_git(["tag", "-l", "lock*"])[:2]
        if ret != 0:
            raise GitError("Konnte nicht Tag prüfen. Bitte Log prüfen.")

        num_locks = output.count("\n")
        if num_locks > 1:
            self._logger.error("> 1 lock acquired")
            raise GitError(
                "Achtung! Mehr als ein Lock! Das darf nicht passieren!")
        elif num_locks == 0:
            self._logger.error("0 locks acquired")
            raise GitError(
                "Achtung! Kein Lock! Das darf nicht passieren!")

        lock_name = output.split("\n")[0].strip()

        # delete lock remotely
        ret = self._execute_git(["push", "--delete", "origin", lock_name])[0]
        if ret != 0:
            raise GitError("Konnte entfernten Tag nicht löschen! Bitte Log prüfen")

        # delete lock locally (if deleting remotely succeeded)
        ret = self._execute_git(["tag", "-d", lock_name])[0]
        if ret != 0:
            raise GitError("Konnte lokalen Tag nicht löschen! Bitte Log prüfen")

    def delete_local_changes(self):
        ret = self._execute_git(["reset", "--hard", "origin/master"])[0]
        if ret != 0:
            raise GitError("Konnte nicht Git auf den letzten Commit resetten.")

        ret = self._execute_git(["clean", "-d", "-f"])[0]
        if ret != 0:
            raise GitError("Konnte nicht Git cleanen.")
