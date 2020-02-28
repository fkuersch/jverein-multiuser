import os
import errno
import logging
import subprocess
from datetime import datetime
from typing import Optional, Tuple, List, Any


class IsLockedError(Exception):
    """ Is already locked """


class GitError(Exception):
    """ Git problem """


class GitLocker:
    """
    This class implements an alternating multi-user access to a Git repository.

    One GitLocker instance locks the repository by creating a tag on the remote repository,
    other GitLocker instances will recognize the tag and raise a GitError when trying to lock the repo.

    There are possible race conditions when two GitLocker instances create a lock tag at the same time,
    but that's acceptable for our purpose.
    """

    def __init__(self,
                 git_cmd: str,
                 local_repo: str,
                 remote_repo: str,
                 author_name: str,
                 author_email: str,
                 instance_name: str):
        """
        Args:
            git_cmd: Path to git executable, ie. '/usr/bin/git'
            local_repo: Path to the local repository, ie. '~/lockable_project'
            remote_repo: Remote repository, ie. 'example.org:~/lockable_project.git'
            author_name: The name that will be used for the commits, ie. 'John Doe'
            author_email: The email that will be used for the commits, ie. 'john@example.org'
            instance_name: The name of this GitLocker instance (ie. computer name), ie. 'Johns MacBook'
                For using multiple locks with the same author's name.
        Raises:
            NotADirectoryError
            ValueError
        """
        self._logger = logging.getLogger(__name__)

        self._git_cmd = git_cmd
        self._local_repo = os.path.expanduser(local_repo)
        self._remote_repo = remote_repo
        self._author_name = author_name
        self._author_email = author_email
        self._instance_name = self._sanitize(instance_name)

        if not os.path.isdir(self._local_repo):
            raise NotADirectoryError(errno.ENOENT, os.strerror(errno.ENOENT), self._local_repo)

        sanitized_author = self._sanitize(self._author_name)
        sanitized_instance = self._instance_name
        if not sanitized_author or not sanitized_instance:
            raise ValueError("invalid author or instance name")

        self._lock_name_prefix = f"lock_{sanitized_author}_{sanitized_instance}"

    @staticmethod
    def _sanitize(src_str: str) -> str:
        allowed_chars = "abcdefghijklmnopqrstuvwxyz-"
        allowed_chars += allowed_chars.upper()

        replacements = [
            (" ", "-"),
            ("ß", "ss"),
            ("ä", "ae"),
            ("ö", "oe"),
            ("ü", "ue"),
        ]

        sanitized_str = src_str.strip()
        for orig, repl in replacements:
            sanitized_str = sanitized_str.replace(orig, repl)

        sanitized_str = "".join([c for c in sanitized_str if c in allowed_chars])

        return sanitized_str

    def _execute_git(self, args: List[str], ignore_err: Optional[str] = None) -> Tuple[int, str, str]:
        git_env = os.environ.copy()
        # we need the output in english to be able to parse it properly
        git_env["LANGUAGE"] = "en_US.UTF-8"

        args = [self._git_cmd,
                "-C", self._local_repo,
                ] + args
        self._logger.info(f"executing: '{' '.join(args)}'")
        proc = subprocess.run(args, capture_output=True, env=git_env)
        stdout_str = proc.stdout.decode()
        stderr_str = proc.stderr.decode()

        ret = proc.returncode
        if ignore_err and ignore_err in stderr_str:
            ret = 0

        if ret != 0:
            self._logger.error(f"RETURNCODE: {proc.returncode}")
            self._logger.error(f"STDOUT: {stdout_str}")
            self._logger.error(f"STDERR: {stderr_str}")
        else:
            self._logger.info(f"RETURNCODE: {proc.returncode}")
            self._logger.info(f"STDOUT: {stdout_str}")
            self._logger.info(f"STDERR: {stderr_str}")

        return ret, stdout_str, stderr_str

    def _git_set_author(self):
        ret = self._execute_git(
            ["config", "--local", "user.name", self._author_name])[0]
        if ret != 0:
            raise GitError("Konnte den Git-Usernamen nicht setzen!")

        ret = self._execute_git(
            ["config", "--local", "user.email", self._author_email])[0]
        if ret != 0:
            raise GitError("Konnte die Git-E-Mail-Adresse nicht setzen!")

    def stage_and_commit(self, commit_message: str):
        self._git_set_author()
        subprocess.run([self._git_cmd, "-C", self._local_repo, "status"], check=True)

        ret = self._execute_git(["add", "--all"])[0]
        if ret != 0:
            raise GitError("Konnte die Änderungen nicht stagen.")

        ret = self._execute_git(["commit", "-m", commit_message])[0]
        if ret != 0:
            raise GitError("Konnte die Änderungen nicht commiten.")

    def is_local_repo_available(self) -> bool:
        return os.path.exists(os.path.join(self._local_repo, ".git"))

    def get_lock_info(self) -> Optional[str]:
        ret, output = self._execute_git(["tag", "-l", "lock*"])[:2]
        if ret != 0:
            raise GitError("Konnte nicht Tag prüfen. Bitte Log prüfen.")

        num_locks = output.count("\n")
        if num_locks > 1:
            raise GitError("Achtung! Mehr als ein Lock! Das darf nicht passieren!")
        elif num_locks == 1:
            lock_name_parts = output.strip().split("_")[1:]  # delete lock_
            lock_author = lock_name_parts[0].replace("-", " ")
            lock_instance = lock_name_parts[1].replace("-", " ")
            lock_date = lock_name_parts[2]
            lock_time = lock_name_parts[3].replace("-", ":")
            return f"{lock_author} ({lock_instance}) {lock_date} {lock_time}"

        return None

    def is_locked_by_me(self) -> bool:
        ret, output = self._execute_git(["tag", "-l", "lock*"])[:2]
        if ret != 0:
            raise GitError("Konnte nicht Tag prüfen. Bitte Log prüfen.")

        num_locks = output.count("\n")
        if num_locks > 1:
            raise GitError(
                "Achtung! Mehr als ein Lock! Das darf nicht passieren!")
        elif num_locks == 1:
            return output.strip().startswith(self._lock_name_prefix)

        return False

    def is_synced_with_remote_repo(self) -> bool:
        if not self.is_local_repo_available():
            return False

        ret, out, err = self._execute_git(["status"])
        if ret != 0:
            raise GitError("Konnte den Git-Status nicht abrufen.")

        for line in out.split("\n"):
            line = line.strip()
            if len(line) > 0:
                self._logger.debug(line)
                if "branch is ahead of" in line:
                    return False
                if "upstream is gone" in line:
                    return False
                if "nothing to commit" in line:
                    return True
        return False

    def need_to_commit(self) -> bool:
        if not self.is_local_repo_available():
            return False

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

    def do_initial_setup(self, initial_commit_data: Optional[Any], initial_commit_file_dst_path: str):
        """
        Args:
            initial_commit_data: Data of the file which will be committed if we cloned an empty repo
            initial_commit_file_dst_path: Relative path to which the data should be written to
        """
        ret, output, error = self._execute_git(["clone", self._remote_repo, "."])
        if ret != 0:
            raise GitError("Konnte nicht clonen. Bitte Log prüfen.")

        if "cloned an empty repository" in error:
            self._logger.warning("Cloned an empty repository. Creating an initial commit.")
            dst_path = os.path.join(self._local_repo, initial_commit_file_dst_path)
            with open(dst_path, "wb") as f:
                f.write(initial_commit_data)
            self.stage_and_commit("initial commit")

    def pull(self):
        ret = self._execute_git(["pull"])[0]
        if ret != 0:
            raise GitError("Konnte nicht updaten. Bitte Log prüfen.")

        ret, out, err = self._execute_git(
            ["pull", "--prune", "origin", "+refs/tags/*:refs/tags/*"],
            ignore_err="no candidates for merging among the refs"
        )
        # you provided a wildcard refspec which had no
        # matches on the remote end.
        # -> we can ignore this error safely

        if ret != 0:
            raise GitError("Konnte nicht updaten. Bitte Log prüfen.")

    def pull_and_lock(self):
        self.pull()

        # check lock after updating
        lock_name = self.get_lock_info()
        is_locked_by_me = self.is_locked_by_me()
        if lock_name is not None and not is_locked_by_me:
            raise IsLockedError(f"Ist bereits gelockt von: {lock_name}")

        if lock_name is not None and is_locked_by_me:
            raise IsLockedError(f"Ist bereits von Dir gelockt: {lock_name}")

        # no lock acquired, create and push tag
        sanitized_datetime = datetime.now().isoformat("_").split(".")[0].replace(":", "-")
        lock_name = self._lock_name_prefix + "_" + sanitized_datetime
        ret = self._execute_git(["tag", lock_name])[0]
        if ret != 0:
            raise GitError("Konnte kein Tag anlegen! Bitte Log prüfen")

        ret = self._execute_git(["push", "origin", lock_name])[0]
        if ret != 0:
            raise GitError("Konnte Tag nicht pushen! Bitte Log prüfen")

    def push(self):
        if self.is_synced_with_remote_repo():
            raise GitError("Keine Änderungen")

        if self.need_to_commit():
            raise GitError("Working directory ist nicht clean!")

        ret = self._execute_git(["push", "-u"])[0]  # set upstream. important for initial commit in an empty repo
        if ret != 0:
            raise GitError("Konnte nicht pushen!")

    def unlock(self):
        ret, output = self._execute_git(["tag", "-l", "lock*"])[:2]
        if ret != 0:
            raise GitError("Konnte nicht Tag prüfen. Bitte Log prüfen.")

        num_locks = output.count("\n")
        if num_locks > 1:
            self._logger.error("> 1 lock acquired")
            raise GitError("Achtung! Mehr als ein Lock! Das darf nicht passieren!")
        elif num_locks == 0:
            self._logger.error("0 locks acquired")
            raise GitError("Achtung! Kein Lock! Das darf nicht passieren!")

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
        ret = self._execute_git(["reset", "--hard", "@{upstream}"])[0]
        if ret != 0:
            raise GitError("Konnte nicht Git auf den letzten Commit resetten.")

        ret = self._execute_git(["clean", "-d", "-f"])[0]
        if ret != 0:
            raise GitError("Konnte nicht Git cleanen.")
