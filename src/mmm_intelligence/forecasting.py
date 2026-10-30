"""Explicit time-varying future inputs; fixed fitted parameters and no future targets."""

from datetime import date, timedelta

import numpy as np

from .diagnostics import ABSTENTION
from .errors import MMMError
from .modeling import adstock, design_matrix, hill
from .simulation import check_model


def prepare(model, request):
    spec = model["request"]
    media, controls = spec["media_columns"], spec["control_columns"]
    if set(request.media_plan) != set(media):
        raise MMMError("CHANNEL_MISMATCH", "Supply exactly the modeled media channels")
    if set(request.future_controls) != set(controls):
        raise MMMError("CONTROL_MISMATCH", "Supply every modeled control explicitly")
    n = len(next(iter(request.media_plan.values())))
    if request.backend == "ridge":
        last = model["state"]["last_date"]
        step = model["state"]["step_days"]
        ranges = {
            c: (
                model["media_parameters"][c]["training_spend_min"],
                model["media_parameters"][c]["training_spend_max"],
            )
            for c in media
        }
    else:
        if model["backend"] != request.backend:
            raise MMMError("BACKEND_MISMATCH", "Model belongs to a different backend")
        data = model["dataset"]
        last = data["rows"][-1][spec["date_column"]]
        step = 7 if data["frequency"] == "weekly" else 1
        training = data["rows"][: model["cutoff"]]
        ranges = {c: (min(r[c] for r in training), max(r[c] for r in training)) for c in media}
    dates = [
        (date.fromisoformat(last) + timedelta(days=step * (i + 1))).isoformat() for i in range(n)
    ]
    rows = [
        {
            spec["date_column"]: d,
            **{c: request.media_plan[c][i] for c in media},
            **{c: request.future_controls[c][i] for c in controls},
        }
        for i, d in enumerate(dates)
    ]
    warnings = list(model.get("warnings", []))
    for c in media:
        if any(v < ranges[c][0] or v > ranges[c][1] for v in request.media_plan[c]):
            warnings.append("EXTRAPOLATION: future spending outside training support for " + c)
    return rows, {
        "horizon": n,
        "frequency_days": step,
        "media_plan": request.media_plan,
        "future_controls": request.future_controls,
        "training_spend_ranges": ranges,
        "trend_and_seasonality": "Persisted model functions evaluated on future dates; no future baseline observations",
        "initial_adstock": "Observed history through " + last + "; no refit of coefficients",
        "uncertainty_exclusions": [
            "Future input error",
            "Misspecification",
            "Unmeasured confounding",
        ],
        "warnings": warnings,
    }


def ridge_forecast(model, request, rows):
    trained = check_model(model)
    n = len(rows)
    transformed = np.column_stack(
        [
            hill(
                adstock(
                    request.media_plan[c],
                    model["media_parameters"][c]["decay"],
                    model["state"]["terminal_adstock"][c],
                ),
                model["media_parameters"][c]["half_saturation"],
            )
            for c in trained.media_columns
        ]
    )
    controls = (
        np.array([request.future_controls[c] for c in trained.control_columns]).T
        if trained.control_columns
        else np.empty((n, 0))
    )
    x = design_matrix(
        transformed,
        controls,
        np.arange(model["state"]["history_periods"], model["state"]["history_periods"] + n),
        model["state"]["step_days"],
    )
    coef = np.array([model["coefficients"][c] for c in model["feature_names"]])
    mean = x @ coef
    result = {
        "dates": [r[trained.date_column] for r in rows],
        "mean": mean.tolist(),
        "total_mean": float(mean.sum()),
        "interval_type": "unavailable_point_estimate",
    }
    if model.get("coefficient_draws"):
        coefficients = np.asarray(model["coefficient_draws"], float)
        if (
            coefficients.ndim != 2
            or coefficients.shape[1] != x.shape[1]
            or not np.isfinite(coefficients).all()
        ):
            raise MMMError("CORRUPT_MODEL", "Invalid bootstrap coefficients")
        draws = coefficients @ x.T
        low, high = np.quantile(draws, [0.05, 0.95], axis=0)
        result.update(
            lower_90=low.tolist(),
            upper_90=high.tolist(),
            total_interval_90=np.quantile(draws.sum(axis=1), [0.05, 0.95]).tolist(),
            interval_type="conditional_bootstrap_mean",
            interval_level=0.9,
        )
    return result


def decision():
    return {
        "business_recommendation_eligible": False,
        "message": ABSTENTION,
        "required_next_step": "Review native diagnostics, prior/input sensitivity, historical support and an independent business experiment",
    }
