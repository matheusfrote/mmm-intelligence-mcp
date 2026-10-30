"""A failed numerical dependency must never produce an accepted recommendation."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from mmm_intelligence.errors import MMMError
from mmm_intelligence.forecasting import prepare, ridge_forecast
from mmm_intelligence.optimization import optimize
from mmm_intelligence.schemas import ForecastRequest, OptimizeRequest, SimulateRequest
from mmm_intelligence.simulation import simulate
from mmm_intelligence.synthetic import controlled_dataset


@pytest.mark.parametrize("periods,noise", [(51, 1), (10001, 1), (52, -1), (52, 10001)])
def test_controlled_dgp_rejects_invalid_experiments(periods, noise):
    with pytest.raises(ValueError):
        controlled_dataset(periods=periods, noise_sd=noise)


@pytest.mark.parametrize(
    "weights,success",
    [
        ([0.3, 0.3, 0.3], True),
        ([-0.1, 0.5, 0.6], True),
        ([0.8, 0.1, 0.1], False),
        ([0, 0, 1], True),
    ],
)
def test_optimization_dependency_failure_or_worse_candidate_is_not_accepted(
    trained, monkeypatch, weights, success
):
    model = deepcopy(trained)
    model["coefficients"].update(spend_search=1e6, spend_social=1e6, spend_video=0)
    monkeypatch.setattr(
        "mmm_intelligence.optimization.minimize",
        lambda *a, **k: SimpleNamespace(
            x=np.array(weights), success=success, message="external solver fixture"
        ),
    )
    with pytest.raises(MMMError) as caught:
        optimize(model, OptimizeRequest(model_id="fit", total_budget=100000.0))
    assert caught.value.code == "OPTIMIZATION_FAILED"


def test_fixed_budget_bounds_and_unknown_channels(trained):
    names = trained["request"]["media_columns"]
    fixed = {channel: 100.0 for channel in names}
    result = optimize(
        trained, OptimizeRequest(model_id="fit", total_budget=300.0, lower=fixed, upper=fixed)
    )
    assert result["solver"]["success"]
    with pytest.raises(MMMError) as caught:
        optimize(
            trained, OptimizeRequest(model_id="fit", total_budget=300.0, lower={"unknown": 1.0})
        )
    assert caught.value.code == "CHANNEL_MISMATCH"


def simulation_request():
    return SimulateRequest(
        model_id="fit",
        total_budget=0.0,
        horizon=27,
        allocation={"spend_search": 1.0, "spend_social": 0.0, "spend_video": 0.0},
    )


def test_negative_predictions_are_disclosed_and_overflow_is_refused(trained):
    model = deepcopy(trained)
    model["coefficients"] = {key: 0.0 for key in model["coefficients"]}
    model["coefficients"]["intercept"] = -1e9
    result = simulate(model, simulation_request())
    assert result["predicted_total"] < 0
    assert any(w.startswith("NEGATIVE_PREDICTIONS") for w in result["warnings"])
    assert any(w.startswith("LONG_HORIZON") for w in result["warnings"])
    model["coefficients"] = {key: 1e308 for key in model["coefficients"]}
    with np.errstate(over="ignore", invalid="ignore"):
        with pytest.raises(MMMError) as caught:
            simulate(model, simulation_request())
    assert caught.value.code == "NUMERICAL_ERROR"


@pytest.mark.parametrize("draws", [[1.0], [[]], [[float("nan")] * 9]])
def test_forecast_rejects_corrupt_bootstrap_coefficients(trained, draws):
    model = deepcopy(trained)
    model["coefficient_draws"] = draws
    request = ForecastRequest(
        model_id="fit",
        media_plan={c: [100.0] for c in model["request"]["media_columns"]},
        future_controls={
            c: [model["state"]["last_controls"][c]] for c in model["request"]["control_columns"]
        },
    )
    rows, _ = prepare(model, request)
    with pytest.raises(MMMError) as caught:
        ridge_forecast(model, request, rows)
    assert caught.value.code == "CORRUPT_MODEL"


@pytest.mark.parametrize("frequency,days", [("weekly", 7), ("daily", 1)])
def test_native_future_input_preparation_preserves_declared_frequency(
    trained, dataset, frequency, days
):
    model = {
        **trained,
        "backend": "pymc_marketing",
        "dataset": {**dataset, "frequency": frequency},
        "cutoff": 100,
    }
    request = ForecastRequest(
        backend="pymc_marketing",
        model_id="fit",
        media_plan={c: [0.0, 0.0] for c in model["request"]["media_columns"]},
        future_controls={c: [1.0, 1.0] for c in model["request"]["control_columns"]},
    )
    rows, assumptions = prepare(model, request)
    assert len(rows) == 2 and assumptions["frequency_days"] == days
    assert assumptions["warnings"]
    with pytest.raises(MMMError) as caught:
        prepare({**model, "backend": "google_meridian"}, request)
    assert caught.value.code == "BACKEND_MISMATCH"
