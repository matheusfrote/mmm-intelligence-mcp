"""Repeated known-truth studies measure estimator performance, never campaign causality."""

import numpy as np
import pytest

from mmm_intelligence.schemas import MonteCarloProtocol
from mmm_intelligence.storage import digest


def test_dgp_is_reproducible_and_keeps_truth_out_of_model_columns():
    from mmm_intelligence.monte_carlo import generate_dgp

    config = MonteCarloProtocol(replications=2)
    data, truth = generate_dgp(config, 47, "well_specified")
    again, same_truth = generate_dgp(config, 47, "well_specified")
    assert digest(data) == digest(again)
    assert digest(truth) == digest(same_truth)
    assert not any("truth" in key or "latent" in key for key in data["rows"][0])
    assert all(value > 0 for value in truth["effect"].values())
    _, null = generate_dgp(config, 47, "null_effect")
    assert set(null["effect"].values()) == {0.0}


def test_monte_carlo_reports_truth_bias_rmse_coverage_and_complete_denominators():
    from mmm_intelligence.monte_carlo import run_study

    config = MonteCarloProtocol(
        replications=3,
        bootstrap_samples=20,
        scenarios=["well_specified", "null_effect", "collinear"],
    )
    report = run_study(config)
    assert report["causal_identification"] is False
    assert report["synthetic"] is True
    assert len(report["replications"]) == 9
    assert report["attempted"] == 9
    for summary in report["summaries"]:
        assert summary["attempted"] == 3
        assert summary["successful"] + summary["failed"] == 3
        assert summary["rmse"] >= abs(summary["bias"]) - 1e-10
        if summary["scenario"] == "collinear":
            assert summary["intervals_available"] == 0
            assert summary["interval_coverage"] is None
        else:
            assert 0 <= summary["interval_coverage"] <= 1
            assert summary["coverage_mcse"] >= 0
            assert len(summary["coverage_interval_95"]) == 2
    errors = np.array(
        [
            r["effects"]["spend_search"]["estimate"] - r["effects"]["spend_search"]["truth"]
            for r in report["replications"]
            if r["scenario"] == "well_specified"
        ]
    )
    summary = next(
        s
        for s in report["summaries"]
        if s["scenario"] == "well_specified" and s["channel"] == "spend_search"
    )
    assert np.isclose(summary["bias"], errors.mean())
    assert np.isclose(summary["rmse"], np.sqrt(np.mean(errors**2)))
    assert report["acceptance"]["status"] == "inconclusive"


def test_invalid_observations_and_unidentifiable_media_remain_in_attempted_denominator():
    from mmm_intelligence.monte_carlo import run_study

    config = MonteCarloProtocol(
        replications=2, bootstrap_samples=20, scenarios=["missing_target", "constant_spend"]
    )
    report = run_study(config)
    assert report["attempted"] == 4
    assert all(r["status"] == "failed" for r in report["replications"])
    assert {r["code"] for r in report["replications"]} == {
        "DATASET_INVALID",
        "UNIDENTIFIABLE_MEDIA",
    }
    assert all(s["interval_coverage"] is None and s["failed"] == 2 for s in report["summaries"])


def test_large_study_is_rejected_before_computing():
    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.monte_carlo import run_study

    with pytest.raises(MMMError, match="Split"):
        run_study(MonteCarloProtocol(replications=1000, bootstrap_samples=500))


def test_monte_carlo_acceptance_requires_explicit_tolerances_and_core_scenarios():
    from mmm_intelligence.monte_carlo import assess_study

    rows = [
        {
            "scenario": scenario,
            "channel": "media",
            "attempted": 1000,
            "successful": 1000,
            "intervals_available": 1000,
            "failed": 0,
            "interval_coverage": 1.0,
            "bias": 0.1,
            "rmse": 0.2,
        }
        for scenario in ["well_specified", "null_effect"]
    ]
    policy = MonteCarloProtocol(replications=1000, max_absolute_bias=1, max_rmse=1)
    assert assess_study({"summaries": rows}, policy)["status"] == "passed_for_studied_DGPs"
    assert assess_study({"summaries": rows}, MonteCarloProtocol())["status"] == "inconclusive"
    assert "core_scenarios_missing" in assess_study({"summaries": []}, policy)["missing"]
    rows[0].update(successful=0, intervals_available=0, failed=1000, interval_coverage=None)
    assert assess_study({"summaries": rows}, policy)["status"] == "failed"
    rows[0].update(successful=1000, intervals_available=1000, failed=0, interval_coverage=0.85)
    strict = MonteCarloProtocol(max_absolute_bias=0.01, max_rmse=0.01)
    report = assess_study({"summaries": rows}, strict)
    assert any("bias_exceeds" in r for r in report["failed"])
    assert any("rmse_exceeds" in r for r in report["failed"])
    assert any("coverage_precision" in r for r in report["missing"])


def test_interval_undercoverage_fails_despite_successful_point_estimation():
    from mmm_intelligence.monte_carlo import assess_study

    # Classifier fixture: known binomial counts, not a fabricated DGP execution.
    summary = {
        "summaries": [
            {
                "scenario": scenario,
                "channel": "media",
                "attempted": 100,
                "successful": 100,
                "intervals_available": 100,
                "failed": 0,
                "interval_coverage": 0.0,
                "bias": 0.1,
                "rmse": 0.2,
            }
            for scenario in ["well_specified", "null_effect"]
        ]
    }
    assessment = assess_study(summary, MonteCarloProtocol(replications=100))
    assert assessment["status"] == "failed"
    assert assessment["undercoverage"]
    assert assessment["causal_identification"] is False


@pytest.mark.parametrize("coverage, expected", [(1.0, "inconclusive"), (0.0, "failed")])
def test_partial_interval_availability_cannot_certify_monte_carlo(coverage, expected):
    from mmm_intelligence.monte_carlo import assess_study

    # Classifier counts only, never presented as executed native or synthetic fits.
    rows = [
        {
            "scenario": scenario,
            "channel": "media",
            "attempted": 1000,
            "successful": 1000,
            "failed": 0,
            "intervals_available": 500,
            "interval_coverage": coverage,
            "bias": 0.1,
            "rmse": 0.2,
        }
        for scenario in ["well_specified", "null_effect"]
    ]
    policy = MonteCarloProtocol(replications=1000, max_absolute_bias=1, max_rmse=1)
    result = assess_study({"summaries": rows}, policy)
    assert result["status"] == expected
    assert set(result["missing"]) == {
        "incomplete_interval_availability:well_specified:media",
        "incomplete_interval_availability:null_effect:media",
    }
    assert all(row["intervals_available"] == 500 for row in result["coverage_checks"])
    assert all(row["successful"] == 1000 for row in result["coverage_checks"])
    assert result["policy"]["require_intervals_for_all_successful_fits"] is True


def test_unknown_interval_denominator_does_not_assume_complete_availability():
    from mmm_intelligence.monte_carlo import assess_study

    rows = [
        {
            "scenario": scenario,
            "channel": "media",
            "successful": 1000,
            "failed": 0,
            "interval_coverage": 1.0,
            "bias": 0.1,
            "rmse": 0.2,
        }
        for scenario in ["well_specified", "null_effect"]
    ]
    policy = MonteCarloProtocol(replications=1000, max_absolute_bias=1, max_rmse=1)
    result = assess_study({"summaries": rows}, policy)
    assert result["status"] == "inconclusive"
    assert not result["coverage_checks"]
    assert any(
        reason.startswith("incomplete_interval_availability") for reason in result["missing"]
    )
