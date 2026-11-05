"""Scientific reports cannot be transplanted across models, data or experiment scopes."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_causal_validation import calibration_case

from mmm_intelligence.causal_validation import (
    ASSUMPTIONS,
    calibrate_evidence,
    load_evidence,
    load_result,
)
from mmm_intelligence.errors import MMMError
from mmm_intelligence.schemas import ScientificProtocol


@pytest.mark.parametrize("field", ["model_id", "backend", "model_sha256", "dataset_sha256"])
def test_analysis_rejects_foreign_or_stale_validation_report(service, trained, field):
    report = service.call("audit_model", {"model_id": "fit", "scientific": {"refit": False}}).data
    if field in {"model_id", "backend"}:
        report[field] = "another"
    else:
        report["provenance"][field] = "0" * 64
    report = service._growth_save("scientific_validation", report)
    response = service.call(
        "get_analysis", {"model_id": "fit", "scientific_report_id": report["artifact_id"]}
    )
    assert response.error.code == "LINEAGE_MISMATCH"


def test_native_metadata_without_runtime_remains_inconclusive_and_rejects_wrong_engine(service):
    fixture = json.loads((Path(__file__).parent / "fixtures/dashboard-models.json").read_text())
    item = fixture["models"]["google_meridian"]
    model = {**item["model"], "dataset": item["dataset"]}
    service.store.write("backend_models", model["model_id"], model)
    report = service.call(
        "audit_model",
        {
            "model_id": model["model_id"],
            "backend": "google_meridian",
            "scientific": {"refit": False, "collect_native": False},
        },
    )
    assert report.ok, report.error
    assert report.data["classifications"]["statistical"]["status"] != "passed_for_protocol"
    bad = service.call(
        "audit_model",
        {
            "model_id": model["model_id"],
            "backend": "pymc_marketing",
            "scientific": {"refit": False},
        },
    )
    assert bad.error.code == "BACKEND_MISMATCH"
    legacy = service.call(
        "audit_model", {"model_id": model["model_id"], "backend": "google_meridian"}
    )
    assert legacy.error.code == "OPERATION_UNAVAILABLE"
    model["dataset_sha256"] = "0" * 64
    model["model_id"] = "bad-lineage"
    service.store.write("backend_models", "bad-lineage", model)
    bad = service.call(
        "audit_model",
        {
            "model_id": "bad-lineage",
            "backend": "google_meridian",
            "scientific": {"refit": False, "collect_native": False},
        },
    )
    assert bad.error.code == "LINEAGE_MISMATCH"


def test_experiment_lineage_kpi_and_origin_are_rechecked(service):
    experiment, _ = calibration_case(service)
    model = service.store.read("models", "boot")
    options = ScientificProtocol(experiment_result_ids=[experiment["artifact_id"]])
    review = load_evidence(service, model, options)
    assert review["status"] == "simulation_only"
    wrong = deepcopy(model)
    wrong["request"]["target_column"] = "another"
    with pytest.raises(MMMError, match="KPI"):
        load_evidence(service, wrong, options)
    with pytest.raises(MMMError, match="origin"):
        load_result(service, {**model, "synthetic": False}, experiment["artifact_id"])
    broken = deepcopy(experiment)
    source = next(iter(broken["source_hashes"]))
    broken["source_hashes"][source] = "0" * 64
    record = service._growth_save("experiment_result", broken)
    with pytest.raises(MMMError, match="source differs"):
        load_result(service, model, record["artifact_id"])


@pytest.mark.parametrize(
    "case,code",
    [
        ("native", "OPERATION_UNAVAILABLE"),
        ("units", "ESTIMAND_MISMATCH"),
        ("window", "ESTIMAND_MISMATCH"),
        ("missing_se", "EVIDENCE_INCOMPLETE"),
        ("nonrandom", "EXPERIMENT_QUALITY"),
        ("attrition", "EXPERIMENT_QUALITY"),
        ("srm_missing", "EXPERIMENT_QUALITY"),
        ("srm", "EXPERIMENT_QUALITY"),
    ],
)
def test_calibration_refuses_inadequate_evidence(service, case, code):
    evidence, calibration = calibration_case(service)
    model = service.store.read("models", "boot")
    backend = "meta_robyn" if case == "native" else "ridge"
    if case == "units":
        calibration["outcome_unit"] = "unknown"
    if case == "window":
        calibration["matching_measurement_window"] = False
    if case == "missing_se":
        evidence["estimate"].pop("standard_error")
    if case == "nonrandom":
        evidence["method"] = "before_after"
    if case == "attrition":
        evidence["losses"]["T"] = 1
    if case in {"srm", "srm_missing"}:
        evidence["sample_ratio_mismatch_pvalue"] = None if case == "srm_missing" else 0.0001
    record = service._growth_save("experiment_result", evidence)
    calibration["experiment_result_id"] = record["artifact_id"]
    with pytest.raises(MMMError) as error:
        calibrate_evidence(service, model, backend, ScientificProtocol(calibration=calibration))
    assert error.value.code == code


def test_authorized_mode_still_requires_design_review_and_never_authenticates_it(service):
    from dataclasses import replace

    # Fabricated records exercise the authorization-mode branch; no real data is used.
    evidence, calibration = calibration_case(service)
    model = service.store.read("models", "boot")
    model["synthetic"] = False
    evidence["synthetic"] = False
    service.settings = replace(service.settings, allow_real_data=True)
    record = service._growth_save("experiment_result", evidence)
    calibration["experiment_result_id"] = record["artifact_id"]
    for extra in ({}, {"review_reference": "Unit fixture, not an authenticated external review"}):
        with pytest.raises(MMMError) as error:
            calibrate_evidence(
                service, model, "ridge", ScientificProtocol(calibration=calibration, **extra)
            )
        assert error.value.code == "EVIDENCE_INCOMPLETE"
    approved_declarations = ScientificProtocol(
        calibration=calibration,
        assumptions={k: "supported" for k in ASSUMPTIONS},
        review_reference="Unit fixture declaration",
    )
    conditional = calibrate_evidence(service, model, "ridge", approved_declarations)
    assert conditional["design_assumptions_authenticated"] is False
    assert conditional["model_changed"] is False
