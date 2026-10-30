import numpy as np
import pytest


def plan(model, horizon=4):
    return {
        "model_id": model["model_id"],
        "backend": "ridge",
        "media_plan": {c: [1000.0] * horizon for c in model["request"]["media_columns"]},
        "future_controls": {
            c: [model["state"]["last_controls"][c]] * horizon
            for c in model["request"]["control_columns"]
        },
    }


def test_flat_forecast_agrees_with_existing_budget_simulator(service, trained):
    req = plan(trained)
    new = service.call("forecast_model", req)
    assert new.ok, new.error
    old = service.call(
        "simulate_budget",
        {
            "model_id": "fit",
            "horizon": 4,
            "total_budget": 12000.0,
            "allocation": {c: 1 / 3 for c in req["media_plan"]},
        },
    )
    assert new.data["prediction"]["total_mean"] == pytest.approx(old.data["predicted_total"])
    assert new.data["prediction"]["dates"][0] == "2025-12-29"
    assert new.data["scope"] == "future_conditional_projection"
    assert not new.data["decision_support"]["business_recommendation_eligible"]


def test_time_varying_plan_and_bootstrap_have_correct_shapes(service):
    service.call("generate_demo_dataset", {"dataset_id": "demo"})
    service.call("train_mmm", {"dataset_id": "demo", "model_id": "fit", "bootstrap_samples": 20})
    model = service.call("get_model", {"model_id": "fit"}).data
    req = plan(model)
    req["media_plan"]["spend_search"] = [0, 0, 2000, 2000]
    out = service.call("forecast_model", req)
    assert out.ok, out.error
    pred = out.data["prediction"]
    assert pred["interval_type"] == "conditional_bootstrap_mean"
    assert len(pred["mean"]) == len(pred["lower_90"]) == len(pred["upper_90"]) == 4
    assert np.isfinite(pred["mean"]).all()
    assert len(pred["total_interval_90"]) == 2


@pytest.mark.parametrize(
    "invalid", ["missing_control", "wrong_length", "negative", "extra_channel"]
)
def test_forecast_rejects_ambiguous_or_invalid_plans(service, trained, invalid):
    req = plan(trained)
    if invalid == "missing_control":
        req["future_controls"] = {}
    elif invalid == "wrong_length":
        req["media_plan"]["spend_search"] = [100.0]
    elif invalid == "negative":
        req["media_plan"]["spend_search"][0] = -1
    else:
        req["media_plan"]["unknown"] = [100.0] * 4
    out = service.call("forecast_model", req)
    assert not out.ok and out.error.code in {
        "INPUT_INVALID",
        "CHANNEL_MISMATCH",
        "CONTROL_MISMATCH",
    }


def test_pymc_future_bridge_includes_post_training_history_but_no_targets(dataset):
    from mmm_intelligence.integrations.worker import pymc_future_rows

    req = {
        "date_column": "date",
        "target_column": "revenue",
        "media_columns": ["spend_search", "spend_social", "spend_video"],
        "control_columns": ["price_index", "promotion"],
    }
    stored = {"dataset": dataset, "cutoff": 124, "request": req}
    future = [
        {
            "date": "2025-12-29",
            "spend_search": 1.0,
            "spend_social": 2.0,
            "spend_video": 3.0,
            "price_index": 1.0,
            "promotion": 0.0,
        }
    ]
    result = pymc_future_rows(stored, future)
    assert len(result) == 33
    assert result[0]["date"] == dataset["rows"][124]["date"]
    assert result[-1] == future[0]
    assert all("revenue" not in row for row in result)
