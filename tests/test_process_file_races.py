"""Deterministic OS/library fault boundaries and real file changes during checks."""

import ctypes
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mmm_intelligence import lifecycle, resources, storage
from mmm_intelligence.config import Settings
from mmm_intelligence.errors import MMMError
from mmm_intelligence.storage import ArtifactStore, canonical, digest


def test_inventory_limit_checks_before_reading_an_extra_artifact(service, monkeypatch):
    assert lifecycle.MAX_INVENTORY == 10000
    for i in range(3):
        service.store.write("reports", f"report-{i}", {"synthetic": True})
    monkeypatch.setattr(lifecycle, "MAX_INVENTORY", 2)
    with pytest.raises(MMMError) as caught:
        lifecycle.inventory(service.store)
    assert caught.value.code == "INVENTORY_LIMIT"
    assert len(list((service.store.root / "reports").glob("*.json"))) == 3


def test_read_refuses_file_grown_after_stat(tmp_path, monkeypatch):
    store = ArtifactStore(Settings(tmp_path, max_file_bytes=1024))
    store.write("reports", "race", {"synthetic": True})
    target = store.path("reports", "race")
    original = Path.open
    armed = True

    def changed(path, *args, **kwargs):
        nonlocal armed
        if path == target and armed and args == ("rb",):
            armed = False
            with original(target, "ab") as out:
                out.write(b"x" * 2048)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", changed)
    with pytest.raises(MMMError) as caught:
        store.read("reports", "race")
    assert caught.value.code == "ARTIFACT_TOO_LARGE"


def test_delete_refuses_changed_hash_during_final_review(service, monkeypatch):
    payload = {"synthetic": True, "value": 1}
    service.store.write("reports", "race", payload)
    path = service.store.path("reports", "race")
    original = service.store.read
    count = 0

    def changed(kind, artifact_id):
        nonlocal count
        count += 1
        if count == 3:
            new = {**payload, "value": 2}
            path.write_bytes(
                canonical(
                    {"schema_version": 1, "kind": kind, "payload": new, "sha256": digest(new)}
                )
            )
        return original(kind, artifact_id)

    monkeypatch.setattr(service.store, "read", changed)
    with pytest.raises(MMMError) as caught:
        lifecycle.delete_artifact(service.store, "reports", "race", digest(payload))
    assert caught.value.code == "HASH_MISMATCH" and path.exists()


def make_link(link, destination):
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(destination)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(destination, target_is_directory=True)


def remove_link(link):
    if os.name == "nt":
        link.rmdir()
    else:
        link.unlink()


@pytest.mark.parametrize("stage", ["store", "delete"])
def test_containment_rechecked_after_real_directory_swap(tmp_path, monkeypatch, stage):
    store = ArtifactStore(Settings(tmp_path / "data"))
    payload = {"synthetic": True}
    checksum = store.write("reports", "race", payload)
    directory = store.root / "reports"
    parked = store.root / "parked"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "race.json"
    sentinel.write_text("preserve")
    swapped = False

    def swap():
        nonlocal swapped
        directory.rename(parked)
        make_link(directory, outside)
        swapped = True

    if stage == "store":
        original = storage.reject_links

        def check(path):
            original(path)
            if path.name == "race.json" and not swapped:
                swap()

        monkeypatch.setattr(storage, "reject_links", check)
    else:
        original_path = store.path
        count = 0

        def checked(kind, artifact_id):
            nonlocal count
            count += 1
            path = original_path(kind, artifact_id)
            # initial path, initial read, inventory read/path, final read, final path.
            if count == 6:
                swap()
            return path

        monkeypatch.setattr(store, "path", checked)
    try:
        with pytest.raises(MMMError) as caught:
            if stage == "store":
                store.path("reports", "race")
            else:
                lifecycle.delete_artifact(store, "reports", "race", checksum)
        assert caught.value.code == "UNSAFE_PATH"
        assert sentinel.read_text() == "preserve"
    finally:
        if swapped:
            remove_link(directory)


def test_worker_output_reader_failure_does_not_return_success(tmp_path, monkeypatch):
    original = resources.threading.Thread

    class FailedReader:
        def __init__(self, **kwargs):
            self.thread = original(**kwargs)

        def start(self):
            self.thread.start()

        def join(self, **kwargs):
            self.thread.join(**kwargs)

        def is_alive(self):
            return True  # injected thread lifecycle failure, not successful execution

    monkeypatch.setattr(resources.threading, "Thread", FailedReader)
    with pytest.raises(RuntimeError, match="output did not close"):
        resources.run_worker(
            [sys.executable, "-c", "print('test')"],
            timeout=10,
            env=None,
            cwd=tmp_path,
            stdout=io.BytesIO(),
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows native job API failure")
def test_windows_cpu_job_api_failure_kills_the_child(tmp_path, monkeypatch):
    original = ctypes.WinDLL

    class Refused:
        def __call__(self, *args):
            return False

    def kernel(*args, **kwargs):
        original(*args, **kwargs)
        return type("KernelBoundary", (), {"SetInformationJobObject": Refused()})()

    monkeypatch.setattr(ctypes, "WinDLL", kernel)
    with pytest.raises(OSError):
        resources.run_worker(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout=10,
            env=None,
            cwd=tmp_path,
            stdout=io.BytesIO(),
        )
