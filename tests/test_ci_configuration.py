"""Validate the workflow artifact, including commands with YAML-sensitive colons."""

from pathlib import Path

import yaml


def test_workflow_parses_and_all_run_commands_are_strings():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert set(workflow["jobs"]) == {"test", "security"}
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "run" in step:
                assert isinstance(step["run"], str)
