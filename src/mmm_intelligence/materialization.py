"""Produce validated immutable inputs actually consumed by existing backend adapters."""

from .datasets import validate
from .errors import MMMError
from .media_validation import eligibility
from .schemas import BackendRequest, TrainRequest
from .storage import digest


def materialize(artifact, request, max_rows):
    if artifact["frequency_days"] not in {1, 7}:
        raise MMMError("ENGINE_FREQUENCY", "Current adapters require daily or weekly regular data")
    if any(artifact["units"].get(c) != request.currency for c in request.media):
        raise MMMError(
            "MEDIA_UNIT",
            "Current adapters and budget operations require media spend in the declared common currency; exposure is not spend",
        )
    if request.target_type == "revenue" and artifact["units"].get(request.kpi) != request.currency:
        raise MMMError("KPI_UNIT", "Revenue outcome must use the declared spend currency")
    eligibility_report = eligibility(artifact, request)
    if not eligibility_report["eligible"]:
        raise MMMError("MMM_INELIGIBLE", "; ".join(eligibility_report["blocking_reasons"]))
    specification = {
        "dataset_id": "preparation-check",
        "date_column": "date",
        "target_column": request.kpi,
        "media_columns": request.media,
        "control_columns": request.controls,
        "test_fraction": 0.2,
    }
    if request.backend != "ridge":
        specification["backend"] = request.backend
    training = (
        (TrainRequest if request.backend == "ridge" else BackendRequest)
        .model_validate(specification)
        .model_dump(mode="json")
    )
    selected = ["date", request.kpi, *request.media, *request.controls]
    payload = {
        "schema_version": 1,
        "synthetic": artifact["synthetic"],
        "rows": [{c: r[c] for c in selected} for r in artifact["rows"]],
        "source": "explicit-normalized-materialization",
        "source_ids": [artifact["artifact_id"]],
        "source_hashes": [digest(artifact)],
        "target_type": request.target_type,
        "frequency": "weekly" if artifact["frequency_days"] == 7 else "daily",
        "units": {c: artifact["units"][c] for c in selected if c != "date"},
        "column_spec": {
            k: training[k]
            for k in ["date_column", "target_column", "media_columns", "control_columns"]
        },
        "authorization_reference": artifact.get(
            "authorization_reference", "inherited-authorized-lineage"
        ),
        "data_context": {
            "kpi_definition": artifact["dimensions"]["kpi_definition"],
            "currency": request.currency,
            "timezone": artifact["timezone"],
        },
        "preparation": {
            "version": "1",
            "backend": request.backend,
            "eligibility": eligibility_report,
            "warnings": [
                "No causal identification or convergence guarantee.",
                "Native adapters use spend as the media exposure proxy; independent exposure and geo inputs are not invented.",
            ],
        },
    }
    report = validate(
        payload,
        (TrainRequest if request.backend == "ridge" else BackendRequest).model_validate(training),
        max_rows,
    )
    if not report["valid"]:
        raise MMMError("DATASET_INVALID", "; ".join(report["issues"]))
    return payload, training
