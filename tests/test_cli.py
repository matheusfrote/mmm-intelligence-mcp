import json
import os
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "mmm_intelligence.cli", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_doctor_does_not_create_storage_or_expose_credentials(tmp_path, monkeypatch):
    root = tmp_path / "absent"
    monkeypatch.setenv("MMM_DATA_DIR", str(root))
    monkeypatch.setenv("MMM_USERS_JSON", "private-test-value")
    result = run_cli("doctor")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["base_runtime_ok"]
    assert "private-test-value" not in result.stdout
    assert not root.exists()
    assert data["optional_runtimes"]["google_meridian"]["library_verified"] is False


def test_config_is_absolute_and_stdio_only_without_writing(tmp_path):
    result = run_cli("config", "--data-dir", str(tmp_path / "with spaces"))
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)["mcpServers"]["mmm-intelligence"]
    assert os.path.isabs(config["command"])
    assert config["args"] == ["-m", "mmm_intelligence.server"]
    assert config["env"]["MMM_ALLOW_REAL_DATA"] == "false"
    assert config["env"]["MMM_TRANSPORT"] == "stdio"
    assert not (tmp_path / "with spaces").exists()


def test_version_and_unknown_command():
    assert run_cli("--version").returncode == 0
    assert run_cli("arbitrary-command").returncode != 0


def test_delete_cli_honors_host_limits_and_exact_hash(tmp_path, monkeypatch):
    from mmm_intelligence.config import Settings
    from mmm_intelligence.storage import ArtifactStore, digest

    store = ArtifactStore(Settings(tmp_path))
    payload = {"synthetic": True, "body": "x" * 2000}
    store.write("reports", "operator", payload)
    args = ("delete-artifact", "--data-dir", str(tmp_path), "--kind", "reports", "--id", "operator")
    monkeypatch.setenv("MMM_MAX_FILE_BYTES", "1024")
    result = run_cli(*args, "--sha256", digest(payload))
    assert result.returncode == 1
    assert store.path("reports", "operator").exists()
    monkeypatch.setenv("MMM_MAX_FILE_BYTES", "10485760")
    assert run_cli(*args, "--sha256", "0" * 64).returncode == 1
    result = run_cli(*args, "--sha256", digest(payload))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["deleted"]
    assert not store.path("reports", "operator").exists()
