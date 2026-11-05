"""Immutable scientific refit ledger; cached fits are explicitly labelled reused."""

import hashlib
import os
from importlib.metadata import version
from pathlib import Path

from .errors import MMMError
from .storage import digest


def training_identity(backend, dataset, configuration):
    from .integrations.bridge import configured_r_library, executable

    package = Path(__file__).resolve().parent
    root = package.parents[1]
    names = (
        ["modeling.py", "inference.py"]
        if backend == "ridge"
        else ["integrations/worker.py", "integrations/native_scientific.py"]
    )
    metadata = {}
    if backend == "pymc_marketing":
        names.append("integrations/native_persistence.py")
    if backend == "meta_robyn":
        names = ["integrations/worker.py", "integrations/robyn_worker.R"]
        metadata.update(
            {
                str(
                    p.relative_to(root)
                    if p.is_relative_to(root)
                    else Path("R_library") / p.parent.name / p.name
                ): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in configured_r_library().glob("*/DESCRIPTION")
            }
        )
        rscript = Path(
            os.environ.get(
                "MMM_RSCRIPT", str(root / "var/runtime/r-portable/R-4.5.2/bin/Rscript.exe")
            )
        )
        if rscript.is_file():
            metadata["Rscript_executable"] = hashlib.sha256(rscript.read_bytes()).hexdigest()
    if backend != "ridge":
        runtime = executable(backend)
        if not runtime.is_file():
            raise MMMError("BACKEND_UNAVAILABLE", "Backend runtime is unavailable: " + backend)
        environment = (
            runtime.parent.parent
            if runtime.parent.name.lower() in {"scripts", "bin"}
            else runtime.parent
        )
        sites = [environment / "Lib/site-packages", *environment.glob("lib/python*/site-packages")]
        for site in sites:
            metadata.update(
                {
                    str(p.relative_to(environment)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in site.glob("*.dist-info/METADATA")
                }
            )
        if not metadata:
            raise MMMError(
                "RUNTIME_PROVENANCE",
                "Cannot verify native runtime package metadata for scientific reuse",
            )
    return {
        "backend": backend,
        "dataset_sha256": digest(dataset),
        "configuration": {k: v for k, v in configuration.items() if k != "model_id"},
        "source_sha256": {
            name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in names
        },
        "runtime_metadata_sha256": metadata,
        "host_numeric_versions": {p: version(p) for p in ("numpy", "scipy")},
    }


def fit_or_reuse(service, backend, dataset, configuration):
    from .datasets import require_native_media_variation, validate
    from .integrations.bridge import execute
    from .modeling import train
    from .schemas import BackendRequest, TrainRequest

    cls = TrainRequest if backend == "ridge" else BackendRequest
    spec = cls.model_validate(configuration)
    identity = training_identity(backend, dataset, spec.model_dump(mode="json"))
    model_id = "science-refit-" + digest(identity)[:40]
    kind = "models" if backend == "ridge" else "backend_models"
    if service.store.path(kind, model_id).is_file():
        fitted = service.store.read(kind, model_id)
        service.authorize(fitted)
        if fitted.get("scientific_training_identity") != identity:
            raise MMMError(
                "LINEAGE_MISMATCH", "Scientific refit identity differs from its immutable record"
            )
        return fitted, True
    spec = spec.model_copy(update={"model_id": model_id})
    if backend == "ridge":
        fitted = train(dataset, spec, model_id, validate(dataset, spec, service.settings.max_rows))
    else:
        quality = validate(dataset, spec, service.settings.max_rows)
        if not quality["valid"]:
            raise MMMError("DATASET_INVALID", "; ".join(quality["issues"]))
        require_native_media_variation(dataset, spec)
        fitted = execute(
            service.store,
            backend,
            {"operation": "train", "dataset": dataset, "request": spec.model_dump(mode="json")},
        )
        fitted.update(
            model_id=model_id,
            dataset_id=spec.dataset_id,
            dataset_sha256=digest(dataset),
            synthetic=dataset["synthetic"],
        )
    after = training_identity(backend, dataset, configuration)
    if digest(after) != digest(identity):
        # Reparse defaults before comparing: old requests may omit new optional fields.
        after = training_identity(
            backend, dataset, cls.model_validate(configuration).model_dump(mode="json")
        )
        if digest(after) != digest(identity):
            raise MMMError(
                "SOURCE_CHANGED",
                "Source/runtime changed during scientific refitting; result not reused",
            )
    fitted["scientific_training_identity"] = identity
    service.store.write(kind, model_id, fitted)
    return fitted, False
