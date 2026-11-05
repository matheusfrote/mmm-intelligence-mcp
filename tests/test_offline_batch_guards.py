"""Operator helpers never import failed fits or use unauthorized real datasets."""

import json
import subprocess
import sys
from pathlib import Path

from mmm_intelligence.config import Settings
from mmm_intelligence.storage import ArtifactStore, digest


def test_failed_operator_batch_cannot_enter_model_ledger(tmp_path):
    batch = tmp_path / "failed"
    batch.mkdir()
    (batch / "result.json").write_text(json.dumps({"operational": "failed", "synthetic": True}))
    result = subprocess.run(
        [
            sys.executable,
            "examples/import_robyn_batch.py",
            "--store",
            str(tmp_path / "store"),
            "--batch",
            str(batch),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0 and "Only completed synthetic batches" in result.stderr
    assert not (tmp_path / "store").exists()


def test_operator_batch_refuses_real_data_before_native_execution(tmp_path):
    store = ArtifactStore(Settings(tmp_path / "store"))
    dataset = {"synthetic": False, "rows": []}
    # Invalid reference for an admission test only; never a claimed native fit.
    store.write("datasets", "unauthorized", dataset)
    store.write(
        "backend_models",
        "admission-fixture",
        {"dataset_id": "unauthorized", "dataset_sha256": digest(dataset)},
    )
    output = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "examples/robyn_offline_refit.py",
            "--store",
            str(store.root),
            "--model-id",
            "admission-fixture",
            "--seed",
            "97",
            "--output-dir",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0 and "Only synthetic data are authorized" in result.stderr
    assert not output.exists()
