import copy

import numpy as np
import pytest

from mmm_intelligence.datasets import validate
from mmm_intelligence.modeling import adstock, fit_ridge, hill, metrics, train
from mmm_intelligence.schemas import TrainRequest


def test_adstock_hand_calculation_continuity_and_time_direction():
    x = [100, 0, 20, 0]
    a = adstock(x, 0.5)
    np.testing.assert_allclose(a, [50, 25, 22.5, 11.25])
    np.testing.assert_allclose(adstock(x[2:], 0.5, a[1]), a[2:])
    np.testing.assert_allclose(adstock([100, 0, 20, 999], 0.5)[:3], a[:3])
    assert adstock(np.full(200, 10), 0.8)[-1] == pytest.approx(10)
    np.testing.assert_allclose(adstock(x, 0), x)


@pytest.mark.parametrize("decay", [-0.1, 1, float("nan")])
def test_adstock_invalid(decay):
    with pytest.raises(ValueError):
        adstock([1], decay)


def test_hill_half_saturation_monotonicity_and_concavity():
    assert hill(0, 20) == 0
    assert hill(20, 20) == 0.5
    values = hill(np.arange(1, 101), 20)
    assert (np.diff(values) > 0).all()
    assert (np.diff(values, n=2) < 0).all()
    assert hill(1e10, 20) == pytest.approx(1)
    with pytest.raises(ValueError):
        hill([1], 0)


def test_metrics_match_hand_calculation_and_undefined_cases():
    m = metrics([10, 20, 30], [12, 18, 33])
    assert m["mae"] == pytest.approx(7 / 3)
    assert m["wape_percent"] == pytest.approx(100 * 7 / 60)
    assert m["r2"] == pytest.approx(1 - 17 / 200)
    assert metrics([0, 0], [0, 1])["wape_percent"] is None
    assert metrics([2, 2], [2, 2])["r2"] is None
    with pytest.raises(ValueError):
        metrics([], [])


def test_restricted_regression_free_controls_and_regularization():
    rng = np.random.default_rng(1)
    media, control = rng.normal(size=(2, 300))
    x = np.column_stack([np.ones(300), media, control])
    y = 5 - 3 * media - 2 * control
    coef, diagnostics = fit_ridge(x, y, 1, 0.01)
    assert diagnostics["success"]
    assert coef[1] >= 0
    assert coef[2] < 0  # Negative control effects remain possible.
    simple = np.column_stack([np.ones(300), media])
    small, _ = fit_ridge(simple, 10 + 4 * media, 1, 0.01)
    large, _ = fit_ridge(simple, 10 + 4 * media, 1, 100)
    assert 0 < large[1] < small[1]


def test_holdout_does_not_change_fit_or_train_transform(dataset):
    req = TrainRequest(dataset_id="demo")
    report = validate(dataset, req, 10000)
    before = train(dataset, req, "a", report)
    changed = copy.deepcopy(dataset)
    cutoff = len(dataset["rows"]) - before["split"]["test_rows"]
    for row in changed["rows"][cutoff:]:
        row["revenue"] = 1e8
        row["spend_search"] = 1e9
        row["price_index"] = 20
    after = train(changed, req, "b", report)
    assert before["coefficients"] == after["coefficients"]
    assert before["media_parameters"] == after["media_parameters"]
    assert before["solver"]["feature_scales"] == after["solver"]["feature_scales"]
    assert before["metrics"]["test"] != after["metrics"]["test"]
    assert before["split"]["train_end"] < before["split"]["test_start"]
    assert before["split"]["refit_on_test"] is False


def test_fit_has_reasonable_synthetic_holdout_and_persists_state(trained, dataset):
    assert all(trained["coefficients"][c] >= 0 for c in trained["request"]["media_columns"])
    assert trained["metrics"]["test"]["wape_percent"] < 10
    assert trained["metrics"]["test"]["mae"] < trained["metrics"]["test_train_mean_baseline"]["mae"]
    for c, value in trained["state"]["terminal_adstock"].items():
        assert value == pytest.approx(adstock([r[c] for r in dataset["rows"]], 0.5)[-1])
