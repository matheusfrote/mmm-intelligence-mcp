"""Deterministic calendar design and declared fixed-parameter diagnostics."""

from copy import deepcopy

import numpy as np
import pytest


def test_calendar_policy_is_train_target_blind_and_reusable_on_future_rows():
    from mmm_intelligence.integrations.native_scientific import calendar_design

    rows = [{"date": "2020-01-06", "revenue": 10}, {"date": "2021-01-05", "revenue": 20}]
    untouched = deepcopy(rows)
    augmented, policy = calendar_design(rows, "date", seasonal=True)
    assert rows == untouched
    assert augmented[0]["mmm_trend_years"] == 0
    assert augmented[1]["mmm_trend_years"] == 365 / 365.25
    future, same = calendar_design([{"date": "2022-01-05"}], "date", policy=policy)
    assert same == policy and future[0]["mmm_trend_years"] > 1


def test_reserved_calendar_columns_are_rejected_and_absent_fixed_nodes_are_not_invented():
    from mmm_intelligence.integrations.native_scientific import calendar_design, verified_fixed

    with pytest.raises(ValueError, match="Reserved"):
        calendar_design([{"date": "2024-01-01", "mmm_trend_years": 0}], "date")
    assert verified_fixed({}, {"absent": {"value": 0}}) == {}


def test_only_declared_deterministic_nodes_are_exempt_from_mcmc_diagnostics():
    from mmm_intelligence.integrations.native_scientific import chain_report

    stats = [{"parameter": name, "sd": 0, "mcse_mean": 0} for name in ("fixed[0]", "stuck")]
    variables = {"fixed": np.ones((4, 100, 1)), "stuck": np.zeros((4, 100))}
    result = chain_report(
        stats, variables, fixed={"fixed": {"value": 1, "basis": "declared deterministic prior"}}
    )
    assert result["undefined_mcse_count"] == 1
    assert result["fixed_parameters"]["fixed"]["verified_against_posterior"] is True
    assert result["parameters"][0]["diagnostic_status"] == "not_applicable_fixed"
    with pytest.raises(ValueError, match="fixed"):
        chain_report(stats, variables, fixed={"fixed": {"value": 0, "basis": "declared prior"}})


def test_robyn_algorithm_and_prior_sensitivity_are_explicit_bounded_contracts():
    from mmm_intelligence.schemas import BackendRequest, ScientificProtocol

    request = BackendRequest(dataset_id="data", backend="meta_robyn", robyn_algorithm="DE")
    assert request.robyn_algorithm == "DE"
    with pytest.raises(ValueError):
        BackendRequest(dataset_id="data", backend="meta_robyn", robyn_algorithm="NGOpt")
    protocol = ScientificProtocol(prior_scale_multipliers=[0.5, 2.0])
    assert protocol.prior_scale_multipliers == [0.5, 2.0]
    with pytest.raises(ValueError):
        BackendRequest(dataset_id="data", backend="google_meridian", robyn_algorithm="NGOpt")
    for options in [
        {"baseline_variants": ["legacy", "legacy"]},
        {"prior_scale_multipliers": [1.0, 1.0]},
    ]:
        with pytest.raises(ValueError):
            ScientificProtocol(**options)
    from mmm_intelligence.schemas import AuditRequest

    with pytest.raises(ValueError):
        AuditRequest(model_id="model", scientific={"native_monte_carlo": {}})


def test_meridian_target_accept_is_translated_to_official_adapter_keyword():
    pytest.importorskip(
        "immutabledict",
        reason="Native Meridian-only dependency; exercised by real isolated transport test",
    )
    from mmm_intelligence.integrations.native_scientific import meridian_sampler_options

    options = meridian_sampler_options({"target_accept": 0.97})
    assert options["dual_averaging_kwargs"] == {"target_accept_prob": 0.97}
    assert options["max_tree_depth"] == 8
    assert meridian_sampler_options({})["dual_averaging_kwargs"]["target_accept_prob"] == 0.85
