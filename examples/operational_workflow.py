"""Official stdio client: original + universal workflows, all45 tools, resource and prompts.

Use --native for the complete acceptance cycle. Reduced MCMC proves software
transport/persistence only; this does not certify analytical convergence.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from closure_workflow import run as closure
from mcp import Client, StdioServerParameters
from mcp_workflow import TOOLS, cycle


async def run(output, native, resume=False):
    if not resume:
        output.mkdir(parents=True, exist_ok=False)
        original = await cycle(output / "original-data", extended=True)
        (output / "original.json").write_text(json.dumps(original, indent=2), encoding="utf-8")
        await closure(output / "universal", native)
    original = json.loads((output / "original.json").read_text(encoding="utf-8"))
    universal = json.loads((output / "universal/result.json").read_text(encoding="utf-8"))
    assert universal["native_cycles_requested"] == native
    executed = set(original["calls"]) | set(universal["calls"])
    missing = sorted(TOOLS - executed)
    model = universal["models"]["ridge"]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mmm_intelligence.server"],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "MMM_DATA_DIR": str(output / "universal/data"),
            "MMM_TRANSPORT": "stdio",
            "MMM_ALLOW_REAL_DATA": "false",
        },
    )
    async with Client(parameters) as client:
        assert {tool.name for tool in (await client.list_tools()).tools} == TOOLS
        normalized_id = model["preparation"]["source_ids"][0]
        restored = await client.call_tool(
            "get_growth_artifact", {"request": {"artifact_id": normalized_id}}
        )
        assert (
            restored.structured_content["ok"]
            and restored.structured_content["data"]["artifact_type"] == "normalized"
        )
        screen = await client.call_tool(
            "check_mmm_eligibility",
            {
                "request": {
                    "artifact_id": normalized_id,
                    "backend": "ridge",
                    "kpi": "revenue",
                    "media": ["spend_search", "spend_social", "spend_video"],
                    "controls": ["price_index", "promotion"],
                    "target_type": "revenue",
                }
            },
        )
        assert screen.structured_content["ok"] and screen.structured_content["data"]["eligible"]
        executed.update(["get_growth_artifact", "check_mmm_eligibility"])
        missing = sorted(TOOLS - executed)
        assert (
            not missing
            if native
            else set(missing) <= {"train_backend", "get_backend_model", "predict_backend"}
        )
        templates = (await client.list_resource_templates()).resource_templates
        assert (
            len(templates) == 1 and str(templates[0].uri_template) == "mmm://datasets/{dataset_id}"
        )
        resource = await client.read_resource(
            "mmm://datasets/" + model["preparation"]["dataset_id"]
        )
        data = json.loads(resource.contents[0].text)
        assert data["synthetic"] is True and len(data["rows"]) == 104
        if native:
            pymc_model = universal["models"]["pymc_marketing"]
            native_resource = await client.read_resource(
                "mmm://datasets/" + pymc_model["preparation"]["dataset_id"]
            )
            last = json.loads(native_resource.contents[0].text)["rows"][-1]
            future = await client.call_tool(
                "forecast_model",
                {
                    "request": {
                        "model_id": pymc_model["model_id"],
                        "backend": "pymc_marketing",
                        "media_plan": {
                            channel: [1000.0, 1100.0, 900.0, 1000.0]
                            for channel in ["spend_search", "spend_social", "spend_video"]
                        },
                        "future_controls": {
                            column: [last[column]] * 4 for column in ["price_index", "promotion"]
                        },
                    }
                },
            )
            assert future.structured_content["ok"], future.structured_content
            forecast = future.structured_content["data"]
            assert (
                len(forecast["prediction"]["mean"]) == 4
                and forecast["prediction"]["dates"][0] > last["date"]
            )
            assert forecast["scope"] == "future_conditional_projection"
        prompt_args = {
            "audit_mmm_pipeline": {"dataset_id": model["preparation"]["dataset_id"]},
            "simulate_budget_scenario": {"model_id": model["model_id"]},
            "growth_incrementality_test": {"artifact_id": universal["artifacts"][0]},
        }
        assert {prompt.name for prompt in (await client.list_prompts()).prompts} == set(prompt_args)
        prompts = {}
        for name, args in prompt_args.items():
            rendered = await client.get_prompt(name, args)
            assert rendered.messages and rendered.messages[0].role == "user"
            prompts[name] = rendered.model_dump(mode="json")
    result = {
        "synthetic": True,
        "transport": "official_sdk_stdio",
        "executed_tools": sorted(executed),
        "executed_tool_count": len(executed),
        "missing_tools": missing,
        "complete_45_tools_verified": not missing,
        "resource_templates": 1,
        "resource_read_verified": True,
        "prompts": prompts,
        "native_requested": native,
        "causal_identification": False,
        "analytical_convergence_certified": False,
        "restart_verified": True,
        "pymc_future_verified": native,
        "resumed_component_receipts": resume,
    }
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "prompts"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed immutable component receipts, then verify protocol contracts",
    )
    options = parser.parse_args()
    asyncio.run(run(options.output_dir.resolve(), options.native, options.resume))
