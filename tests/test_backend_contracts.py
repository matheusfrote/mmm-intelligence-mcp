import pytest

from mmm_intelligence.errors import MMMError
from mmm_intelligence.integrations.bridge import execute


def test_backend_missing_runtime_never_falls_back_to_ridge(service, monkeypatch):
    monkeypatch.setenv("MMM_MERIDIAN_PYTHON", str(service.store.root / "missing-python"))
    with pytest.raises(MMMError, match="not installed"):
        execute(service.store, "google_meridian", {})


def test_backend_rejects_unknown_and_unbounded_timeout(service, monkeypatch):
    with pytest.raises(MMMError):
        execute(service.store, "unknown", {})
    monkeypatch.setenv("MMM_BACKEND_TIMEOUT_SECONDS", "99999")
    import sys

    monkeypatch.setenv("MMM_MERIDIAN_PYTHON", sys.executable)
    with pytest.raises(MMMError, match="timeout"):
        execute(service.store, "google_meridian", {})


def test_backend_records_exclude_native_code_and_remain_guarded(service):
    service.store.write(
        "backend_models",
        "external",
        {
            "synthetic": True,
            "backend": "test",
            "native_base64": "opaque",
            "dataset": {"rows": []},
            "metrics": {},
        },
    )
    out = service.call("get_backend_model", {"model_id": "external"})
    assert out.ok and "native_base64" not in out.data and "dataset" not in out.data


def test_migration_uses_sdk_v2():
    from importlib.metadata import version

    from mmm_intelligence.server import create_server

    assert version("mcp").split(".")[0] == "2"
    assert callable(create_server)


def test_robyn_rejects_unsupported_temporal_split(service, monkeypatch):
    def must_not_launch(*args, **kwargs):
        pytest.fail("Unsupported split must fail before launching a worker")

    monkeypatch.setattr("mmm_intelligence.integrations.bridge.execute", must_not_launch)
    service.call("generate_demo_dataset", {"dataset_id": "demo"})
    result = service.call(
        "train_backend", {"dataset_id": "demo", "backend": "meta_robyn", "test_fraction": 0.4}
    )
    assert not result.ok and result.error.code == "INPUT_INVALID"
