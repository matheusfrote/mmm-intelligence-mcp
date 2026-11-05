"""Expensive scientific refits survive retries without being mistaken for new draws."""

import pytest

from mmm_intelligence.schemas import ScientificProtocol
from mmm_intelligence.validation import stability_study


def test_partial_configuration_reuses_only_after_defaults_are_normalized(service):
    from mmm_intelligence.refits import fit_or_reuse

    assert service.call("generate_demo_dataset", {"dataset_id": "defaults"}).ok
    data = service.load_dataset("defaults")
    fitted, reused = fit_or_reuse(service, "ridge", data, {"dataset_id": "defaults"})
    assert not reused
    second, reused = fit_or_reuse(service, "ridge", data, {"dataset_id": "defaults"})
    assert reused and second == fitted


def test_changed_source_refuses_reuse_after_actual_ridge_fit(service, dataset, monkeypatch):
    from mmm_intelligence import refits
    from mmm_intelligence.errors import MMMError

    original = refits.training_identity
    calls = 0

    def changing(*args):
        nonlocal calls
        calls += 1
        identity = original(*args)
        if calls > 1:
            identity["source_sha256"]["modeling.py"] = "source changed during unit regression"
        return identity

    monkeypatch.setattr(refits, "training_identity", changing)
    with pytest.raises(MMMError, match="changed"):
        refits.fit_or_reuse(service, "ridge", dataset, {"dataset_id": "changed"})
    assert not list((service.store.root / "models").glob("*.json"))


def test_tampered_refit_identity_is_not_accepted_even_with_a_rehashed_envelope(service, dataset):
    import json

    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.refits import fit_or_reuse
    from mmm_intelligence.storage import digest

    fitted, _ = fit_or_reuse(service, "ridge", dataset, {"dataset_id": "tamper"})
    path = service.store.path("models", fitted["model_id"])
    envelope = json.loads(path.read_text())
    envelope["payload"]["scientific_training_identity"] = {}
    envelope["sha256"] = digest(envelope["payload"])
    path.write_text(json.dumps(envelope))
    with pytest.raises(MMMError, match="identity"):
        fit_or_reuse(service, "ridge", dataset, {"dataset_id": "tamper"})


@pytest.mark.parametrize("parent", ["bin", "custom-runtime"])
def test_unverifiable_native_runtime_metadata_abstains_without_executing_it(
    dataset, monkeypatch, tmp_path, parent
):
    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.refits import training_identity

    runtime = tmp_path / parent / "python"
    runtime.parent.mkdir()
    runtime.write_text("unit-only non-executable placeholder")
    monkeypatch.setenv("MMM_PYMC_PYTHON", str(runtime))
    with pytest.raises(MMMError, match="metadata"):
        training_identity("pymc_marketing", dataset, {})


def test_real_refits_are_immutable_and_explicitly_reused(service, trained):
    dataset = service.load_dataset("demo")
    first = stability_study(service, trained, dataset, "ridge", ScientificProtocol())
    assert all("model_id" in row for row in first["runs"])
    second = stability_study(service, trained, dataset, "ridge", ScientificProtocol())
    assert all(row["reused"] for row in second["runs"])
    assert [r["model_sha256"] for r in first["runs"]] == [r["model_sha256"] for r in second["runs"]]
    assert all(not r["reused"] for r in first["runs"])


def test_native_constant_media_is_rejected_before_worker(service, dataset, monkeypatch, tmp_path):
    monkeypatch.setenv("MMM_ROBYN_PYTHON", str(tmp_path / "not-installed.exe"))
    for row in dataset["rows"]:
        row["spend_search"] = 100
    # Public native training shares the same preflight as scientific refits.
    service.store.write("datasets", "constant-native", dataset)
    result = service.call(
        "train_backend", {"dataset_id": "constant-native", "backend": "meta_robyn"}
    )
    assert not result.ok and result.error.code == "UNIDENTIFIABLE_MEDIA"


def test_missing_r_and_python_configuration_is_not_native_provenance(
    dataset, monkeypatch, tmp_path
):
    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.refits import training_identity

    monkeypatch.setenv("MMM_RSCRIPT", str(tmp_path / "not-installed-Rscript"))
    monkeypatch.setenv("MMM_ROBYN_PYTHON", str(tmp_path / "not-installed-python"))
    with pytest.raises(MMMError, match="unavailable"):
        training_identity("meta_robyn", dataset, {})


def test_robyn_wrapper_change_invalidates_scientific_refit_identity(dataset, monkeypatch, tmp_path):
    """Hash regression only: no placeholder fit is passed as native evidence."""
    import hashlib
    import sys
    from pathlib import Path

    from mmm_intelligence.refits import training_identity
    from mmm_intelligence.storage import digest

    monkeypatch.setenv("MMM_R_LIBRARY", str(tmp_path))
    monkeypatch.setenv("MMM_RSCRIPT", str(tmp_path / "not-installed-Rscript"))
    monkeypatch.setenv("MMM_ROBYN_PYTHON", sys.executable)
    before = training_identity("meta_robyn", dataset, {})
    original = Path.read_bytes
    wrapper = Path(__file__).resolve().parents[1] / "src/mmm_intelligence/integrations/worker.py"
    changed = original(wrapper) + b"\n# changed wrapper for provenance regression\n"

    def read_source(path):
        return changed if path == wrapper else original(path)

    monkeypatch.setattr(Path, "read_bytes", read_source)
    after = training_identity("meta_robyn", dataset, {})
    assert digest(before) != digest(after)
    assert after["source_sha256"]["integrations/worker.py"] == hashlib.sha256(changed).hexdigest()
    assert (
        before["source_sha256"]["integrations/robyn_worker.R"]
        == after["source_sha256"]["integrations/robyn_worker.R"]
    )
