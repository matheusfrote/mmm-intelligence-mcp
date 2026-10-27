import asyncio
import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest
import yaml
from mcp import Client, StdioServerParameters


def test_local_plugin_archive_is_reproducible_and_contains_real_components(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("build_plugin", root / "examples/build_plugin.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    one, two = tmp_path / "one.zip", tmp_path / "two.zip"
    assert builder.build(one) == builder.build(two)
    with pytest.raises(FileExistsError):
        builder.build(one)
    with zipfile.ZipFile(one) as archive:
        names = archive.namelist()
        assert "server/mmm_intelligence/web/client.js" in names
        assert "LICENSE" in names and "NOTICE" in names
        assert not any("node_modules" in n or "__pycache__" in n or ".app.json" in n for n in names)
        plugin = json.loads(archive.read("plugin.json"))
        assert plugin["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        interface = plugin["extensions"]["com.openai"]["interface"]
        assert len(interface["shortDescription"]) <= 30
        assert interface["category"] == "Data & Analytics"
        assert interface["logo"].removeprefix("./") in names
        mcp = json.loads(archive.read("mcp.json"))
        server = mcp["mcpServers"]["mmm-intelligence"]
        assert server["type"] == "stdio" and "url" not in server
        assert server["args"] == ["${PLUGIN_ROOT}/launch.py"]
        skill = archive.read("skills/explore-mmm/SKILL.md").decode()
        assert yaml.safe_load(skill.split("---")[1])["name"] == "explore-mmm"


def test_bundled_plugin_starts_outside_checkout_and_discovers_tools(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("build_plugin", root / "examples/build_plugin.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    archive = tmp_path / "plugin.zip"
    builder.build(archive)
    installation = tmp_path / "plugin"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(installation)  # trusted archive just built above
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(installation / "launch.py")],
        cwd=tmp_path,
        env={**os.environ, "MMM_DATA_DIR": str(tmp_path / "data"), "MMM_ALLOW_REAL_DATA": "false"},
    )

    async def check():
        async with Client(parameters) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 26
            generated = await client.call_tool(
                "generate_demo_dataset", {"request": {"dataset_id": "plugin-demo"}}
            )
            assert generated.structured_content["ok"]
            validated = await client.call_tool(
                "validate_dataset", {"request": {"dataset_id": "plugin-demo"}}
            )
            assert validated.structured_content["data"]["valid"]

    asyncio.run(check())
