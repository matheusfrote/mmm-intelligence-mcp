"""Experiment-based evidence uses actual estimators and cannot authenticate assignment."""

from copy import deepcopy

from test_experiment_protocol import fixture_rows, protocol

from mmm_intelligence.experiments import analyze_experiment, plan_experiment
from mmm_intelligence.schemas import ScientificProtocol


def result(null=False):
    rows = fixture_rows()
    if null:
        for row in rows:
            row["conversion"] = int(int(row["unit"]) % 10 < 2)
    plan = {**plan_experiment(protocol()), "artifact_id": "plan"}
    artifact = {"artifact_id": "source", "rows": rows, "synthetic": True}
    return analyze_experiment(artifact, plan)


def test_non_significant_placebo_is_not_equivalence_or_no_confounding():
    from mmm_intelligence.causal_validation import review_evidence

    study = result()
    null = result(null=True)
    review = review_evidence(
        [study], [null], [null], ScientificProtocol(equivalence_margin=0.01), synthetic=False
    )
    assert review["status"] != "supported_under_declared_assumptions"
    assert review["placebos"][0]["status"] == "inconclusive"
    assert review["no_unmeasured_confounding_verified"] is False
    assert review["causal_identification"] is False


def test_failed_assumptions_dominate_but_synthetic_origin_never_certifies():
    from mmm_intelligence.causal_validation import review_evidence

    study = result()
    options = ScientificProtocol(assumptions={"no_interference": "violated"})
    study["synthetic"] = False  # Unit fixture for origin classification, not actual business data.
    review = review_evidence([study], [], [], options, synthetic=False)
    assert review["status"] == "contradicted"
    synthetic = review_evidence([study], [], [], options, synthetic=True)
    assert synthetic["status"] == "simulation_only"
    assert "no_interference" in synthetic["violated_assumptions"]


def test_srm_and_attrition_cannot_be_overridden_by_declared_randomization():
    from mmm_intelligence.causal_validation import review_evidence

    study = deepcopy(result())
    study["synthetic"] = False
    study["sample_ratio_mismatch_pvalue"] = 0.0001
    study["losses"] = {"T": 20, "C": 0}
    review = review_evidence([study], [], [], ScientificProtocol(), synthetic=False)
    assert review["status"] == "contradicted"
    assert "sample_ratio_mismatch" in review["threats"]
    assert "missing_outcomes" in review["threats"]


def calibration_case(service):
    rows = fixture_rows()
    for row in rows:
        row["revenue"] = float(row["conversion"] * 1000)
    source = service._growth_save("source", {"synthetic": True, "rows": rows})
    planned = protocol(
        kpi="revenue",
        outcome_type="continuous",
        baseline=200,
        minimum_effect=100,
        standard_deviation=450,
        cost_column=None,
    )
    plan = service.call("plan_experiment", planned.model_dump(mode="json"))
    assert plan.ok
    experimental = service.call(
        "analyze_experiment",
        {"artifact_id": source["artifact_id"], "plan_id": plan.data["artifact_id"]},
    )
    assert experimental.ok
    assert experimental.data["estimate"]["standard_error"] > 0
    assert service.call("generate_demo_dataset", {"dataset_id": "demo"}).ok
    assert service.call(
        "train_mmm", {"dataset_id": "demo", "model_id": "boot", "bootstrap_samples": 20}
    ).ok
    calibration = {
        "experiment_result_id": experimental.data["artifact_id"],
        "channel": "spend_search",
        "treatment_spend": 1500.0,
        "control_spend": 1000.0,
        "horizon": 4,
        "aggregate_multiplier": 1.0,
        "outcome_unit": "synthetic_revenue",
        "transformation_justification": "Synthetic scope transformation for a software test",
        "matching_population": True,
        "matching_measurement_window": True,
    }
    return experimental.data, calibration


def test_calibration_uses_persisted_experiment_uncertainty_and_disjoint_validation(service):
    experimental, calibration = calibration_case(service)
    report = service.call(
        "audit_model",
        {"model_id": "boot", "scientific": {"refit": False, "calibration": calibration}},
    )
    assert report.ok, report.error
    assert report.data["calibration"]["observed_lift"] == experimental["estimate"]["difference"]
    assert report.data["classifications"]["causal"]["status"] == "simulation_only"
    assert report.data["calibration"]["model_changed"] is False
    duplicate = service.call(
        "audit_model",
        {
            "model_id": "boot",
            "scientific": {
                "refit": False,
                "calibration": calibration,
                "experiment_result_ids": [experimental["artifact_id"]],
            },
        },
    )
    assert not duplicate.ok


def test_excessive_calibration_scope_is_input_failure_not_internal_error(service):
    _, calibration = calibration_case(service)
    calibration["aggregate_multiplier"] = 1e9
    result = service.call(
        "audit_model",
        {"model_id": "boot", "scientific": {"refit": False, "calibration": calibration}},
    )
    assert not result.ok
    assert result.error.code == "CALIBRATION_NUMERIC_RANGE"
