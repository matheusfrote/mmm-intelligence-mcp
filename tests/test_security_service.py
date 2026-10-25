import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from mmm_intelligence.config import Settings
from mmm_intelligence.errors import MMMError
from mmm_intelligence.schemas import ModelRequest
from mmm_intelligence.service import MMMService
from mmm_intelligence.storage import ArtifactStore


def test_real_data_guard_including_model_reads(service, dataset):
    dataset["synthetic"] = False
    service.store.write("datasets", "private", dataset)
    for name in ["validate_dataset", "train_mmm"]:
        result = service.call(name, {"dataset_id": "private"})
        assert not result.ok
        assert result.error.code == "REAL_DATA_DISABLED"
    service.store.write("models", "private", {"synthetic": False})
    assert service.call("get_model", {"model_id": "private"}).error.code == "REAL_DATA_DISABLED"


def test_operator_authorized_data_and_defaults(tmp_path, dataset):
    dataset["synthetic"] = False
    svc = MMMService(Settings(tmp_path / "authorized", allow_real_data=True))
    try:
        svc.store.write("datasets", "authorized", dataset)
        assert svc.call("validate_dataset", {"dataset_id": "authorized"}).data["valid"]
    finally:
        svc.close()
    assert Settings(tmp_path).allow_real_data is False


def test_corruption_and_file_limit_are_structured(service):
    path = service.store.path("datasets", "broken")
    path.write_text('{"payload": null}', encoding="utf-8")
    assert (
        service.call("validate_dataset", {"dataset_id": "broken"}).error.code == "CORRUPT_ARTIFACT"
    )
    service.store.write("datasets", "tampered", {"synthetic": True})
    path = service.store.path("datasets", "tampered")
    envelope = json.loads(path.read_text())
    envelope["payload"]["synthetic"] = False
    path.write_text(json.dumps(envelope))
    assert (
        service.call("validate_dataset", {"dataset_id": "tampered"}).error.code
        == "CORRUPT_ARTIFACT"
    )
    small = ArtifactStore(Settings(service.store.root / "small", max_file_bytes=1024))
    with pytest.raises(MMMError, match="byte limit"):
        small.write("datasets", "huge", {"x": "x" * 2000})
    small.path("datasets", "huge").write_text("x" * 2000)
    with pytest.raises(MMMError, match="byte limit"):
        small.read("datasets", "huge")


def test_racing_writes_never_replace(tmp_path):
    store = ArtifactStore(Settings(tmp_path))

    def write(value):
        try:
            store.write("datasets", "same", {"winner": value})
            return "ok"
        except MMMError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(write, [1, 2]))
    assert sorted(statuses) == ["ALREADY_EXISTS", "ok"]
    assert store.read("datasets", "same")["winner"] in {1, 2}


def test_hard_link_cannot_read_external_file(tmp_path):
    store = ArtifactStore(Settings(tmp_path / "inside"))
    outside = tmp_path / "secret.json"
    outside.write_text('{"secret": "private"}')
    os.link(outside, store.path("datasets", "escape"))
    with pytest.raises(MMMError, match="regular, unlinked"):
        store.read("datasets", "escape")


def test_junction_or_symlink_blocks_directory_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    inside = tmp_path / "inside"
    inside.mkdir()
    link = inside / "datasets"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(MMMError, match="Links"):
            ArtifactStore(Settings(inside))
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()
    assert not list(outside.iterdir())


def test_model_immutable_during_read_and_simulation(service, trained):
    before = service.store.path("models", "fit").read_bytes()
    result = service.call(
        "simulate_budget",
        {
            "model_id": "fit",
            "total_budget": 10000,
            "allocation": {c: 1 / 3 for c in trained["request"]["media_columns"]},
        },
    )
    assert result.ok
    assert service.get_model(ModelRequest(model_id="fit")) == trained
    assert service.store.path("models", "fit").read_bytes() == before
    duplicate = service.call("train_mmm", {"dataset_id": "demo", "model_id": "fit"})
    assert duplicate.error.code == "ALREADY_EXISTS"


def test_failures_logged_without_payload_or_paths(service, monkeypatch):
    result = service.call("get_model", {"model_id": "../SENSITIVE"})
    assert result.error.code == "INPUT_INVALID"
    assert service.call("unknown", {}).error.code == "UNKNOWN_TOOL"
    assert (
        service.call(
            "generate_demo_dataset", {"periods": 52, "start_date": "9999-12-31"}
        ).error.code
        == "INVALID_DATA"
    )

    def fail(*args):
        raise OSError("SENSITIVE host path")

    monkeypatch.setattr(service.store, "read", fail)
    assert service.call("get_model", {"model_id": "x"}).error.code == "STORAGE_ERROR"
    log = (service.store.root / "logs" / "server.log").read_text()
    assert "SENSITIVE" not in log
    assert "code=INPUT_INVALID" in log and "code=STORAGE_ERROR" in log


def test_invalid_dataset_and_constant_media_block_training(service, dataset):
    dataset["rows"][0]["revenue"] = None
    service.store.write("datasets", "invalid", dataset)
    assert service.call("train_mmm", {"dataset_id": "invalid"}).error.code == "DATASET_INVALID"
    for row in dataset["rows"]:
        row["revenue"] = 100
        row["spend_search"] = 0
    service.store.write("datasets", "constant", dataset)
    assert (
        service.call("train_mmm", {"dataset_id": "constant"}).error.code == "UNIDENTIFIABLE_MEDIA"
    )


def test_invalid_output_never_logs_success_or_labels_input_invalid(service, monkeypatch):
    monkeypatch.setattr(service, "backend_status", lambda request: {"warnings": "invalid-output"})
    result = service.call("backend_status", {})
    assert not result.ok and result.error.code == "INTERNAL_ERROR"
    log = (service.store.root / "logs" / "server.log").read_text()
    assert "status=ok" not in log
    assert "status=error code=INTERNAL_ERROR" in log
