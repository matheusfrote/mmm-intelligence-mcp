import copy

import numpy as np
import pytest

from mmm_intelligence.errors import MMMError
from mmm_intelligence.modeling import adstock, hill
from mmm_intelligence.schemas import SimulateRequest
from mmm_intelligence.simulation import simulate


def request(**kwargs):
    return SimulateRequest(
        model_id="fit",
        total_budget=60000,
        allocation={"spend_search": 0.5, "spend_social": 0.3, "spend_video": 0.2},
        **kwargs,
    )


def test_budget_accounting_controls_and_horizon(trained):
    result = simulate(trained, request(horizon=8))
    assert sum(result["spend_per_period"].values()) * 8 == pytest.approx(60000)
    assert len(result["periods"]) == 8
    assert result["predicted_total"] == pytest.approx(
        sum(p["predicted"] for p in result["periods"])
    )
    assert result["periods"][0]["date"] > trained["state"]["last_date"]
    assert (
        result["future_controls"]["price_index"]
        == [trained["state"]["last_controls"]["price_index"]] * 8
    )


def test_reference_plan_identity_and_zero_budget_carryover(trained):
    ref = trained["state"]["reference_spend_per_period"]
    total = sum(ref.values())
    same = simulate(
        trained,
        SimulateRequest(
            model_id="fit",
            horizon=4,
            total_budget=total * 4,
            allocation={c: v / total for c, v in ref.items()},
        ),
    )
    assert same["predicted_difference"] == pytest.approx(0, abs=1e-8)
    zero = simulate(
        trained,
        SimulateRequest(
            model_id="fit", horizon=3, total_budget=0, allocation={c: 1 / 3 for c in ref}
        ),
    )
    expected = sum(
        trained["coefficients"][c]
        * hill(
            adstock([0], 0.5, trained["state"]["terminal_adstock"][c]),
            trained["media_parameters"][c]["half_saturation"],
        )[0]
        for c in ref
    )
    assert zero["periods"][0]["modeled_media_component"] == pytest.approx(expected)
    assert expected > 0


def test_horizon_is_not_naive_multiplication_and_explicit_controls(trained):
    one = simulate(trained, request(horizon=1))
    many = simulate(trained, request(horizon=10))
    assert many["predicted_total"] != pytest.approx(one["predicted_total"] * 10)
    controls = {"price_index": [2.0] * 13, "promotion": [0.0] * 13}
    explicit = simulate(trained, request(future_controls=controls))
    assert explicit["future_controls"] == controls
    assert explicit["predicted_total"] != simulate(trained, request())["predicted_total"]


def test_wrong_names_and_damaged_model_fail(trained):
    req = request().model_copy(update={"allocation": {"wrong": 1}})
    with pytest.raises(MMMError, match="modeled media"):
        simulate(trained, req)
    req = request(future_controls={"wrong": [1.0] * 13})
    with pytest.raises(MMMError, match="modeled controls"):
        simulate(trained, req)
    broken = copy.deepcopy(trained)
    broken["coefficients"]["spend_search"] = np.nan
    with pytest.raises(MMMError, match="invalid"):
        simulate(broken, request())
