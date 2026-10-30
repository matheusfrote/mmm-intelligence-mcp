"""Synthetic files -> materialization -> real native train/reload through MCP."""

import argparse
import asyncio
import base64
import json
import math
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from mmm_intelligence.datasets import generate
from mmm_intelligence.schemas import GenerateRequest


async def run(root, backend, output, resume=False):
    output.mkdir(parents=True, exist_ok=resume)
    sample = generate(GenerateRequest(periods=104))["rows"]
    source_file = output / "synthetic-source.json"
    if not resume:
        source_file.write_text(json.dumps(sample), encoding="utf-8")
    env = {
        **os.environ,
        "MMM_DATA_DIR": str((output / "data").resolve()),
        "MMM_TRANSPORT": "stdio",
        "MMM_ALLOW_REAL_DATA": "false",
        "MMM_MAX_FILE_BYTES": "52428800",
        "MMM_BACKEND_TIMEOUT_SECONDS": "1800",
        "MMM_MERIDIAN_PYTHON": str(root / "var/envs/meridian/Scripts/python.exe"),
        "MMM_PYMC_PYTHON": str(root / "var/envs/pymc/Scripts/python.exe"),
        "MMM_ROBYN_PYTHON": str(root / "var/envs/robyn/Scripts/python.exe"),
        "MMM_RSCRIPT": str(root / "var/runtime/r-portable/R-4.5.2/bin/Rscript.exe"),
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mmm_intelligence.server"], cwd=root, env=env
    )
    record = {"backend": backend, "synthetic": True, "calls": [], "convergence_certified": False}
    async with Client(params, read_timeout_seconds=2000) as client:

        async def call(tool, **request):
            result = await client.call_tool(tool, {"request": request})
            assert not result.is_error and result.structured_content["ok"], (
                result.structured_content
            )
            record["calls"].append(tool)
            return result.structured_content["data"]

        if resume:
            inventory = await call("storage_inventory")
            models = [item for item in inventory["artifacts"] if item["kind"] == "backend_models"]
            assert len(models) == 1, "Resume requires exactly one persisted native model"
            trained = {"model_id": models[0]["artifact_id"]}
            existing = await call("get_backend_model", model_id=trained["model_id"])
            prepared = {"dataset_id": existing["dataset_id"], "sha256": existing["dataset_sha256"]}
        else:
            profile = await call(
                "register_media_profile",
                name="native_input",
                version="1",
                family="synthetic",
                required=list(sample[0]),
            )
            source = await call(
                "import_source",
                format="json",
                content_base64=base64.b64encode(source_file.read_bytes()).decode(),
                origin="fabricated native fixture",
                synthetic=True,
                confirm=True,
            )
            mapped = await call(
                "map_dataset_schema",
                source_id=source["artifact_id"],
                profile=profile["artifact_id"],
                mapping={c: c for c in sample[0]},
                units={
                    c: "BRL" if c.startswith("spend_") or c == "revenue" else "index"
                    for c in sample[0]
                    if c != "date"
                },
                dimensions={
                    "channel": "synthetic channels",
                    "strategy": "paid",
                    "kpi_definition": "synthetic revenue",
                },
            )
            prepared = await call(
                "prepare_mmm_dataset",
                artifact_id=mapped["artifact_id"],
                backend=backend,
                kpi="revenue",
                media=["spend_search", "spend_social", "spend_video"],
                controls=["price_index", "promotion"],
                target_type="revenue",
                currency="BRL",
            )
            training = {**prepared["training_request"], "draws": 20, "tune": 20}
            trained = await call("train_backend", **training)
        model_id = trained["model_id"]
        metadata = await call("get_backend_model", model_id=model_id)
        assert metadata["dataset_id"] == prepared["dataset_id"]
        assert metadata["dataset_sha256"] == prepared["sha256"]
        prediction = await call("predict_backend", model_id=model_id)
        assert all(
            math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)
            for a, b in zip(metadata["test"]["mean"], prediction["prediction"]["mean"])
        )
        record.update(
            model_id=model_id,
            dataset_id=prepared["dataset_id"],
            lineage_verified=True,
            metrics=metadata["test"]["metrics"],
            diagnostics=metadata.get("diagnostics", {}),
        )
    async with Client(params, read_timeout_seconds=2000) as restarted:
        result = await restarted.call_tool("predict_backend", {"request": {"model_id": model_id}})
        assert result.structured_content["ok"], result.structured_content
        assert (
            result.structured_content["data"]["prediction"]["mean"]
            == prediction["prediction"]["mean"]
        )
        scenario = await restarted.call_tool(
            "predict_backend",
            {"request": {"model_id": model_id, "media_multiplier": {"spend_search": 1.1}}},
        )
        assert scenario.structured_content["ok"], scenario.structured_content
        record["restart_scenario_verified"] = True
    (output / "result.json").write_text(
        json.dumps(record, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {"backend": backend, "lineage_verified": True, "restart_scenario_verified": True}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=["google_meridian", "pymc_marketing", "meta_robyn"], required=True
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        run(
            Path(__file__).resolve().parents[1],
            args.backend,
            args.output_dir.resolve(),
            args.resume,
        )
    )
