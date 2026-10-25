"""Verify actual optional engine train/get/predict over MCP stdio, without mocks."""

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def run(backend, data_dir, output, draws):
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mmm_intelligence.server"],
        cwd=root,
        env={
            **os.environ,
            "MMM_TRANSPORT": "stdio",
            "MMM_DATA_DIR": str(data_dir.absolute()),
            "MMM_ALLOW_REAL_DATA": "false",
        },
    )
    report = {"backend": backend, "transport": "stdio", "calls": {}}
    async with asyncio.timeout(1800):
        async with Client(params, read_timeout_seconds=1200) as client:

            async def call(name, request):
                result = await client.call_tool(name, {"request": request})
                value = result.structured_content
                report["calls"][name] = value
                (output / "result.json").write_text(
                    json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
                )
                assert not result.is_error and value["ok"], value
                return value["data"]

            dataset = await call("generate_demo_dataset", {"seed": 42, "periods": 156})
            model = await call(
                "train_backend",
                {
                    "dataset_id": dataset["dataset_id"],
                    "backend": backend,
                    "draws": draws,
                    "tune": draws,
                },
            )
            metadata = await call("get_backend_model", {"model_id": model["model_id"]})
            assert metadata["restore_verified"]
            prediction = await call("predict_backend", {"model_id": model["model_id"]})
            expected = metadata["test"]["mean"]
            actual = prediction["prediction"]["mean"]
            assert len(actual) == len(expected)
            assert all(
                math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5) for a, b in zip(actual, expected)
            )
            assert 1000 < sum(actual) / len(actual) < 100000, "Synthetic KPI scale mismatch"
            report["same_prediction_after_reload"] = True
            report["model_id"] = model["model_id"]
        async with Client(params, read_timeout_seconds=1200) as client:
            result = await client.call_tool(
                "predict_backend",
                {
                    "request": {
                        "model_id": model["model_id"],
                        "media_multiplier": {"spend_search": 1.1},
                    }
                },
            )
            report["calls"]["predict_backend_scenario"] = result.structured_content
            assert not result.is_error and result.structured_content["ok"], (
                result.structured_content
            )
            report["restart_scenario_verified"] = True
    (output / "result.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=["google_meridian", "pymc_marketing", "meta_robyn"], required=True
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=50)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = asyncio.run(run(args.backend, args.data_dir, args.output_dir, args.draws))
    print(json.dumps({k: v for k, v in result.items() if k != "calls"}, indent=2))


if __name__ == "__main__":
    main()
