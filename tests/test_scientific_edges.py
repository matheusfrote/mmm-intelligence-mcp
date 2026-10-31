"""Failure, missing evidence and provenance boundaries for the scientific layer.

Dictionary fixtures below test classification rules, not sampler convergence or
real-world causal effects. Actual engine execution is tested separately.
"""

from copy import deepcopy

import numpy as np
import pytest

from mmm_intelligence.causal_validation import ASSUMPTIONS, review_evidence
from mmm_intelligence.schemas import AuditRequest, BackendRequest, ScientificProtocol
from mmm_intelligence.validation import classify_scientific, stability_study


def diagnostic_fixture(trained):
    model = deepcopy(trained)
    model["restore_verified"] = True
    model["diagnostics"] = {
        "chains": 4,
        "draws": 1000,
        "tune": 1000,
        "r_hat_max": 1.001,
        "ess_bulk_min": 900,
        "ess_tail_min": 800,
        "divergences": 0,
        "r_hat_undefined_count": 0,
        "ess_bulk_undefined_count": 0,
        "ess_tail_undefined_count": 0,
    }
    model["scientific_diagnostics"] = {
        "available": True,
        "mcse_sd_ratio_max": 0.02,
        "undefined_mcse_count": 0,
        "trace_series": [{"chains": [[0], [1]]}],
        "truncated": False,
    }
    model["posterior_predictive_check"] = {
        "available": True,
        "scope": "observed_outcome",
        "degenerate": False,
        "discrepancy_flags": [],
    }
    return model


@pytest.mark.parametrize(
    "change,missing,failed",
    [
        ({"mcse_sd_ratio_max": None}, "mcse_undefined", None),
        ({"mcse_sd_ratio_max": float("nan")}, "mcse_undefined", None),
        (
            {"undefined_mcse_count": 1, "mcse_sd_ratio_max": 0.2},
            "mcse_undefined",
            "mcse_exceeds_precision_policy",
        ),
        ({"trace_series": []}, "complete_chain_inspection", None),
        ({"truncated": True}, "complete_chain_inspection", None),
    ],
)
def test_incomplete_chains_never_approve(change, missing, failed, service, trained):
    model = diagnostic_fixture(trained)
    model["scientific_diagnostics"].update(change)
    review = classify_scientific(
        model,
        service.load_dataset("demo"),
        backend="pymc_marketing",
        stability={"status": "executed", "unstable": False, "estimate_consistency_available": True},
    )
    assert missing in review["statistical"]["missing"]
    assert review["statistical"]["status"] != "passed_for_protocol"
    if failed:
        assert failed in review["statistical"]["failed"]


def test_passing_numeric_screens_do_not_promote_causal_evidence(service, trained):
    model = diagnostic_fixture(trained)
    result = classify_scientific(
        model,
        service.load_dataset("demo"),
        backend="google_meridian",
        stability={"status": "executed", "unstable": False, "estimate_consistency_available": True},
    )
    assert result["statistical"]["status"] == "passed_for_protocol"
    assert result["causal"]["status"] == "simulation_only"
    assert not result["statistical"]["convergence_certified"]
    assert not result["business_recommendation_eligible"]
    model["posterior_predictive_check"]["degenerate"] = True
    failed = classify_scientific(
        model,
        service.load_dataset("demo"),
        backend="google_meridian",
        stability={"status": "executed", "unstable": True},
    )
    assert {"degenerate_predictive_distribution", "unstable_estimates"} <= set(
        failed["statistical"]["failed"]
    )


def test_rank_lineage_and_search_failures_remain_independent(service, trained):
    dataset = service.load_dataset("demo")
    model = deepcopy(trained)
    model["dataset_sha256"] = "0" * 64
    model["diagnostics"] = {}
    review = classify_scientific(model, dataset, backend="ridge")
    assert review["operational"]["status"] == "failed"
    assert "design_rank" in review["statistical"]["missing"]
    model["diagnostics"] = {"standardized_matrix_rank": 1, "feature_count": 2}
    review = classify_scientific(
        model, dataset, backend="ridge", stability={"status": "executed", "unstable": True}
    )
    assert {"rank_deficient", "unstable_estimates"} <= set(review["statistical"]["failed"])
    model["diagnostics"] = {
        "trials": 3,
        "iterations": 2000,
        "optimization_trace": [
            {"error_type": "NRMSE", "cuts": "2000", "flag_med": True, "flag_sd": True},
            {"error_type": "RSSD", "cuts": "2000", "flag_med": True, "flag_sd": True},
        ],
    }
    review = classify_scientific(
        model, dataset, backend="meta_robyn", stability={"status": "executed", "unstable": False}
    )
    assert "native_effect_parameter_stability" in review["statistical"]["missing"]


def test_real_failed_refits_are_retained_instead_of_dropping_them(
    service, trained, monkeypatch, tmp_path
):
    dataset = deepcopy(service.load_dataset("demo"))
    for row in dataset["rows"]:
        row["spend_search"] = 100.0
    result = stability_study(service, trained, dataset, "ridge", ScientificProtocol())
    assert result["status"] == "incomplete"
    assert not result["runs"]
    assert {r["code"] for r in result["failures"]} == {"UNIDENTIFIABLE_MEDIA"}
    monkeypatch.setenv("MMM_ROBYN_PYTHON", str(tmp_path / "absent.exe"))
    model = {
        **trained,
        "request": BackendRequest(dataset_id="demo", backend="meta_robyn").model_dump(),
    }
    result = stability_study(service, model, dataset, "meta_robyn", ScientificProtocol())
    assert {r["code"] for r in result["failures"]} == {"BACKEND_UNAVAILABLE"}


def test_invalid_protocol_duplicates_and_foreign_engine_controls_are_rejected():
    for scientific in (
        {"seeds": [1, 1]},
        {"regularization": [0.1, 0.1]},
        {"experiment_result_ids": ["same"], "placebo_result_ids": ["same"]},
    ):
        with pytest.raises(ValueError):
            AuditRequest(model_id="model", scientific=scientific)
    with pytest.raises(ValueError):
        BackendRequest(dataset_id="data", backend="google_meridian", robyn_trials=2)


def test_actual_experiment_screens_distinguish_inconclusive_and_contradicted():
    from test_causal_validation import result

    primary, placebo = result(), result(null=True)
    for study in (primary, placebo):
        study["synthetic"] = False  # Unit classification fixtures; no real data used.
        study["guardrails"] = {}
    options = ScientificProtocol(
        assumptions={k: "supported" for k in ASSUMPTIONS},
        review_reference="Unit-test declaration, not an authenticated review",
        equivalence_margin=0.5,
        confounding_bias_grid=[-0.1, 0.0, 0.1],
    )
    review = review_evidence([primary], [placebo], [placebo], options, synthetic=False)
    assert review["status"] == "experimental_support_pending_external_review"
    assert review["causal_identification"] is False
    assert (
        review["confounding_sensitivity"][0]["bias_grid"][1]["adjusted_estimate"]
        == primary["estimate"]["difference"]
    )
    primary.update(
        method="before_after",
        population_verified=False,
        measurement_window_verified=False,
        guardrails={"cost": {"status": "harm_detected"}, "other": {"status": "inconclusive"}},
    )
    primary["estimate"]["interval"] = [-1.0, 1.0]
    review = review_evidence(
        [primary], [result()], [], ScientificProtocol(equivalence_margin=0.001), synthetic=False
    )
    assert (
        review["status"] == "simulation_only"
    )  # A synthetic falsification cannot certify a real result.
    assert "falsification_contradiction" in review["threats"]
    assert {
        "randomization_design_not_verified",
        "population_or_measurement_window",
        "effect_direction_inconclusive",
        "guardrail_evidence",
    } <= set(review["missing"])


def test_nonfinite_and_malformed_posterior_arrays_are_refused():
    from mmm_intelligence.integrations.native_scientific import chain_report, parameter_means

    with pytest.raises(ValueError):
        chain_report([], {"beta": np.ones((1, 10))})
    with pytest.raises(ValueError):
        parameter_means({"beta": np.full((4, 10), np.nan)})


def test_search_budget_threshold_is_independent_of_numeric_trace_flags(service, trained):
    model = deepcopy(trained)
    model["diagnostics"] = {
        "trials": 5,
        "iterations": 2000,
        "optimization_trace": [
            {"error_type": "NRMSE", "cuts": 2000, "flag_med": True, "flag_sd": True}
        ],
    }
    result = classify_scientific(
        model,
        service.load_dataset("demo"),
        backend="meta_robyn",
        stability={"status": "executed", "unstable": False, "estimate_consistency_available": True},
    )
    assert "prespecified_search_budget" not in result["statistical"]["missing"]
    assert result["statistical"]["status"] == "passed_for_protocol"
    assert result["causal"]["status"] == "simulation_only"


def test_actual_ridge_regularization_without_controls_remains_reproducible(service, trained):
    fitted = service.call(
        "train_mmm", {"dataset_id": "demo", "model_id": "no-controls", "control_columns": []}
    )
    assert fitted.ok, fitted.error
    result = stability_study(
        service,
        service.store.read("models", "no-controls"),
        service.load_dataset("demo"),
        "ridge",
        ScientificProtocol(),
    )
    assert len(result["runs"]) == 3
    assert result["status"] == "executed"
    assert all(r["configuration"]["control_columns"] == [] for r in result["runs"])
