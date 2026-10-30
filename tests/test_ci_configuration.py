"""Validate the workflow artifact, including commands with YAML-sensitive colons."""

import re
from pathlib import Path

import yaml


def test_workflow_parses_and_all_run_commands_are_strings():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert set(workflow["jobs"]) == {"test", "security", "native", "coverage"}
    assert set(workflow["jobs"]["coverage"]["needs"]) == {"test", "native"}
    for job in workflow["jobs"].values():
        assert "steps" in job or job.get("uses") == "./.github/workflows/native-engines.yml"
        for step in job.get("steps", []):
            if "run" in step:
                assert isinstance(step["run"], str)


def test_all_workflows_are_read_only_with_pinned_actions_and_string_commands():
    root = Path(__file__).resolve().parents[1] / ".github/workflows"
    for path in root.glob("*.yml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert workflow["permissions"] == {"contents": "read"}, path.name
        for job in workflow["jobs"].values():
            if "uses" in job:
                assert job["uses"] == "./.github/workflows/native-engines.yml"
                assert (root.parents[1] / job["uses"]).is_file()
            else:
                assert "steps" in job
            for step in job.get("steps", []):
                if "run" in step:
                    assert isinstance(step["run"], str), path.name
                if "uses" in step:
                    assert re.search(r"@[0-9a-f]{40}$", step["uses"]), path.name


def test_dashboard_and_container_have_executable_ci_checks():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/dashboard.yml").read_text())
    assert set(workflow["jobs"]) == {"browser", "container"}
    browser = workflow["jobs"]["browser"]
    commands = "\n".join(s.get("run", "") for s in browser["steps"])
    assert "npm ci --ignore-scripts" in commands
    assert "npm run test:web" in commands
    assert browser["env"]["MMM_TEST_BROWSER"] == "chromium"
    container = workflow["jobs"]["container"]
    assert any("examples/container_smoke.py" in s.get("run", "") for s in container["steps"])
