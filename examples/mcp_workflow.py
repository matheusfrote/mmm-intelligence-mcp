"""Actual SDK v2 stdio cycle, including restart and the new local tools."""

import argparse
import asyncio
import csv
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import validate as validate_json
from mcp import Client, StdioServerParameters

CORE_TOOLS = {
    "generate_demo_dataset",
    "validate_dataset",
    "train_mmm",
    "get_model",
    "simulate_budget",
}
TOOLS = CORE_TOOLS | {
    "backend_status",
    "import_dataset",
    "optimize_budget",
    "tune_mmm",
    "calibrate_experiment",
    "render_dashboard",
    "generate_report",
    "train_backend",
    "predict_backend",
    "get_backend_model",
    "audit_model",
}


async def cycle(data_dir: Path, *, entrypoint: str = "module", extended: bool = False) -> dict:
    project = Path(__file__).resolve().parents[1]
    args = (
        ["-m", "mmm_intelligence.server"]
        if entrypoint == "module"
        else [str(project / "server.py")]
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=args,
        cwd=project,
        env={
            **os.environ,
            "MMM_DATA_DIR": str(data_dir.absolute()),
            "MMM_ALLOW_REAL_DATA": "false",
            "MMM_TRANSPORT": "stdio",
        },
    )
    report = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "transport": "stdio",
        "entrypoint": entrypoint,
        "calls": {},
    }
    async with asyncio.timeout(120):
        async with Client(params) as session:
            report["protocol_version"] = session.protocol_version
            discovered = await session.list_tools()
            assert {t.name for t in discovered.tools} == TOOLS
            schemas = {t.name: t.output_schema for t in discovered.tools}
            assert all(schemas.values())
            report["tools"] = [t.model_dump(mode="json") for t in discovered.tools]

            async def call(name, req):
                result = await session.call_tool(name, {"request": req})
                assert not result.is_error, result.content
                data = result.structured_content
                validate_json(data, schemas[name])
                assert data["ok"], data
                report["calls"][name] = data
                return data["data"]

            demo = await call("generate_demo_dataset", {"periods": 156, "seed": 42})
            assert (await call("validate_dataset", {"dataset_id": demo["dataset_id"]}))["valid"]
            fit = await call(
                "train_mmm",
                {"dataset_id": demo["dataset_id"], "bootstrap_samples": 40 if extended else 0},
            )
            model = await call("get_model", {"model_id": fit["model_id"]})
            total = sum(model["state"]["reference_spend_per_period"].values()) * 13
            await call(
                "simulate_budget",
                {
                    "model_id": fit["model_id"],
                    "horizon": 13,
                    "total_budget": total,
                    "allocation": {"spend_search": 0.5, "spend_social": 0.3, "spend_video": 0.2},
                },
            )
            if extended:
                await call("backend_status", {})
                from mmm_intelligence.datasets import generate
                from mmm_intelligence.schemas import GenerateRequest

                imported = await call(
                    "import_dataset",
                    {
                        "rows": generate(GenerateRequest())["rows"],
                        "synthetic": True,
                        "authorization_reference": "builtin-synthetic-client-example",
                    },
                )
                assert imported["validation"]["valid"]
                await call("optimize_budget", {"model_id": fit["model_id"], "total_budget": total})
                audited = await call("audit_model", {"model_id": fit["model_id"]})
                assert audited["decomposition"]["maximum_reconciliation_error"] < 1e-8
                assert not audited["decision_support"]["business_recommendation_eligible"]
                await call(
                    "tune_mmm",
                    {
                        "dataset_id": demo["dataset_id"],
                        "decays": [0.2, 0.5, 0.8],
                        "multipliers": [0.5, 1.0, 2.0],
                    },
                )
                await call(
                    "calibrate_experiment",
                    {
                        "model_id": fit["model_id"],
                        "channel": "spend_search",
                        "treatment_spend": 1500.0,
                        "control_spend": 500.0,
                        "horizon": 4,
                        "lift_mean": 2000.0,
                        "lift_sd": 1000.0,
                        "experiment_id": "synthetic-lift",
                        "synthetic": True,
                    },
                )
                await call("render_dashboard", {"model_id": fit["model_id"]})
                await call("generate_report", {"model_id": fit["model_id"]})
            invalid = await session.call_tool(
                "simulate_budget",
                {
                    "request": {
                        "model_id": fit["model_id"],
                        "total_budget": 100,
                        "allocation": {"spend_search": 0.4},
                    }
                },
            )
            assert invalid.is_error
            missing = await session.call_tool("get_model", {"request": {"model_id": "absent"}})
            assert missing.structured_content["error"]["code"] == "NOT_FOUND"
            duplicate = await session.call_tool(
                "generate_demo_dataset", {"request": {"dataset_id": demo["dataset_id"]}}
            )
            assert duplicate.structured_content["error"]["code"] == "ALREADY_EXISTS"
            report["error_checks"] = {
                "invalid_input": "is_error=true",
                "missing": "NOT_FOUND",
                "overwrite": "ALREADY_EXISTS",
            }
        async with Client(params) as session:
            loaded = await session.call_tool(
                "get_model", {"request": {"model_id": fit["model_id"]}}
            )
            assert loaded.structured_content["data"] == model
            report["restart_persistence"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("var/demo"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--entrypoint", choices=["module", "script"], default="module")
    parser.add_argument("--extended", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = asyncio.run(cycle(args.data_dir, entrypoint=args.entrypoint, extended=args.extended))
    with (args.output_dir / "mcp-cycle.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
    from mmm_intelligence.config import Settings
    from mmm_intelligence.storage import ArtifactStore

    dataset_id = report["calls"]["generate_demo_dataset"]["data"]["dataset_id"]
    dataset = ArtifactStore(Settings(args.data_dir)).read("datasets", dataset_id)
    with (args.output_dir / "demo.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(dataset["rows"][0]))
        writer.writeheader()
        writer.writerows(dataset["rows"])
    for tool, filename in [
        ("render_dashboard", "dashboard.html"),
        ("generate_report", "report.md"),
    ]:
        if tool in report["calls"]:
            (args.output_dir / filename).write_text(
                report["calls"][tool]["data"]["content"], encoding="utf-8"
            )
    if "audit_model" in report["calls"]:
        (args.output_dir / "audit.json").write_text(
            json.dumps(
                report["calls"]["audit_model"]["data"],
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "tools": sorted(TOOLS),
                "calls": list(report["calls"]),
                "restart_persistence": report["restart_persistence"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
