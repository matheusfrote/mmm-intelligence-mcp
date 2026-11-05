"""Original-unit regression checks; these tests never establish causal effects."""

from copy import deepcopy

import numpy as np

from mmm_intelligence.datasets import validate
from mmm_intelligence.modeling import train
from mmm_intelligence.schemas import SimulateRequest, TrainRequest
from mmm_intelligence.simulation import simulate


def test_kpi_unit_change_preserves_relative_fit_and_rescales_effect_uncertainty(dataset):
    request = TrainRequest(dataset_id="units", bootstrap_samples=0)
    reference = train(dataset, request, "reference", validate(dataset, request, 100000))
    scaled = deepcopy(dataset)
    factor = 1000
    for row in scaled["rows"]:
        row["revenue"] *= factor
    converted = train(scaled, request, "converted", validate(scaled, request, 100000))
    np.testing.assert_allclose(
        list(converted["coefficients"].values()),
        np.asarray(list(reference["coefficients"].values())) * factor,
        rtol=1e-6,
        atol=1e-6,
    )
    assert np.isclose(converted["metrics"]["test"]["r2"], reference["metrics"]["test"]["r2"])
    assert np.isclose(
        converted["metrics"]["test"]["wape_percent"], reference["metrics"]["test"]["wape_percent"]
    )
    assert np.isclose(
        converted["metrics"]["test"]["mae"], reference["metrics"]["test"]["mae"] * factor
    )
    scenario = SimulateRequest(
        model_id="scale-test",
        total_budget=90000,
        allocation={c: 1 / 3 for c in request.media_columns},
    )
    original = simulate(reference, scenario)
    result = simulate(converted, scenario)
    assert np.isclose(result["predicted_total"], original["predicted_total"] * factor)
    for method in ("hc3", "hac"):
        before = original["conditional_linear_confidence"]["methods"][method]
        after = result["conditional_linear_confidence"]["methods"][method]
        assert before["available"] and after["available"]
        for metric in ("estimate", "lower", "upper", "standard_error"):
            assert np.isclose(after[metric], before[metric] * factor, rtol=1e-6, atol=1e-6)
