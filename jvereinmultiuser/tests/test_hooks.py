import os
import logging
import unittest
import tempfile
import textwrap
from unittest import TestCase


import jvereinmultiuser.hooks as hooks

# TODO tests work on macOS only


class TestHooks(TestCase):
    def setUp(self) -> None:
        super().setUp()
        logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            level=logging.DEBUG)

    def test_create_example_files(self):
        with tempfile.TemporaryDirectory() as local_repo_dir:
            hooks.create_example_files_if_necessary(local_repo_dir)
            example_script_files = [
                "linux_post_upload.example.sh",
                "macos_post_upload.example.sh",
                "win_post_upload.example.bat",
            ]
            resources_hook_dir = os.path.join(os.path.dirname(__file__), "..", "resources", "hooks")
            number_of_files_in_resources_hook_dir = len(os.listdir(resources_hook_dir))
            self.assertEqual(len(example_script_files), number_of_files_in_resources_hook_dir)

            hooks_dir = os.path.join(local_repo_dir, "hooks")
            number_of_files_in_hook_dir = len(os.listdir(hooks_dir))
            self.assertEqual(len(example_script_files), number_of_files_in_hook_dir)
            self.assertEqual(number_of_files_in_hook_dir, len(hooks._ALL_HOOKS) * 3)

            for script_name in example_script_files:
                script_path = os.path.join(hooks_dir, script_name)
                self.assertTrue(os.path.exists(script_path))

    def test_post_upload_hook(self):
        with tempfile.TemporaryDirectory() as local_repo_dir:
            hooks_dir = os.path.join(local_repo_dir, "hooks")
            script_path = os.path.join(hooks_dir, hooks.PostUploadHook.macos_script)
            test_file = os.path.join(local_repo_dir, "test_file")
            os.makedirs(hooks_dir)
            with open(script_path, "w") as f:
                f.write(textwrap.dedent(f"""
                    #!/bin/bash
                    echo "creating test file: {test_file}"
                    echo "test" > {test_file}
                    """.lstrip()))
            os.chmod(script_path, 0o764)
            hooks.run_hook(hooks.PostUploadHook, local_repo_dir)
            self.assertTrue(os.path.exists(test_file))

    def test_post_upload_hook_not_executable(self):
        with tempfile.TemporaryDirectory() as local_repo_dir:
            hooks_dir = os.path.join(local_repo_dir, "hooks")
            script_path = os.path.join(hooks_dir, hooks.PostUploadHook.macos_script)
            os.makedirs(hooks_dir)
            with open(script_path, "w") as f:
                f.write(textwrap.dedent(f"""
                    #!/bin/bash
                    echo "this should never be displayed"
                    """.lstrip()))
            os.chmod(script_path, 0o664)
            self.assertRaisesRegex(hooks.HookExecutionError, "nicht ausführbar", hooks.run_hook, hooks.PostUploadHook, local_repo_dir)

    def test_post_upload_hook_error(self):
        with tempfile.TemporaryDirectory() as local_repo_dir:
            hooks_dir = os.path.join(local_repo_dir, "hooks")
            script_path = os.path.join(hooks_dir, hooks.PostUploadHook.macos_script)
            os.makedirs(hooks_dir)
            with open(script_path, "w") as f:
                f.write(textwrap.dedent(f"""
                    #!/bin/bash
                    exit 42
                    """.lstrip()))
            os.chmod(script_path, 0o764)
            self.assertRaisesRegex(hooks.HookExecutionError, "returncode 42", hooks.run_hook, hooks.PostUploadHook, local_repo_dir)


if __name__ == '__main__':
    unittest.main()
