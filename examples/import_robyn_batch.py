"""Verify and import a trusted local synthetic R batch into the immutable ledger.

Operator-only: no file import endpoint is exposed to MCP clients. The batch must
have been produced locally by robyn_offline_refit.py using the current runtime.
Native restoration is checked before making the result available for MCP reuse.
"""

import argparse
import base64
import json
import subprocess  # nosec B404
from pathlib import Path

import numpy as np

from mmm_intelligence.config import Settings
from mmm_intelligence.integrations.bridge import executable, execute, worker_environment
from mmm_intelligence.refits import training_identity
from mmm_intelligence.schemas import BackendRequest
from mmm_intelligence.service import MMMService
from mmm_intelligence.storage import digest, reject_links


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    options = parser.parse_args()
    folder = options.batch.resolve()
    for name in ("result.json", "input.json", "native-result.json", "model.robyn.json"):
        reject_links(folder / name)
    receipt = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    if receipt.get("operational") != "passed" or receipt.get("synthetic") is not True:
        raise ValueError("Only completed synthetic batches can be imported")
    payload = json.loads((folder / "input.json").read_text(encoding="utf-8"))
    native = json.loads((folder / "native-result.json").read_text(encoding="utf-8"))
    if digest(native) != receipt["native_result_sha256"] or native != receipt["result"]:
        raise ValueError("Native batch result differs from its receipt")
    dataset = payload["dataset"]
    request = BackendRequest.model_validate(payload["request"])
    if request.backend != "meta_robyn" or dataset.get("synthetic") is not True:
        raise ValueError("Only actual synthetic Robyn batches are supported")
    configuration = request.model_dump(mode="json")
    if configuration != receipt["configuration"]:
        raise ValueError("Native configuration differs from its receipt")
    identity = training_identity("meta_robyn", dataset, configuration)
    if identity != receipt["training_identity"]:
        raise ValueError("Batch source, dataset or runtime identity changed")
    model_id = "science-refit-" + digest(identity)[:40]
    request = request.model_copy(update={"model_id": model_id})
    # Fixed metadata query in the actual isolated runtime, never a client command.
    versions = subprocess.run(  # nosec B603
        [
            str(executable("meta_robyn")),
            "-I",
            "-c",
            "import json,importlib.metadata as m;print(json.dumps({n:m.version(n) for n in ('nevergrad','numpy','scipy')}))",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env=worker_environment(),
    )
    fitted = {
        **native,
        "backend": "meta_robyn",
        "model_id": model_id,
        "dataset_id": request.dataset_id,
        "dataset_sha256": digest(dataset),
        "dataset": dataset,
        "request": request.model_dump(mode="json"),
        "synthetic": True,
        "native_format": "robyn-json",
        "native_base64": base64.b64encode((folder / "model.robyn.json").read_bytes()).decode(),
        "native_runtime_versions": {
            **json.loads(versions.stdout),
            "R": native["r_version"],
            "Robyn": native["backend_version"],
        },
        "scientific_training_identity": identity,
        "operator_batch": {
            "receipt_sha256": digest(receipt),
            "timeout_seconds": receipt["timeout_seconds"],
            "transport": "local_native_r_batch",
        },
    }
    with MMMService(Settings(options.store, max_file_bytes=104857600)) as service:
        actual_dataset = service.load_dataset(request.dataset_id)
        if digest(actual_dataset) != digest(dataset):
            raise ValueError("Store dataset differs from batch lineage")
        restored = execute(
            service.store,
            "meta_robyn",
            {"operation": "predict", "model": fitted, "request": {"media_multiplier": {}}},
        )
        if restored["scope"] != "historical_restored_prediction" or not np.allclose(
            restored["prediction"]["mean"], fitted["test"]["mean"], rtol=1e-7, atol=1e-7
        ):
            raise ValueError("Native restoration changed the fitted predictions")
        path = service.store.path("backend_models", model_id)
        if path.is_file():
            if digest(service.store.read("backend_models", model_id)) != digest(fitted):
                raise ValueError("Immutable model already exists with different content")
            reused = True
        else:
            service.store.write("backend_models", model_id, fitted)
            reused = False
    print(
        json.dumps(
            {
                "model_id": model_id,
                "restoration_verified": True,
                "existing_model_reused": reused,
                "origin": "actual_local_native_r_batch",
                "causal_identification": False,
            }
        )
    )


if __name__ == "__main__":
    main()
