"""Observable failures for legacy numerical and input-contract boundaries."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from mmm_intelligence.diagnostics import classify_bayesian, interval_coverage
from mmm_intelligence.errors import MMMError
from mmm_intelligence.modeling import fit_ridge
from mmm_intelligence.schemas import CSVImportRequest, DatasetSpec, ForecastRequest, SimulateRequest
from mmm_intelligence.simulation import check_model, simulate


@pytest.mark.parametrize(
    "changes",
    [
        {"target_column": "../target"},
        {"date_column": "date with space"},
        {"media_columns": ["x", "x"]},
        {"media_columns": ["invalid name"]},
        {"control_columns": ["intercept"]},
        {"media_columns": ["trend_years"]},
        {"media_columns": ["revenue"]},
        {"control_columns": ["date"]},
    ],
)
def test_model_schema_rejects_ambiguous_or_internal_feature_names(changes):
    with pytest.raises(ValidationError):
        DatasetSpec(dataset_id="data", **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"aggregate_weekly": True},
        {"frequency": "daily"},
        {"duplicate_policy": "aggregate"},
        {
            "duplicate_policy": "aggregate",
            "reducers": {
                "revenue": "mean",
                "spend_search": "sum",
                "spend_social": "sum",
                "spend_video": "sum",
                "price_index": "mean",
                "promotion": "mean",
            },
        },
        {"reducers": {"revenue": "sum"}},
        {"date_format": "iso_datetime"},
        {"timezone": "UTC"},
        {"column_mapping": {"a": "revenue", "b": "revenue"}},
        {"column_mapping": {"": "revenue"}},
    ],
)
def test_csv_policy_requires_explicit_unambiguous_transformations(changes):
    with pytest.raises(ValidationError):
        CSVImportRequest(
            csv_text="a,b\n1,2", synthetic=True, authorization_reference="synthetic", **changes
        )


def test_scenario_input_limits_controls_and_horizons():
    for controls in [{str(i): [0.0] for i in range(11)}, {"price_index": [1.0, 2.0]}]:
        with pytest.raises(ValidationError):
            SimulateRequest(
                model_id="fit",
                horizon=1,
                total_budget=10.0,
                allocation={"a": 1.0},
                future_controls=controls,
            )
    with pytest.raises(ValidationError):
        ForecastRequest(model_id="fit", media_plan={"a": [1e9, 1e9]}, future_controls={})


@pytest.mark.parametrize(
    "x,y,count,alpha",
    [
        ([1, 2], [1, 2], 1, 1),
        ([[1, 2]], [[1]], 1, 1),
        ([[1, 2]], [1, 2], 1, 1),
        (np.empty((0, 2)), [], 1, 1),
        ([[1, np.nan]], [1], 1, 1),
        ([[1, 2]], [np.inf], 1, 1),
        ([[1, 2]], [1], 1, float("nan")),
        ([[1, 2]], [1], 1, 0),
        ([[1, 2]], [1], 0, 1),
        ([[1, 2]], [1], 2, 1),
    ],
)
def test_ridge_rejects_invalid_numerical_shapes(x, y, count, alpha):
    with pytest.raises(ValueError):
        fit_ridge(x, y, count, alpha)


@pytest.mark.parametrize("success,coefficients", [(False, [1.0, 2.0]), (True, [np.nan, 2.0])])
def test_solver_failure_never_creates_a_successful_model(monkeypatch, success, coefficients):
    monkeypatch.setattr(
        "mmm_intelligence.modeling.lsq_linear",
        lambda *a, **k: SimpleNamespace(success=success, x=np.array(coefficients)),
    )
    with pytest.raises(MMMError) as error:
        fit_ridge([[1, 1], [1, 2]], [1, 2], 1, 1)
    assert error.value.code == "SOLVER_FAILED"


@pytest.mark.parametrize(
    "policy",
    [{"max_rhat": 1}, {"max_rhat": 1.3}, {"min_ess_per_chain": 9}, {"min_ess_per_chain": 10001}],
)
def test_diagnostic_policy_bounds_are_enforced(policy):
    with pytest.raises(ValueError):
        classify_bayesian({}, **policy)


def test_short_and_failed_bayesian_runs_abstain():
    diagnostics = {
        "chains": 2,
        "draws": 20,
        "tune": 20,
        "r_hat_max": 1.0,
        "ess_bulk_min": 5,
        "ess_tail_min": 5,
        "divergences": 0,
        "r_hat_undefined_count": 0,
        "ess_bulk_undefined_count": 0,
        "ess_tail_undefined_count": 0,
    }
    report = classify_bayesian(diagnostics)
    assert report["status"] == "inadequate"
    assert "fewer_than_four_chains" in report["missing_or_insufficient"]
    assert set(report["failed_screens"]) == {"ess_bulk_min", "ess_tail_min"}
    assert (
        classify_bayesian({**diagnostics, "estimation_failed": True})["status"] == "not_estimable"
    )


@pytest.mark.parametrize(
    "truth,low,high,estimand",
    [
        ([], [], [], "observed"),
        ([[1]], [[0]], [[2]], "observed"),
        ([1], [0, 0], [2, 2], "observed"),
        ([1], [0], [2, 2], "observed"),
        ([np.nan], [0], [2], "observed"),
        ([1], [2], [0], "observed"),
        ([1], [0], [2], "unknown"),
    ],
)
def test_interval_coverage_refuses_invalid_evidence(truth, low, high, estimand):
    with pytest.raises(ValueError):
        interval_coverage(truth, low, high, estimand)


@pytest.mark.parametrize(
    "path,value",
    [
        (("state", "step_days"), 2),
        (("state", "history_periods"), 1),
        (("state", "last_controls"), {}),
        (("media_parameters", "spend_search", "decay"), 1),
        (("media_parameters", "spend_search", "half_saturation"), 0),
        (("state", "last_controls", "price_index"), np.nan),
    ],
)
def test_corrupt_persisted_parameters_cannot_produce_scenarios(trained, path, value):
    model = deepcopy(trained)
    target = model
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(MMMError) as error:
        check_model(model)
    assert error.value.code == "CORRUPT_MODEL"


def test_scenario_control_names_must_match_and_corrupt_bootstrap_refused(trained):
    arguments = {
        "model_id": trained["model_id"],
        "horizon": 1,
        "total_budget": 0.0,
        "allocation": {"spend_search": 1.0, "spend_social": 0.0, "spend_video": 0.0},
    }
    with pytest.raises(MMMError) as error:
        simulate(trained, SimulateRequest(**arguments, future_controls={"wrong": [1.0]}))
    assert error.value.code == "CONTROL_MISMATCH"
    model = deepcopy(trained)
    model["coefficient_draws"] = [[1.0]]
    with pytest.raises(MMMError) as error:
        simulate(model, SimulateRequest(**arguments))
    assert error.value.code == "CORRUPT_MODEL"
