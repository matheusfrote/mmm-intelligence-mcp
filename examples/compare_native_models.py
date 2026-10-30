"""Compare existing synthetic native artifacts through MCP in a disposable store."""

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

from mmm_intelligence.config import Settings
from mmm_intelligence.storage import ArtifactStore


async def run(specs):
    with tempfile.TemporaryDirectory(prefix="mmm-compare-") as directory:
        store = ArtifactStore(Settings(Path(directory), max_file_bytes=52428800))
        references = []
        for backend, root, model_id in specs:
            source = ArtifactStore(Settings(Path(root), max_file_bytes=52428800))
            model = source.read("backend_models", model_id)
            if not model["synthetic"] or not model["dataset"]["synthetic"]:
                raise ValueError("This example accepts only synthetic artifacts")
            if model["backend"] != backend:
                raise ValueError("Backend mismatch")
            store.write("backend_models", model_id, model)
            references.append({"backend": backend, "model_id": model_id})
        store.write("datasets", "comparison", model["dataset"])
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mmm_intelligence.server"],
            env={
                **os.environ,
                "MMM_DATA_DIR": directory,
                "MMM_TRANSPORT": "stdio",
                "MMM_ALLOW_REAL_DATA": "false",
                "MMM_MAX_FILE_BYTES": "52428800",
            },
        )
        async with Client(params) as client:
            fit = await client.call_tool(
                "train_mmm", {"request": {"dataset_id": "comparison", "bootstrap_samples": 20}}
            )
            assert fit.structured_content["ok"], fit.structured_content
            references.append(
                {"backend": "ridge", "model_id": fit.structured_content["data"]["model_id"]}
            )
            exact = await client.call_tool("compare_models", {"request": {"models": references}})
            intersection = await client.call_tool(
                "compare_models",
                {"request": {"models": references, "window_policy": "intersection"}},
            )
            assert intersection.structured_content["ok"], intersection.structured_content
            return {
                "synthetic": True,
                "transport": "stdio",
                "native_models_retrained": False,
                "exact": exact.structured_content,
                "intersection": intersection.structured_content,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", nargs=3, action="append", required=True, metavar=("BACKEND", "ROOT", "ID")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= len(args.model) <= 4:
        parser.error(
            "Supply one to four native models; a Ridge model is fitted on the last dataset"
        )
    result = asyncio.run(run(args.model))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    data = result["intersection"]["data"]
    print(
        json.dumps(
            {
                "models": len(data["models"]),
                "periods": data["comparison_window"]["rows"],
                "exact_ok": result["exact"]["ok"],
                "winner": data["winner"],
            }
        )
    )


if __name__ == "__main__":
    main()
