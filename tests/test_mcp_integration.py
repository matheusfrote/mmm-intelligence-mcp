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
    report = asyncio.run(workflow.cycle(tmp_path / "mcp-data", entrypoint=entrypoint))
    assert report["restart_persistence"]
    assert len(report["calls"]) == 5
