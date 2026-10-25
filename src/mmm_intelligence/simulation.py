"""Conditional future scenarios using persisted parameters and historical carryover."""

from datetime import date, timedelta

import numpy as np

from .errors import MMMError
from .modeling import adstock, design_matrix, hill
from .schemas import DISCLAIMER, SimulateRequest, TrainRequest


def check_model(model: dict) -> TrainRequest:
    """Verify persisted model dimensions before evaluating any scenario."""
    try:
        request = TrainRequest.model_validate(model["request"])
        names = [
            "intercept",
            *request.media_columns,
            "trend_years",
            "sin_year",
            "cos_year",
            *request.control_columns,
        ]
        if (
            model["schema_version"] != 1
            or model["engine"] != "constrained-ridge-v1"
            or model["feature_names"] != names
            or set(model["coefficients"]) != set(names)
            or not np.isfinite(list(model["coefficients"].values())).all()
            or model.get("exploratory") is not True
        ):
            raise ValueError("Invalid model")
        state = model["state"]
        if (
            state["step_days"] not in (1, 7)
            or not 52 <= state["history_periods"] <= 100000
            or set(state["last_controls"]) != set(request.control_columns)
        ):
            raise ValueError("Invalid state")
        date.fromisoformat(state["last_date"])
        for name in request.media_columns:
            p = model["media_parameters"][name]
            numbers = [
                p["decay"],
                p["half_saturation"],
                state["terminal_adstock"][name],
                state["reference_spend_per_period"][name],
                model["coefficients"][name],
            ]
            if (
                not np.isfinite(numbers).all()
                or min(numbers) < 0
                or not p["decay"] < 1
                or p["half_saturation"] <= 0
            ):
                raise ValueError("Invalid parameters")
        if not np.isfinite(list(state["last_controls"].values())).all():
            raise ValueError("Invalid controls")
        return request
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise MMMError("CORRUPT_MODEL", "Stored model has an invalid schema or parameters") from exc


def plan_design(model: dict, plan: dict, controls: np.ndarray, horizon: int) -> np.ndarray:
    media = model["request"]["media_columns"]
    transformed = np.column_stack(
        [
            hill(
                adstock(
                    np.full(horizon, plan[c]),
                    model["media_parameters"][c]["decay"],
                    model["state"]["terminal_adstock"][c],
                ),
                model["media_parameters"][c]["half_saturation"],
            )
            for c in media
        ]
    )
    return design_matrix(
        transformed,
        controls,
        np.arange(model["state"]["history_periods"], model["state"]["history_periods"] + horizon),
        model["state"]["step_days"],
    )


def simulate(model: dict, request: SimulateRequest) -> dict:
    trained = check_model(model)
    media, control_names = trained.media_columns, trained.control_columns
    if set(request.allocation) != set(media):
        raise MMMError(
            "CHANNEL_MISMATCH", "Allocation must contain exactly the modeled media names"
        )
    if request.future_controls is not None and set(request.future_controls) != set(control_names):
        raise MMMError(
            "CONTROL_MISMATCH", "Future controls must contain exactly the modeled controls"
        )
    state = model["state"]
    horizon = request.horizon
    controls = (
        np.column_stack(
            [
                request.future_controls[c]
                if request.future_controls is not None
                else np.full(horizon, state["last_controls"][c])
                for c in control_names
            ]
        )
        if control_names
        else np.empty((horizon, 0))
    )
    per_period = {c: request.total_budget * request.allocation[c] / horizon for c in media}
    reference = state["reference_spend_per_period"]
    coef = np.array([model["coefficients"][c] for c in model["feature_names"]])
    warnings = [
        *model.get("warnings", []),
        "POINT_SCENARIO: no uncertainty interval or causal interpretation",
        "REFERENCE: flat per-period mean spending of the last up to 13 historical periods",
        "HORIZON: residual effects beyond the horizon are excluded; history carryover included",
    ]
    if request.future_controls is None and control_names:
        warnings.append("CONTROL_ASSUMPTION: future controls held at the last observed value")
    if horizon > 26:
        warnings.append("LONG_HORIZON: trend extrapolation increases specification risk")
    for c in media:
        params = model["media_parameters"][c]
        if not params["training_spend_min"] <= per_period[c] <= params["training_spend_max"]:
            warnings.append(f"EXTRAPOLATION: scenario spend outside training range for {c}")

    def evaluate(plan):
        x = plan_design(model, plan, controls, horizon)
        return x @ coef, x[:, 1 : 1 + len(media)] @ coef[1 : 1 + len(media)], x

    prediction, component, scenario_design = evaluate(per_period)
    baseline, _, baseline_design = evaluate(reference)
    if not np.isfinite([prediction, baseline]).all():
        raise MMMError("NUMERICAL_ERROR", "Scenario produced nonfinite values")
    if (prediction < 0).any() or (baseline < 0).any():
        warnings.append(
            "NEGATIVE_PREDICTIONS: baseline model may be unsuitable; no clipping applied"
        )
    dates = [
        (
            date.fromisoformat(state["last_date"]) + timedelta(days=state["step_days"] * (i + 1))
        ).isoformat()
        for i in range(horizon)
    ]
    result = {
        "model_id": request.model_id,
        "exploratory": True,
        "disclaimer": DISCLAIMER,
        "synthetic": model["synthetic"],
        "horizon": horizon,
        "step_days": state["step_days"],
        "total_budget": request.total_budget,
        "allocation": request.allocation,
        "spend_per_period": per_period,
        "reference_spend_per_period": reference,
        "reference_total_budget": float(sum(reference.values()) * horizon),
        "predicted_total": float(prediction.sum()),
        "reference_predicted_total": float(baseline.sum()),
        "predicted_difference": float((prediction - baseline).sum()),
        "future_controls": {c: controls[:, j].tolist() for j, c in enumerate(control_names)},
        "terminal_adstock_initial": state["terminal_adstock"],
        "units": model["units"],
        "periods": [
            {
                "date": dates[i],
                "predicted": float(prediction[i]),
                "reference_predicted": float(baseline[i]),
                "modeled_media_component": float(component[i]),
            }
            for i in range(horizon)
        ],
        "warnings": warnings,
    }
    if model.get("coefficient_draws"):
        draws = np.asarray(model["coefficient_draws"], float)
        if draws.ndim != 2 or draws.shape[1] != len(coef) or not np.isfinite(draws).all():
            raise MMMError("CORRUPT_MODEL", "Invalid bootstrap coefficients")
        totals = draws @ scenario_design.sum(axis=0)
        differences = draws @ (scenario_design - baseline_design).sum(axis=0)
        result["uncertainty"] = {
            "method": model["uncertainty"],
            "interval_probability": 0.9,
            "total_mean_interval": np.quantile(totals, [0.05, 0.95]).tolist(),
            "difference_mean_interval": np.quantile(differences, [0.05, 0.95]).tolist(),
        }
        result["warnings"] = [w for w in warnings if not w.startswith("POINT_SCENARIO")]
        result["warnings"].append(
            "CONDITIONAL_INTERVAL: fixed shape, controls and observed initial state; no causal guarantee"
        )
    return result
