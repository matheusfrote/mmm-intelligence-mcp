"""Read/reload an existing synthetic native model; verify canonical and future operations."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def check(backend, model_id, data_dir):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mmm_intelligence.server"],
        env={
            **os.environ,
            "MMM_DATA_DIR": str(data_dir.absolute()),
            "MMM_TRANSPORT": "stdio",
            "MMM_ALLOW_REAL_DATA": "false",
            "MMM_MAX_FILE_BYTES": "52428800",
        },
    )
    record = {"backend": backend, "fresh_training": False, "transport": "stdio", "synthetic": True}
    async with Client(params, read_timeout_seconds=1200) as client:

        async def call(name, req):
            out = await client.call_tool(name, {"request": req})
            assert not out.is_error and out.structured_content["ok"], out.structured_content
            return out.structured_content["data"]

        analysis = await call("get_analysis", {"backend": backend, "model_id": model_id})
        assert analysis["source"]["synthetic"]
        restored = await call("predict_backend", {"model_id": model_id})
        import numpy as np

        np.testing.assert_allclose(
            restored["prediction"]["mean"],
            [p["predicted"] for p in analysis["evaluation"]],
            rtol=1e-5,
            atol=1e-5,
        )
        record.update(
            canonical_metrics=analysis["metrics"],
            diagnostic_assessment=analysis["diagnostic_assessment"],
            reload_matches=True,
            capabilities=analysis["capabilities"],
        )
        if backend == "pymc_marketing":
            req = analysis["request"]
            from mmm_intelligence.config import Settings
            from mmm_intelligence.storage import ArtifactStore

            model = ArtifactStore(Settings(data_dir, max_file_bytes=52428800)).read(
                "backend_models", model_id
            )
            last = model["dataset"]["rows"][-1]
            future = {
                "backend": backend,
                "model_id": model_id,
                "media_plan": {c: [1000.0, 1100.0, 900.0, 1000.0] for c in req["media_columns"]},
                "future_controls": {c: [last[c]] * 4 for c in req["control_columns"]},
            }
            forecast = await call("forecast_model", future)
            assert forecast["prediction"]["dates"][0] > last[req["date_column"]]
            assert len(forecast["prediction"]["mean"]) == 4
            assert np.isfinite(forecast["prediction"]["mean"]).all()
            assert forecast["prediction"]["interval_type"] == "posterior_predictive_observed"
            record["forecast"] = forecast
    if backend == "pymc_marketing":
        async with Client(params, read_timeout_seconds=1200) as client:
            out = await client.call_tool("forecast_model", {"request": future})
            assert not out.is_error and out.structured_content["ok"], out.structured_content
            np.testing.assert_allclose(
                out.structured_content["data"]["prediction"]["mean"],
                record["forecast"]["prediction"]["mean"],
                rtol=1e-7,
                atol=1e-7,
            )
            record["future_restart_reproducible"] = True
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", required=True, choices=["pymc_marketing", "google_meridian", "meta_robyn"]
    )
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(check(args.backend, args.model_id, args.data_dir))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(
        json.dumps(
            {
                "backend": args.backend,
                "reload_matches": True,
                "future_restart_reproducible": result.get("future_restart_reproducible"),
            }
        )
    )


if __name__ == "__main__":
    main()
