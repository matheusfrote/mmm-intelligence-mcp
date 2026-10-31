"""Extensive sampling is explicitly separated from quick compatibility checks."""

from pathlib import Path

import yaml


def test_extensive_workflow_is_manual_reuses_pinned_runtimes_and_records_outcomes():
    root = Path(__file__).resolve().parents[1]
    path = root / ".github/workflows/scientific-validation.yml"
    assert path.is_file()
    workflow = yaml.safe_load(path.read_text())
    events = workflow.get("on", workflow.get(True))  # YAML1.1 interprets 'on' as a boolean.
    assert set(events) == {"workflow_dispatch"}
    assert workflow["jobs"]["scientific"]["uses"] == "./.github/workflows/native-engines.yml"
    assert workflow["jobs"]["scientific"]["with"]["scientific_extensive"] is True
    native = (root / ".github/workflows/native-engines.yml").read_text()
    assert "examples/scientific_protocol.py --backend all" in native
    assert "inputs.scientific_extensive" in native
    assert "evidence/scientific-extensive/result.json" in native
