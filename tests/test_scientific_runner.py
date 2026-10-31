"""The public reproducibility command uses a real official SDK stdio server."""

import json
import subprocess
import sys
from pathlib import Path


def test_scientific_runner_preserves_independent_classifications(tmp_path):
    project = Path(__file__).resolve().parents[1]
    output = tmp_path / "run"
    result = subprocess.run(
        [
            sys.executable,
            "examples/scientific_protocol.py",
            "--backend",
            "ridge",
            "--output-dir",
            str(output),
            "--transport-smoke",
            "--skip-refits",
            "--replications",
            "2",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr[-5000:]
    receipt = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert receipt["transport"] == "official_sdk_stdio"
    assert receipt["profiles"]["ridge"]["classifications"]["causal"]["status"] == "simulation_only"
    assert receipt["source_unchanged"] is True
    assert receipt["scientific_approval"] is False
    assert receipt["profiles"]["ridge"]["monte_carlo"]["attempted"] == 20
    reused = tmp_path / "reused"
    second = subprocess.run(
        [
            sys.executable,
            "examples/scientific_protocol.py",
            "--backend",
            "ridge",
            "--reuse-store",
            str(output / "data"),
            "--output-dir",
            str(reused),
            "--transport-smoke",
            "--skip-refits",
            "--replications",
            "2",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert second.returncode == 0, second.stderr[-5000:]
    copied = json.loads((reused / "result.json").read_text(encoding="utf-8"))
    assert copied["reused_models"] == ["ridge"]
    assert (
        copied["profiles"]["ridge"]["provenance"]["model_sha256"]
        == receipt["profiles"]["ridge"]["provenance"]["model_sha256"]
    )
