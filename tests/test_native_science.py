"""Scientific boundary regressions; no optional native engine is imported."""

from copy import deepcopy

import pytest

from mmm_intelligence.integrations.worker import (
    declared_target_type,
    divergence_diagnostics,
    prepare_meridian_holdout,
    robyn_split_indices,
    summarize,
    summarize_diagnostics,
)


def _data():
    return {
        "target_type": "revenue",
        "rows": [{"sales": value, "spend": value / 2} for value in range(100, 152)],
    }


def test_meridian_holdout_target_perturbation_cannot_change_native_input():
    data = _data()
    original = deepcopy(data)
    req = {"target_column": "sales", "test_fraction": 0.2}
    rows, observed, cutoff, policy = prepare_meridian_holdout(data, req)
    altered = deepcopy(data)
    for row in altered["rows"][cutoff:]:
        row["sales"] *= 100
    new_rows, new_observed, new_cutoff, new_policy = prepare_meridian_holdout(altered, req)
    assert data == original  # Shared data and stored observations remain untouched.
    assert rows == new_rows
    assert policy == new_policy
    assert cutoff == new_cutoff == 41
    assert observed[:cutoff] == new_observed[:cutoff]
    assert observed[cutoff:] != new_observed[cutoff:]
    assert policy["placeholder"] == 120
    assert rows[-1]["sales"] == 120
    assert policy["test_rows"] == 11
    assert not policy["target_holdout_used_in_native_preprocessing"]


@pytest.mark.parametrize("fraction", [0, 1, float("nan"), True, "0.2"])
def test_meridian_holdout_rejects_invalid_fraction_before_native_import(fraction):
    with pytest.raises(ValueError, match="test_fraction"):
        prepare_meridian_holdout(_data(), {"target_column": "sales", "test_fraction": fraction})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, None])
def test_meridian_holdout_rejects_missing_or_nonfinite_target(value):
    data = _data()
    data["rows"][-1]["sales"] = value
    with pytest.raises(ValueError, match="targets"):
        prepare_meridian_holdout(data, {"target_column": "sales", "test_fraction": 0.2})


def test_meridian_does_not_infer_generic_kpi_is_money():
    data = _data()
    del data["target_type"]
    with pytest.raises(ValueError, match="declared revenue"):
        prepare_meridian_holdout(data, {"target_column": "sales", "test_fraction": 0.2})
    data["target_type"] = "non_revenue"
    with pytest.raises(ValueError, match="declared revenue"):
        prepare_meridian_holdout(data, {"target_column": "sales", "test_fraction": 0.2})


def test_target_semantics_legacy_fallback_is_restricted_to_known_demo():
    legacy = {"synthetic": True, "source": "built-in-demo-v1"}
    assert declared_target_type(legacy, "revenue") == "revenue"
    assert declared_target_type(legacy, "conversions") == "unspecified"
    assert declared_target_type({"synthetic": True, "source": "user"}, "revenue") == "unspecified"
    assert declared_target_type({"source": "built-in-demo-v1"}, "revenue") == "unspecified"
    assert declared_target_type({"target_type": "non_revenue"}, "revenue") == "non_revenue"
    with pytest.raises(ValueError, match="target_type"):
        declared_target_type({"target_type": []}, "sales")


@pytest.mark.parametrize(
    ("n", "train_end", "validation_end", "test_count"),
    [
        (91, 55, 73, 18),
        (94, 56, 74, 20),
        (96, 58, 77, 19),
        (99, 59, 78, 21),
        (101, 61, 81, 20),
        (104, 62, 82, 22),
    ],
)
def test_robyn_native_partition_matches_installed_r_reference(
    n, train_end, validation_end, test_count
):
    split = robyn_split_indices(n)
    assert split == {"train_end": train_end, "validation_end": validation_end, "test_end": n}
    assert n - split["validation_end"] == test_count


def test_robyn_rejects_empty_partitions():
    with pytest.raises(ValueError, match="empty partition"):
        robyn_split_indices(3)


def test_diagnostic_extrema_preserve_precision_and_flag_undefined_values():
    diagnostics = summarize_diagnostics(
        {
            "r_hat": [1.0149032188, float("nan")],
            "ess_bulk": [312.2387654, 450],
            "ess_tail": [100.0123456, 200],
        }
    )
    assert diagnostics["r_hat_max"] == 1.0149032188
    assert diagnostics["ess_bulk_min"] == 312.2387654
    assert diagnostics["ess_tail_min"] == 100.0123456
    assert diagnostics["r_hat_undefined_count"] == 1
    assert diagnostics["r_hat_available"]
    missing = summarize_diagnostics({})
    assert missing["r_hat_max"] is None
    assert not missing["ess_tail_available"]
    assert not diagnostics["convergence_certified"]
    assert divergence_diagnostics({})["divergences_available"] is False


def test_expected_and_predictive_intervals_keep_explicit_different_semantics():
    samples = [[10, 20], [12, 22], [14, 24]]
    dates = ["2025-01-06", "2025-01-13"]
    mean = summarize(samples, dates, interval_type="conditional_expected_outcome")
    predictive = summarize(samples, dates, interval_type="posterior_predictive_observed")
    assert mean["interval_type"] != predictive["interval_type"]
    assert mean["interval_level"] == predictive["interval_level"] == 0.9
