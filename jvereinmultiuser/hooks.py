import os
import sys
import pkgutil
import subprocess
from typing import Type


class GenericHook:
    name = None
    linux_script = None
    macos_script = None
    win_script = None


class PostUploadHook(GenericHook):
    name = "post_upload"
    linux_script = "linux_post_upload.sh"
    macos_script = "macos_post_upload.sh"
    win_script = "win_post_upload.bat"


_ALL_HOOKS = [PostUploadHook]


def _create_example_file_name(script_name):
    parts = script_name.split(".")
    parts.insert(-1, "example")
    return ".".join(parts)


def create_example_files_if_necessary(local_repo_dir):
    hooks_dir = os.path.join(local_repo_dir, "hooks")
    if not os.path.exists(hooks_dir):
        os.makedirs(hooks_dir)
    for hook in _ALL_HOOKS:
        for script_name in [hook.linux_script, hook.macos_script, hook.win_script]:
            example_script_name = _create_example_file_name(script_name)
            dst_script_path = os.path.join(hooks_dir, example_script_name)
            if not os.path.exists(dst_script_path):
                resource_script_path = os.path.join("resources", "hooks", example_script_name)
                script_data = pkgutil.get_data("jvereinmultiuser", resource_script_path)
                with open(dst_script_path, "wb") as f:
                    f.write(script_data)


def run_hook(hook: Type[GenericHook], local_repo_dir: str):
    if sys.platform.startswith("win32") or sys.platform.startswith("cygwin"):  # Windows
        script_name = hook.win_script
    elif sys.platform.startswith("darwin"):  # macOS
        script_name = hook.macos_script
    else:  # Linux
        script_name = hook.linux_script
    script_path = os.path.join(local_repo_dir, "hooks", script_name)

    if os.path.isfile(script_path):
        print(f"Führe Hook aus: {hook.name}")
        subprocess.run(script_path)
