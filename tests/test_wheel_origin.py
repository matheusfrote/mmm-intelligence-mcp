"""Exercise real directory aliases, like macOS /var -> /private/var."""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest


def verifier():
    source = Path(__file__).resolve().parents[1] / "examples" / "verify_wheel.py"
    spec = importlib.util.spec_from_file_location("verify_wheel", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_import_origin


def alias_directory(alias, target):
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)], check=True, capture_output=True
        )
    else:
        alias.symlink_to(target, target_is_directory=True)


def test_runtime_alias_accepts_its_real_installed_package(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    installed = runtime / "module.py"
    installed.write_text("# installed wheel")
    alias = tmp_path / "runtime-alias"
    alias_directory(alias, runtime)
    verify = verifier()
    verify(str(installed.resolve()), alias)
    verify(str(alias / "module.py"), runtime)


def test_external_import_and_link_escape_remain_rejected(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    outside = tmp_path / "runtime-other"
    outside.mkdir()
    module = outside / "module.py"
    module.write_text("# unrelated source")
    alias_directory(runtime / "external", outside)
    verify = verifier()
    for path in (module, runtime / "external" / "module.py"):
        with pytest.raises(RuntimeError, match="not imported from the installed wheel"):
            verify(str(path), runtime)
