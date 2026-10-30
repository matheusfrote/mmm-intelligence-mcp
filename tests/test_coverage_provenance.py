"""Acceptance rejects stale executed source and retains the complete denominator."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def gate_module():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "coverage_gate", root / "examples/coverage_gate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measured_cli(tmp_path):
    gate = gate_module()
    directory = tmp_path / "capture"
    directory.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--data-file",
            str(directory / ".coverage"),
            "-m",
            "mmm_intelligence.cli",
            "doctor",
        ],
        cwd=gate.ROOT,
        check=True,
        capture_output=True,
        timeout=30,
    )
    gate.record(directory, "actual-cli")
    return gate, directory / "manifest.json"


def test_gate_rejects_stale_executed_source(tmp_path):
    gate, manifest = measured_cli(tmp_path)
    record = json.loads(manifest.read_text())
    record["source_sha256"]["src/mmm_intelligence/config.py"] = "0" * 64
    manifest.write_text(json.dumps(record))
    output = tmp_path / "aggregate"
    with pytest.raises(ValueError, match="Executed source changed"):
        gate.check([manifest], output)
    assert not output.exists()


def test_unexecuted_snapshot_changes_cannot_remove_production_from_denominator(tmp_path):
    gate, manifest = measured_cli(tmp_path)
    record = json.loads(manifest.read_text())
    record["source_sha256"]["src/mmm_intelligence/integrations/worker.py"] = "0" * 64
    manifest.write_text(json.dumps(record))
    output = tmp_path / "aggregate"
    with pytest.raises(SystemExit, match="100%"):
        gate.check([manifest], output)
    report = json.loads((output / "coverage.json").read_text())
    names = {name.replace("\\", "/") for name in report["files"]}
    assert "src/mmm_intelligence/integrations/worker.py" in names
    assert {"server.py", "plugins/mmm-intelligence-local/launch.py"} <= names
    assert len(names) == len(gate.sources())
    assert report["totals"]["missing_lines"] > 0 and report["totals"]["missing_branches"] > 0


def test_plugin_package_server_hash_cannot_be_confused_with_root_launcher(tmp_path):
    gate = gate_module()
    copied = tmp_path / "plugin/server/mmm_intelligence"
    shutil.copytree(
        gate.ROOT / "src/mmm_intelligence", copied, ignore=shutil.ignore_patterns("__pycache__")
    )
    capture = tmp_path / "capture"
    capture.mkdir()
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import runpy\nrunpy.run_path("
        + repr(str(copied / "server.py"))
        + ",run_name='mmm_intelligence.server')\n"
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--rcfile",
            str(gate.ROOT / "pyproject.toml"),
            "--source",
            str(copied),
            "--data-file",
            str(capture / ".coverage"),
            str(probe),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(copied.parent)},
        check=True,
        capture_output=True,
        timeout=30,
    )
    gate.record(capture, "actual-plugin-server")
    manifest = capture / "manifest.json"
    record = json.loads(manifest.read_text())
    record["source_sha256"]["src/mmm_intelligence/server.py"] = "0" * 64
    manifest.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Executed source changed"):
        gate.check([manifest], tmp_path / "aggregate")
