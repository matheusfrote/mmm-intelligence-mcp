"""Scientific regression tests. All constructed records are explicitly synthetic."""

import copy

import numpy as np
import pytest

from mmm_intelligence.datasets import validate
from mmm_intelligence.modeling import metrics, train
from mmm_intelligence.optimization import optimize
from mmm_intelligence.schemas import CalibrationRequest, OptimizeRequest, TrainRequest


def test_metrics_rmse_and_mape_zero_denominators():
    out = metrics([0, 10, 20], [1, 12, 18])
    assert out["rmse"] == pytest.approx(np.sqrt(3))
    assert out["mape_nonzero_percent"] == pytest.approx(15)
    assert out["mape_excluded_zeros"] == 1
    assert metrics([0, 0], [1, 1])["mape_nonzero_percent"] is None


def test_collinear_model_retains_diagnostics_and_abstains(dataset):
    for row in dataset["rows"]:
        row["spend_social"] = row["spend_search"] * 2
    req = TrainRequest(dataset_id="synthetic", bootstrap_samples=20)
    model = train(dataset, req, "collinear", validate(dataset, req, 10000))
    out = optimize(model, OptimizeRequest(model_id="collinear", total_budget=60000.0))
    assert out["solver"]["success"]
    assert any("ILL_CONDITIONED" in w for w in out["warnings"])
    assert not out["decision_support"]["business_recommendation_eligible"]
    assert "RANK_DEFICIENT" in out["decision_support"]["reasons"]
    assert out["recommended_spend"] is None


def test_calibration_rejects_mixed_origins(service, trained):
    from mmm_intelligence.analysis import calibrate
    from mmm_intelligence.errors import MMMError

    request = CalibrationRequest(
        model_id="fit",
        channel="spend_search",
        treatment_spend=1000.0,
        control_spend=100.0,
        lift_mean=200.0,
        lift_sd=100.0,
        experiment_id="external",
        synthetic=False,
    )
    with pytest.raises(MMMError, match="origins"):
        calibrate(trained, request)


def test_scientific_audit_reconciles_and_backtests_over_mcp_service(service):
    assert service.call("generate_demo_dataset", {"dataset_id": "science"}).ok
    assert service.call(
        "train_mmm",
        {
            "dataset_id": "science",
            "model_id": "science",
            "bootstrap_samples": 20,
        },
    ).ok
    out = service.call("audit_model", {"model_id": "science", "folds": 3})
    assert out.ok, out.error
    d = out.data
    assert d["decomposition"]["maximum_reconciliation_error"] < 1e-8
    assert d["decomposition"]["roi"] is None
    assert len(d["backtest"]["folds"]) == 3
    assert all(f["train_end"] < f["test_start"] for f in d["backtest"]["folds"])
    assert len(d["sensitivity"]["specifications"]) >= 3
    assert d["insight"]["action"] and d["insight"]["validation"]
    assert d["source"]["dataset_sha256"]
    assert not d["decision_support"]["business_recommendation_eligible"]


def test_optimizer_compares_same_total_and_reports_marginal_units(trained):
    out = optimize(trained, OptimizeRequest(model_id="fit", total_budget=20000.0))
    c = out["comparison_same_total"]
    assert sum(c["reference_spend"].values()) == pytest.approx(20000)
    assert sum(out["optimal_spend"].values()) == pytest.approx(20000)
    assert set(out["marginal_kpi_per_spend"]) == set(out["optimal_spend"])
    assert "profit" not in out["solver"]["objective"]


def test_standardized_condition_is_invariant_to_control_units(dataset):
    req = TrainRequest(dataset_id="synthetic")
    a = train(dataset, req, "a", validate(dataset, req, 10000))
    other = copy.deepcopy(dataset)
    for row in other["rows"]:
        row["price_index"] *= 1000
    b = train(other, req, "b", validate(other, req, 10000))
    assert a["diagnostics"]["standardized_condition_number"] == pytest.approx(
        b["diagnostics"]["standardized_condition_number"], rel=1e-8
    )


def test_bootstrap_penalty_bias_is_visible(dataset):
    req = TrainRequest(dataset_id="synthetic", ridge_alpha=10000.0, bootstrap_samples=30)
    model = train(dataset, req, "biased", validate(dataset, req, 10000))
    assert model["uncertainty"]["coverage_certified"] is False
    assert any("BOOTSTRAP_SHRINKAGE" in w for w in model["warnings"])


def test_backtest_of_tuned_model_reselects_shapes_without_future_leakage(dataset):
    from mmm_intelligence.analysis import tune
    from mmm_intelligence.schemas import TuneRequest
    from mmm_intelligence.scientific import backtest

    req = TuneRequest(dataset_id="synthetic", decays=[0.2, 0.5, 0.8], multipliers=[0.5, 1.0, 2.0])
    original = tune(dataset, req, "original", 10000)
    altered = copy.deepcopy(dataset)
    for row in altered["rows"][92:124]:
        row["revenue"] *= 10
    later = tune(altered, req, "later", 10000)
    a = backtest(dataset, original, 3)["folds"][0]
    b = backtest(altered, later, 3)["folds"][0]
    assert a == b
    assert a["shape_policy"] == "nested_selection_within_fold"


def test_five_backtest_folds_use_feasible_proportions_with_sufficient_history():
    from mmm_intelligence.datasets import generate
    from mmm_intelligence.schemas import GenerateRequest
    from mmm_intelligence.scientific import backtest

    data = generate(GenerateRequest(periods=1000))
    req = TrainRequest(dataset_id="long-synthetic")
    model = train(data, req, "long", validate(data, req, 10000))
    result = backtest(data, model, 5)
    assert result["status"] == "executed" and len(result["folds"]) == 5
    for a, b in zip(result["folds"], result["folds"][1:]):
        assert a["test_end"] < b["test_start"]
