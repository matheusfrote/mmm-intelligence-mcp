"""Private worker envelopes must contain dependency failures and sanitize paths."""

import json
import sys

import numpy as np
import pytest

from mmm_intelligence.integrations import worker


def invoke(tmp_path, monkeypatch, backend, payload):
    source = tmp_path / "input.json"
    destination = tmp_path / "output.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["worker.py", backend, str(source), str(destination)])
    worker.main()
    return json.loads(destination.read_text(encoding="utf-8"))


def test_worker_domain_and_missing_r_runtime_fail_in_structured_envelope(tmp_path, monkeypatch):
    result = invoke(
        tmp_path,
        monkeypatch,
        "meta_robyn",
        {
            "operation": "train",
            "dataset": {"synthetic": True, "target_type": "unspecified", "source": "supplied"},
            "request": {"target_column": "revenue"},
        },
    )
    assert result["ok"] is False and result["code"] == "BACKEND_FAILED"
    assert "declared revenue" in result["message"]
    monkeypatch.setenv("MMM_RSCRIPT", str(tmp_path / "missing-Rscript"))
    result = invoke(tmp_path, monkeypatch, "meta_robyn", {"operation": "predict"})
    assert result["ok"] is False and "runtime is unavailable" in result["message"]


def test_worker_dependency_failure_does_not_expose_job_or_home_path(tmp_path, monkeypatch):
    def broken(payload, root):
        raise ValueError("private diagnostic path " + str(root))

    monkeypatch.setattr(worker, "meridian", broken)
    result = invoke(tmp_path, monkeypatch, "google_meridian", {"operation": "train"})
    assert result["ok"] is False and "<job>" in result["message"]
    assert str(tmp_path) not in result["message"]


def test_worker_serializes_arrays_and_nonfinite_optional_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(
        worker,
        "pymc",
        lambda payload, root: {
            "warnings": "functional only",
            "mean": np.array([1.0, 2.0]),
            "optional": float("nan"),
        },
    )
    result = invoke(tmp_path, monkeypatch, "pymc_marketing", {"operation": "predict"})
    assert result == {
        "ok": True,
        "data": {"warnings": ["functional only"], "mean": [1.0, 2.0], "optional": None},
    }


def test_native_prediction_invalid_support_and_tiny_split_are_rejected():
    with pytest.raises(ValueError, match="Nonfinite"):
        worker.summarize([[float("inf")]], ["2026-01-01"])
    with pytest.raises(ValueError, match="empty partition"):
        worker.robyn_split_indices(3, 0.99)
    with pytest.raises(ValueError, match="Invalid native Robyn split"):
        worker.robyn_split_indices(True, 0.6)
    with pytest.raises(ValueError, match="two train"):
        worker.prepare_meridian_holdout(
            {"target_type": "revenue", "rows": [{"y": 1}, {"y": 2}]},
            {"target_column": "y", "test_fraction": 0.9},
        )
