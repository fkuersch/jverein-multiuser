import os
import logging
import tempfile
import unittest
import subprocess
from unittest import TestCase

from jvereinmultiuser.gitlocker import GitLocker, GitError, IsLockedError

GIT_EXEC = "/usr/bin/git"
AUTHOR_NAME = "John Doe"
AUTHOR_EMAIL = "johndoe@example.org"
INSTANCE_NAME = "John Doe's Computer"
INSTANCE_NAME2 = f"Second Computer"


# noinspection DuplicatedCode
class TestGitLocker(TestCase):

    def setUp(self) -> None:
        super().setUp()
        logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            level=logging.DEBUG)

    def test_creation_without_local_repo_dir(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            not_existing_local_repo = os.path.join(local_repo, "doesntexist")
            self.assertRaises(
                NotADirectoryError,
                GitLocker,
                GIT_EXEC,
                not_existing_local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

    def test_creation_successful(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

    def test_author(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init", "--bare"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )
            initial_commit_file = os.path.join(os.path.dirname(__file__), "..", "resources", "jverein.gitignore")
            with open(initial_commit_file, "rb") as f:
                data = f.read()
            g.do_initial_setup(
                data,
                "jverein.gitignore"
            )

            # author needs to be set for the initial commit
            # get "<author> <email>" of last commit
            proc = subprocess.run([GIT_EXEC, "-C", local_repo, "log", "-1", "--pretty=format:'%an %ae'"],
                                  check=True,
                                  capture_output=True)
            self.assertTrue(f"{AUTHOR_NAME} {AUTHOR_EMAIL}" in proc.stdout.decode())

            # the changed author needs to be set for the next commit
            author2 = "Alice Doe"
            email2 = "alicedoe@example.org"
            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                author2,
                email2,
                INSTANCE_NAME
            )
            with open(os.path.join(local_repo, "example"), "w") as f:
                f.write("example content")
            g.stage_and_commit("second commit")

            proc = subprocess.run([GIT_EXEC, "-C", local_repo, "log", "-1", "--pretty=format:'%an %ae'"],
                                  check=True,
                                  capture_output=True)
            self.assertTrue(f"{author2} {email2}" in proc.stdout.decode())

    def test_is_local_repo_available_without_git(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )
            self.assertFalse(g.is_local_repo_available())

    def test_is_local_repo_available_with_git(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", local_repo, "init"], check=True)
            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )
            self.assertTrue(g.is_local_repo_available())

    def test_is_synced_with_remote_repo(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init", "--bare"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            # local repo is empty directory
            self.assertFalse(g.is_synced_with_remote_repo())

            # cloned repo is empty, so there's an initial commit to push
            initial_commit_file = os.path.join(os.path.dirname(__file__), "..", "resources", "jverein.gitignore")
            with open(initial_commit_file, "rb") as f:
                data = f.read()
            g.do_initial_setup(
                data,
                "jverein.gitignore"
            )
            self.assertFalse(g.is_synced_with_remote_repo())

            g.push()
            self.assertTrue(g.is_synced_with_remote_repo())

            # unstaged file is not synced
            with open(os.path.join(local_repo, "example"), "w") as f:
                f.write("example content")
            self.assertFalse(g.is_synced_with_remote_repo())

            # committed file is not synced
            g.stage_and_commit("add example file")
            self.assertFalse(g.is_synced_with_remote_repo())

            g.push()
            self.assertTrue(g.is_synced_with_remote_repo())

    def test_need_to_commit(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init", "--bare"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            # empty directory
            self.assertFalse(g.need_to_commit())

            # initial commit
            initial_commit_file = os.path.join(os.path.dirname(__file__), "..", "resources", "jverein.gitignore")
            with open(initial_commit_file, "rb") as f:
                data = f.read()
            g.do_initial_setup(
                data,
                "jverein.gitignore"
            )
            self.assertFalse(g.need_to_commit())

            # unstaged file
            with open(os.path.join(local_repo, "example"), "w") as f:
                f.write("example content")
            self.assertTrue(g.need_to_commit())

            g.stage_and_commit("second commit")
            self.assertFalse(g.need_to_commit())

            g.push()
            self.assertFalse(g.need_to_commit())

    def test_do_initial_setup_with_empty_remote(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init", "--bare"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            self.assertFalse(os.path.exists(os.path.join(local_repo, "jverein.gitignore")))

            initial_commit_file = os.path.join(os.path.dirname(__file__), "..", "resources", "jverein.gitignore")
            with open(initial_commit_file, "rb") as f:
                data = f.read()
            g.do_initial_setup(
                data,
                "jverein.gitignore"
            )

            self.assertTrue(os.path.exists(os.path.join(local_repo, "jverein.gitignore")))
            self.assertFalse(g.is_synced_with_remote_repo())

    def test_do_initial_setup_with_existing_remote(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init"], check=True)
            with open(os.path.join(remote_repo, "example"), "w") as f:
                f.write("example content")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", remote_repo, "commit", "-m", "initial commit"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            self.assertFalse(os.path.exists(os.path.join(local_repo, "jverein.gitignore")))
            self.assertFalse(os.path.exists(os.path.join(local_repo, "example")))

            initial_commit_file = os.path.join(os.path.dirname(__file__), "..", "resources", "jverein.gitignore")
            with open(initial_commit_file, "rb") as f:
                data = f.read()
            g.do_initial_setup(
                data,
                "jverein.gitignore"
            )

            # initial_commit_file (jverein.gitignore) must not be copied if the repository already existed
            self.assertFalse(os.path.exists(os.path.join(local_repo, "jverein.gitignore")))
            self.assertTrue(os.path.exists(os.path.join(local_repo, "example")))
            self.assertTrue(g.is_synced_with_remote_repo())

    def test_pull(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init"], check=True)
            with open(os.path.join(remote_repo, "example"), "w") as f:
                f.write("example content")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", remote_repo, "commit", "-m", "initial commit"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            self.assertRaises(GitError, g.pull)

            g.do_initial_setup("", "")

            # changed remote
            with open(os.path.join(remote_repo, "example2"), "w") as f:
                f.write("example content2")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", remote_repo, "commit", "-m", "second commit"], check=True)

            self.assertFalse(os.path.exists(os.path.join(local_repo, "example2")))
            g.pull()
            self.assertTrue(os.path.exists(os.path.join(local_repo, "example2")))

            # merge conflict
            with open(os.path.join(remote_repo, "example2"), "w") as f:
                f.write("example content3_remote")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", remote_repo, "commit", "-m", "third commit remote"], check=True)

            with open(os.path.join(local_repo, "example2"), "w") as f:
                f.write("example content3_local")
            subprocess.run([GIT_EXEC, "-C", local_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", local_repo, "commit", "-m", "third commit local"], check=True)

            self.assertRaises(GitError, g.pull)

    def test_push(self):
        with tempfile.TemporaryDirectory() as remote_repo, \
                tempfile.TemporaryDirectory() as local_repo, \
                tempfile.TemporaryDirectory() as tmp_repo:

            subprocess.run([GIT_EXEC, "-C", remote_repo, "init", "--bare"], check=True)

            subprocess.run([GIT_EXEC, "-C", tmp_repo, "clone", remote_repo, "."], check=True)
            with open(os.path.join(tmp_repo, "example"), "w") as f:
                f.write("example content")
            subprocess.run([GIT_EXEC, "-C", tmp_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", tmp_repo, "commit", "-m", "initial commit"], check=True)
            subprocess.run([GIT_EXEC, "-C", tmp_repo, "push", "-u"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            # empty directory
            self.assertRaises(GitError, g.push)

            g.do_initial_setup("", "")

            # no changes
            self.assertRaises(GitError, g.push)

            with open(os.path.join(local_repo, "example2"), "w") as f:
                f.write("example content")

            # changes not committed
            self.assertRaises(GitError, g.push)

            g.stage_and_commit("second commit")
            g.push()  # success

            # changed both remote and local file (need to fetch/merge first)
            subprocess.run([GIT_EXEC, "-C", tmp_repo, "pull"], check=True)
            with open(os.path.join(tmp_repo, "example2"), "w") as f:
                f.write("remote content")
            subprocess.run([GIT_EXEC, "-C", tmp_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", tmp_repo, "commit", "-m", "remote commit"], check=True)
            subprocess.run([GIT_EXEC, "-C", tmp_repo, "push"], check=True)
            with open(os.path.join(local_repo, "example2"), "w") as f:
                f.write("local content")
            g.stage_and_commit("local commit")
            self.assertRaises(GitError, g.push)

    def test_pull_and_lock_single_user(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init"], check=True)
            with open(os.path.join(remote_repo, "example"), "w") as f:
                f.write("example content")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", remote_repo, "commit", "-m", "initial commit"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            g.do_initial_setup("", "")

            self.assertIsNone(g.get_lock_info())
            self.assertFalse(g.is_locked_by_me())
            g.pull_and_lock()
            self.assertIsNotNone(g.get_lock_info())
            self.assertTrue(g.is_locked_by_me())
            g.unlock()
            self.assertIsNone(g.get_lock_info())
            self.assertFalse(g.is_locked_by_me())

    def test_pull_and_lock_two_instances(self):
        with tempfile.TemporaryDirectory() as remote_repo, \
                tempfile.TemporaryDirectory() as local_repo1, \
                tempfile.TemporaryDirectory() as local_repo2:
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init"], check=True)
            with open(os.path.join(remote_repo, "example"), "w") as f:
                f.write("example content")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", remote_repo, "commit", "-m", "initial commit"], check=True)

            g1 = GitLocker(
                GIT_EXEC,
                local_repo1,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            g2 = GitLocker(
                GIT_EXEC,
                local_repo2,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME2
            )

            g1.do_initial_setup("", "")
            g2.do_initial_setup("", "")

            self.assertIsNone(g1.get_lock_info())
            self.assertFalse(g1.is_locked_by_me())
            self.assertIsNone(g2.get_lock_info())
            self.assertFalse(g2.is_locked_by_me())

            g1.pull_and_lock()
            self.assertIsNotNone(g1.get_lock_info())
            self.assertTrue(g1.is_locked_by_me())
            self.assertIsNone(g2.get_lock_info())
            self.assertFalse(g2.is_locked_by_me())

            # g1 has the lock
            self.assertRaises(IsLockedError, g2.pull_and_lock)
            self.assertIsNotNone(g2.get_lock_info())
            print(g2.get_lock_info())
            self.assertTrue(AUTHOR_NAME in g2.get_lock_info())
            self.assertTrue("John Does Computer" in g2.get_lock_info())  # stripped the '
            self.assertFalse(INSTANCE_NAME2 in g2.get_lock_info())
            self.assertFalse(g2.is_locked_by_me())

            g1.unlock()
            self.assertIsNone(g1.get_lock_info())
            self.assertFalse(g1.is_locked_by_me())
            self.assertIsNotNone(g2.get_lock_info())  # g2 not updated yet
            self.assertFalse(g2.is_locked_by_me())

            g2.pull()
            self.assertIsNone(g2.get_lock_info())

            g2.pull_and_lock()
            self.assertIsNotNone(g2.get_lock_info())
            self.assertTrue(AUTHOR_NAME in g2.get_lock_info())
            self.assertFalse("John Does Computer" in g2.get_lock_info())
            self.assertTrue(INSTANCE_NAME2 in g2.get_lock_info())
            self.assertTrue(g2.is_locked_by_me())

    def test_delete_local_changes(self):
        with tempfile.TemporaryDirectory() as remote_repo, tempfile.TemporaryDirectory() as local_repo:
            example_file = os.path.join(remote_repo, "example")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "init"], check=True)
            with open(example_file, "w") as f:
                f.write("example content")
            subprocess.run([GIT_EXEC, "-C", remote_repo, "add", "--all"], check=True)
            subprocess.run([GIT_EXEC, "-C", remote_repo, "commit", "-m", "initial commit"], check=True)

            g = GitLocker(
                GIT_EXEC,
                local_repo,
                remote_repo,
                AUTHOR_NAME,
                AUTHOR_EMAIL,
                INSTANCE_NAME
            )

            g.do_initial_setup("", "")
            self.assertTrue(os.path.exists(example_file))

            # clear unstaged file
            example_file2 = os.path.join(local_repo, "example2")
            with open(example_file2, "w") as f:
                f.write("example content")
            self.assertTrue(os.path.exists(example_file2))
            g.delete_local_changes()
            self.assertFalse(os.path.exists(example_file2))

            # clear committed file
            example_file2 = os.path.join(local_repo, "example2")
            with open(example_file2, "w") as f:
                f.write("example content")
            self.assertTrue(os.path.exists(example_file2))
            g.stage_and_commit("second commit")
            self.assertTrue(os.path.exists(example_file2))
            self.assertFalse(g.is_synced_with_remote_repo())
            g.delete_local_changes()
            self.assertFalse(os.path.exists(example_file2))
            self.assertTrue(g.is_synced_with_remote_repo())


if __name__ == '__main__':
    unittest.main()
