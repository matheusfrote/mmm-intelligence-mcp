"""Check the actual distributable rather than trusting ignore patterns."""

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def test_source_and_wheel_include_workers_but_exclude_private_runtime(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(tmp_path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    with tarfile.open(next(tmp_path.glob("*.tar.gz"))) as archive:
        names = ["/".join(Path(n).parts[1:]) for n in archive.getnames()]
    assert "examples/mcp-config.example.json" in names
    assert "src/mmm_intelligence/integrations/robyn_worker.R" in names
    assert "IMPLEMENTATION_PROGRESS.md" in names
    assert "MMM_AUDIT_REPORT.md" in names
    assert "SECURITY_DEPLOY_AUDIT.md" in names
    assert "docs/validation/v4/demo.csv" in names
    assert "tests/web/dashboard.test.mjs" in names
    assert "package-lock.json" in names
    assert "LICENSE" in names and "NOTICE" in names
    assert not any(
        n.startswith(("var/", "evidence/", ".venv/"))
        or n.endswith(".local.json")
        or n == "preservation-baseline.json"
        for n in names
    )
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as archive:
        assert "mmm_intelligence/integrations/robyn_worker.R" in archive.namelist()
        for name in (
            "index.html",
            "app.js",
            "client.js",
            "views.js",
            "charts.js",
            "ui.js",
            "app.css",
            "icon.svg",
        ):
            assert "mmm_intelligence/web/" + name in archive.namelist()
        metadata = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        assert "License-Expression: Apache-2.0" in archive.read(metadata).decode()
        assert any(n.endswith("/licenses/LICENSE") for n in archive.namelist())
        assert any(n.endswith("/licenses/NOTICE") for n in archive.namelist())
