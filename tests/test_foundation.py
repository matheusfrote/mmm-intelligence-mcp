from pathlib import Path

import pytest
from pydantic import ValidationError

from mmm_intelligence.config import Settings
from mmm_intelligence.errors import MMMError
from mmm_intelligence.schemas import GenerateRequest, SimulateRequest
from mmm_intelligence.storage import ArtifactStore


def test_storage_roundtrip_and_no_overwrite(tmp_path):
    store = ArtifactStore(Settings(tmp_path))
    store.write("datasets", "demo", {"synthetic": True})
    with pytest.raises(MMMError, match="exists"):
        store.write("datasets", "demo", {"synthetic": False})
    assert store.read("datasets", "demo") == {"synthetic": True}
    assert not list((tmp_path / "datasets").glob(".pending-*"))


@pytest.mark.parametrize("name", ["../secret", "C:\\secret", "/tmp/x", "con", "a/b", "x:y"])
def test_path_rejected(tmp_path, name):
    with pytest.raises(MMMError):
        ArtifactStore(Settings(tmp_path)).read("datasets", name)


def test_contracts_and_environment(monkeypatch):
    monkeypatch.setenv("MMM_DATA_DIR", "./local")
    assert Settings.from_env().data_dir == Path("./local").absolute()
    monkeypatch.setenv("MMM_ALLOW_REAL_DATA", "yes")
    with pytest.raises(ValueError):
        Settings.from_env()
    for data in ({"periods": True}, {"periods": 2}, {"unknown": 1}):
        with pytest.raises(ValidationError):
            GenerateRequest(**data)
    with pytest.raises(ValidationError):
        SimulateRequest(model_id="a", total_budget=100, allocation={"x": 0.4})
