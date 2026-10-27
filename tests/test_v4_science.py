import numpy as np
import pytest

from mmm_intelligence.datasets import validate
from mmm_intelligence.modeling import metrics, train
from mmm_intelligence.schemas import TrainRequest


def test_bias_and_undefined_metrics_are_explicit():
    out = metrics([0, 0], [1, 3])
    assert out["bias_predicted_minus_observed"] == 2
    assert out["wape_percent"] is None
    assert out["r2"] is None
    assert out["mape_nonzero_percent"] is None


def test_bayesian_classification_never_certifies_decisions():
    from mmm_intelligence.diagnostics import classify_bayesian

    good = dict(
        chains=4,
        draws=1000,
        tune=1000,
        r_hat_max=1.001,
        ess_bulk_min=600,
        ess_tail_min=500,
        divergences=0,
        r_hat_undefined_count=0,
        ess_bulk_undefined_count=0,
        ess_tail_undefined_count=0,
    )
    assert classify_bayesian(good)["status"] == "adequate_for_screened_diagnostics"
    assert not classify_bayesian(good)["business_recommendation_eligible"]
    assert classify_bayesian({**good, "r_hat_max": 1.02})["status"] == "inadequate"
    assert classify_bayesian({**good, "divergences": 1})["status"] == "inadequate"
    assert classify_bayesian({**good, "ess_tail_min": None})["status"] == "inconclusive"
    assert classify_bayesian({**good, "r_hat_undefined_count": 1})["status"] == "inconclusive"
    assert classify_bayesian({})["status"] == "inconclusive"
    assert classify_bayesian({"estimation_failed": True})["status"] == "not_estimable"


def test_interval_coverage_measures_the_declared_estimand():
    from mmm_intelligence.diagnostics import interval_coverage

    out = interval_coverage([1, 2, 10], [0, 1, 3], [2, 3, 5], "conditional_mean")
    assert out["empirical_coverage"] == pytest.approx(2 / 3)
    assert out["estimand"] == "conditional_mean"
    assert not out["coverage_certified"]
    with pytest.raises(ValueError):
        interval_coverage([1], [2], [0], "conditional_mean")


@pytest.mark.parametrize("seed", [3, 19, 44])
def test_identified_known_shapes_recover_positive_and_null_effects(seed):
    from mmm_intelligence.synthetic import controlled_dataset

    dataset, truth = controlled_dataset(seed=seed, noise_sd=2)
    req = TrainRequest(dataset_id="known", ridge_alpha=1e-5)
    model = train(dataset, req, "known-model", validate(dataset, req, 10000))
    for channel, coefficient in truth["media_coefficients"].items():
        assert abs(model["coefficients"][channel] - coefficient) < 15
    assert model["coefficients"]["price_index"] < 0
    assert (
        np.max(
            np.abs(
                np.array([p["predicted"] for p in model["predictions"]])
                - np.array(truth["conditional_mean"])[8:]
            )
        )
        < 5
    )


def test_synthetic_collinearity_is_detected_and_origins_are_explicit():
    from mmm_intelligence.scientific import decision_support
    from mmm_intelligence.synthetic import controlled_dataset

    data, truth = controlled_dataset(collinear=True)
    req = TrainRequest(dataset_id="known")
    model = train(data, req, "fit", validate(data, req, 10000))
    assert data["synthetic"] and truth["known_dgp"]
    assert "RANK_DEFICIENT" in decision_support(model)["reasons"]


def test_bootstrap_warns_about_constrained_null_boundary(dataset):
    req = TrainRequest(dataset_id="known", bootstrap_samples=20)
    model = train(dataset, req, "fit", validate(dataset, req, 10000))
    assert "null" in model["uncertainty"]["boundary_note"]
    assert not model["uncertainty"]["supports_null_effect_testing"]
