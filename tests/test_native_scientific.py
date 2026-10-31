"""Check real numerical diagnostics without pretending to sample a native model."""

import numpy as np
import pytest


def test_chain_collection_keeps_parameter_mcse_and_independent_traces():
    from mmm_intelligence.integrations.native_scientific import chain_report

    rng = np.random.default_rng(41)
    values = rng.normal(size=(4, 1000))
    result = chain_report(
        [
            {
                "parameter": "beta",
                "mean": 0.0,
                "sd": 1.0,
                "mcse_mean": 0.02,
                "r_hat": 1.001,
                "ess_bulk": 900,
                "ess_tail": 800,
            }
        ],
        {"beta": values},
    )
    assert result["available"]
    assert result["mcse_sd_ratio_max"] == 0.02
    assert result["parameters"][0]["parameter"] == "beta"
    trace = result["trace_series"][0]
    assert len(trace["chains"]) == 4
    assert len(trace["draw_indices"]) <= 128
    assert trace["chains"][2] == values[2, trace["draw_indices"]].tolist()


def test_undefined_and_truncated_evidence_stays_visible():
    from mmm_intelligence.integrations.native_scientific import chain_report

    result = chain_report(
        [{"parameter": "constant", "sd": 0.0, "mcse_mean": 0.0}],
        {"constant": np.ones((4, 20, 70))},
    )
    assert result["undefined_mcse_count"] == 1
    assert result["mcse_sd_ratio_max"] is None
    assert result["truncated"] is True
    assert result["total_trace_parameters"] == 70


def test_ppc_observed_distribution_detects_large_discrepancy():
    from mmm_intelligence.integrations.native_scientific import predictive_check

    rng = np.random.default_rng(73)
    samples = rng.normal(100, 5, size=(500, 30))
    compatible = predictive_check(samples, np.full(30, 100.0), [str(i) for i in range(30)])
    shifted = predictive_check(samples, np.full(30, 200.0), [str(i) for i in range(30)])
    assert compatible["scope"] == "observed_outcome"
    assert compatible["coverage_90"] == 1
    assert shifted["coverage_90"] == 0
    assert "mean_discrepancy" in shifted["discrepancy_flags"]
    assert shifted["causal_identification"] is False
    with pytest.raises(ValueError):
        predictive_check([[float("nan")]], [1], ["date"])


def test_native_parameter_means_retain_engine_parameter_units():
    from mmm_intelligence.integrations.native_scientific import parameter_means

    means = parameter_means(
        {"saturation_beta": np.ones((4, 10, 2)) * [2.0, 3.0], "sigma": np.ones((4, 10))}
    )
    assert means == {"saturation_beta[0]": 2.0, "saturation_beta[1]": 3.0}
