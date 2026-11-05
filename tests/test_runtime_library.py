"""Trusted R library configuration also works outside an editable checkout."""

from pathlib import Path

import pytest

from mmm_intelligence.errors import MMMError


def test_explicit_r_library_is_not_replaced_by_checkout_default(monkeypatch, tmp_path):
    from mmm_intelligence.integrations.bridge import configured_r_library

    monkeypatch.setenv("MMM_R_LIBRARY", str(tmp_path))
    assert configured_r_library() == tmp_path
    monkeypatch.setenv("MMM_R_LIBRARY", str(tmp_path / "missing"))
    with pytest.raises(MMMError, match="library") as failure:
        configured_r_library()
    assert failure.value.code == "INVALID_CONFIG"
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setenv("MMM_R_LIBRARY", tmp_path.name)
    assert configured_r_library() == tmp_path
    monkeypatch.delenv("MMM_R_LIBRARY")
    assert configured_r_library() == Path(__file__).resolve().parents[1] / "var/runtime/r-library"


def test_external_library_descriptions_are_included_in_identity(monkeypatch, dataset):
    """Metadata-only unit fixture; does not execute or certify an R runtime."""
    import hashlib
    import sys
    import tempfile

    from mmm_intelligence.refits import training_identity

    with tempfile.TemporaryDirectory(prefix="mmm-r-metadata-") as temporary:
        library = Path(temporary)
        package = library / "unit_metadata_fixture"
        package.mkdir()
        description = b"Package: unit_metadata_fixture\nVersion: 0.0.0\n"
        (package / "DESCRIPTION").write_bytes(description)
        monkeypatch.setenv("MMM_R_LIBRARY", str(library))
        monkeypatch.setenv("MMM_ROBYN_PYTHON", sys.executable)
        identity = training_identity("meta_robyn", dataset, {})
        key = str(Path("R_library") / "unit_metadata_fixture" / "DESCRIPTION")
        assert identity["runtime_metadata_sha256"][key] == hashlib.sha256(description).hexdigest()
