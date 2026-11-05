"""Bounded operator-only R batch for extensive synthetic Robyn refits.

This is not an MCP endpoint. Its explicit two-hour ceiling does not change the
one-hour MCP worker limit, statistical criteria, search budget or engine code.
"""

import argparse
import json
import os
import tempfile
from pathlib import Path

from mmm_intelligence.config import Settings
from mmm_intelligence.integrations.bridge import (
    configured_r_library,
    executable,
    worker_environment,
)
from mmm_intelligence.refits import training_identity
from mmm_intelligence.resources import run_worker
from mmm_intelligence.schemas import BackendRequest
from mmm_intelligence.storage import ArtifactStore, digest
from mmm_intelligence.validation import search_assessment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--omit-first-control", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, choices=[3600, 7200], default=7200)
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    store = ArtifactStore(Settings(options.store, max_file_bytes=104857600))
    reference = store.read("backend_models", options.model_id)
    dataset = store.read("datasets", reference["dataset_id"])
    if dataset.get("synthetic") is not True:
        raise ValueError("Only synthetic data are authorized for this example")
    if digest(dataset) != reference["dataset_sha256"]:
        raise ValueError("Reference dataset lineage mismatch")
    request = BackendRequest.model_validate({**reference["request"], "seed": options.seed})
    if options.omit_first_control:
        request = request.model_copy(update={"control_columns": request.control_columns[1:]})
    if request.backend != "meta_robyn" or request.robyn_algorithm != "DE":
        raise ValueError("Use a predeclared native DE reference model")
    if (
        request.robyn_trials is None
        or request.robyn_trials < 5
        or request.robyn_iterations is None
        or request.robyn_iterations < 2000
    ):
        raise ValueError(
            "Declare at least five trials and 2000 iterations in the reference profile"
        )
    root = options.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = (
        Path(__file__).resolve().parents[1] / "src/mmm_intelligence/integrations/robyn_worker.R"
    )
    rscript = Path(
        os.environ.get(
            "MMM_RSCRIPT", str(source.parents[3] / "var/runtime/r-portable/R-4.5.2/bin/Rscript.exe")
        )
    )
    if not rscript.is_file():
        raise ValueError("Configure the actual Rscript runtime")
    configuration = request.model_dump(mode="json")
    identity = training_identity("meta_robyn", dataset, configuration)
    receipt = {
        "scope": "Actual operator-only native R batch; no MCMC or causal certification",
        "configuration": configuration,
        "training_identity": identity,
        "reference_model_sha256": digest(reference),
        "timeout_seconds": options.timeout_seconds,
        "synthetic": True,
        "causal_identification": False,
    }
    input_path = root / "input.json"
    output_path = root / "native-result.json"
    input_path.write_text(
        json.dumps(
            {"operation": "train", "dataset": dataset, "request": configuration}, allow_nan=False
        ),
        encoding="utf-8",
    )
    try:
        with tempfile.TemporaryDirectory(prefix="mmm-r-offline-") as temporary:
            if " " in temporary:
                raise ValueError("R requires an OS temporary directory without spaces")
            environment = {
                **worker_environment(),
                "RETICULATE_PYTHON": str(executable("meta_robyn")),
                "RETICULATE_AUTOCONFIGURE": "FALSE",
                "R_LIBS_USER": str(configured_r_library()),
                "R_USER": temporary,
                "TMP": temporary,
                "TEMP": temporary,
                "TMPDIR": temporary,
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
            }
            with (root / "worker.log").open("xb") as log:
                process = run_worker(
                    [str(rscript), "--vanilla", str(source), str(input_path), str(output_path)],
                    timeout=options.timeout_seconds,
                    env=environment,
                    cwd=root,
                    stdout=log,
                )
        if process.returncode != 0:
            raise RuntimeError("Native R batch failed; inspect the private worker log")
        if identity != training_identity("meta_robyn", dataset, configuration):
            raise RuntimeError("Training source/runtime changed during the batch")
        result = json.loads(output_path.read_text(encoding="utf-8"))
        receipt.update(
            operational="passed",
            result=result,
            numerical_assessment=search_assessment(result),
            native_result_sha256=digest(result),
        )
    except Exception as error:
        receipt.update(operational="failed", error_type=type(error).__name__)
        raise
    finally:
        (root / "result.json").write_text(
            json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "operational": receipt["operational"],
                "numerical_assessment": receipt["numerical_assessment"],
            }
        )
    )


if __name__ == "__main__":
    main()
