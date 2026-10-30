import asyncio
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("entrypoint", ["module", "script"])
def test_full_stdio_cycle_with_restart(tmp_path, entrypoint):
    source = Path(__file__).resolve().parents[1] / "examples" / "mcp_workflow.py"
    spec = importlib.util.spec_from_file_location("workflow", source)
    workflow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(workflow)
    extended = entrypoint == "module"
    report = asyncio.run(
        workflow.cycle(tmp_path / "mcp-data", entrypoint=entrypoint, extended=extended)
    )
    assert report["restart_persistence"]
    assert len(report["calls"]) == (23 if extended else 5)
    if extended:
        audit = report["calls"]["audit_model"]["data"]
        assert audit["decomposition"]["maximum_reconciliation_error"] < 1e-8
        assert not audit["decision_support"]["business_recommendation_eligible"]
