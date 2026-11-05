"""Confidence sets for conditional linear effects, including the sign boundary."""

import numpy as np


def test_training_retains_unpenalized_covariance_separate_from_bootstrap(trained):
    assert "linear_inference" in trained
    inference = trained["linear_inference"]
    assert inference["available"]
    assert inference["point_estimator"] == "unpenalized_OLS"
    assert not inference["causal_identification"]


def test_simulation_exposes_separate_ols_contrast_without_relabelling_ridge(service, trained):
    from mmm_intelligence.schemas import SimulateRequest
    from mmm_intelligence.simulation import simulate

    result = simulate(
        trained,
        SimulateRequest(
            model_id="fit",
            total_budget=90000,
            allocation={c: 1 / 3 for c in trained["request"]["media_columns"]},
        ),
    )
    methods = result["conditional_linear_confidence"]["methods"]
    assert methods["hc3"]["available"]
    assert methods["hc3"]["method"] == "OLS_hc3"
    assert methods["hc3"]["lower"] <= methods["hc3"]["estimate"] <= methods["hc3"]["upper"]


def test_legacy_model_simulation_does_not_invent_new_inference(trained):
    from mmm_intelligence.schemas import SimulateRequest
    from mmm_intelligence.simulation import simulate

    legacy = {key: value for key, value in trained.items() if key != "linear_inference"}
    result = simulate(
        legacy,
        SimulateRequest(
            model_id="fit",
            total_budget=90000,
            allocation={c: 1 / 3 for c in trained["request"]["media_columns"]},
        ),
    )
    assert "conditional_linear_confidence" not in result
    assert np.isfinite(result["predicted_total"])


def test_projected_null_intervals_do_not_inherit_positive_bootstrap_boundary():
    from mmm_intelligence.inference import fit_linear_inference, linear_contrast

    rng = np.random.default_rng(731)
    x = np.column_stack([np.ones(120), rng.normal(size=(120, 2))])
    covered = 0
    for _ in range(100):
        y = 5 + rng.normal(size=120)
        fitted = fit_linear_inference(x, y)
        interval = linear_contrast(fitted, [0, 1, 0], nonnegative=True)
        assert interval["lower"] >= 0
        covered += interval["lower"] <= 0 <= interval["upper"]
    assert 88 <= covered <= 100


def test_rank_deficiency_refuses_a_confidence_set_instead_of_pseudoinverse_certainty():
    from mmm_intelligence.inference import fit_linear_inference

    x = np.column_stack([np.ones(60), np.arange(60), np.arange(60)])
    result = fit_linear_inference(x, np.arange(60))
    assert not result["available"]
    assert result["reason"] == "rank_deficient"


def test_actual_dgp_compares_projected_and_legacy_intervals_on_identical_repetitions():
    from mmm_intelligence.monte_carlo import run_study
    from mmm_intelligence.schemas import MonteCarloProtocol

    study = run_study(MonteCarloProtocol(replications=30, scenarios=["null_effect"], seed=734))
    row = next(r for r in study["summaries"] if r["channel"] == "spend_search")
    assert row["interval_method"] == "projected_hc3"
    assert row["interval_coverage"] >= 0.8
    comparisons = {r["interval_method"]: r for r in study["method_comparisons"]}
    assert comparisons["legacy_percentile"]["interval_coverage"] < 0.2


def test_legacy_benchmark_records_its_own_inadequacy_instead_of_upgrading_draws(service, trained):
    result = service.call(
        "audit_model",
        {
            "model_id": "fit",
            "scientific": {
                "refit": False,
                "monte_carlo": {"replications": 2, "interval_method": "legacy_percentile"},
            },
        },
    )
    assert result.ok, result.error
    assessment = result.data["classifications"]["statistical"]
    assert assessment["uncertainty_validation_scope"] == "legacy_percentile"
    assert assessment["status"] != "passed_for_protocol"


def test_projected_benchmark_does_not_validate_legacy_bootstrap_draws(service, trained):
    assert service.call(
        "train_mmm", {"dataset_id": "demo", "model_id": "legacy-draws", "bootstrap_samples": 20}
    ).ok
    result = service.call(
        "audit_model",
        {
            "model_id": "legacy-draws",
            "scientific": {"refit": False, "monte_carlo": {"replications": 2}},
        },
    )
    assert result.ok, result.error
    assert (
        "conditional_interval_validation_unavailable"
        in result.data["classifications"]["statistical"]["missing"]
    )
