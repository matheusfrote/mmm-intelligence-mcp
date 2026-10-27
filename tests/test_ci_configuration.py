"""Validate the workflow artifact, including commands with YAML-sensitive colons."""

import re
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


def test_all_workflows_are_read_only_with_pinned_actions_and_string_commands():
    root = Path(__file__).resolve().parents[1] / ".github/workflows"
    for path in root.glob("*.yml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert workflow["permissions"] == {"contents": "read"}, path.name
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                if "run" in step:
                    assert isinstance(step["run"], str), path.name
                if "uses" in step:
                    assert re.search(r"@[0-9a-f]{40}$", step["uses"]), path.name
