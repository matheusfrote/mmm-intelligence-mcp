"""Training-only shape selection, sensitivity and explicit experiment calibration."""

from itertools import product

import numpy as np

from .datasets import validate
from .errors import MMMError
from .modeling import adstock, hill, train
from .schemas import CalibrationRequest, TrainRequest, TuneRequest


def tune(dataset: dict, request: TuneRequest, model_id: str, max_rows: int) -> dict:
    full_report = validate(dataset, request, max_rows)
    if not full_report["valid"]:
        raise MMMError("DATASET_INVALID", "; ".join(full_report["issues"]))
    outer_cutoff = len(dataset["rows"]) - int(np.ceil(len(dataset["rows"]) * request.test_fraction))
    # One strictly pre-test validation slice; final holdout remains untouched by selection.
    inner = {**dataset, "rows": dataset["rows"][:outer_cutoff]}
    rankings = []
    for decay, multiplier in product(request.decays, request.multipliers):
        params = request.model_dump(exclude={"decays", "multipliers"})
        params.update(adstock_decay=decay, saturation_multiplier=multiplier, bootstrap_samples=0)
        candidate_request = TrainRequest.model_validate(params)
        report = validate(inner, candidate_request, max_rows)
        if not report["valid"]:
            raise MMMError("INSUFFICIENT_TUNING_HISTORY", "; ".join(report["issues"]))
        candidate = train(inner, candidate_request, "cv", report)
        rankings.append(
            {
                "decay": decay,
                "saturation_multiplier": multiplier,
                "validation_mae": candidate["metrics"]["test"]["mae"],
                "validation_start": candidate["split"]["test_start"],
                "validation_end": inner["rows"][-1][request.date_column],
            }
        )
    rankings.sort(key=lambda r: r["validation_mae"])
    best = rankings[0]
    params = request.model_dump(exclude={"decays", "multipliers"})
    params.update(adstock_decay=best["decay"], saturation_multiplier=best["saturation_multiplier"])
    selected = TrainRequest.model_validate(params)
    result = train(dataset, selected, model_id, full_report)
    result["shape_selection"] = {
        "method": "nested_chronological_single_validation",
        "selection_data_end": inner["rows"][-1][request.date_column],
        "rankings": rankings,
        "outer_test_used": False,
    }
    return result


def calibrate(model: dict, request: CalibrationRequest) -> dict:
    if model.get("synthetic") is not request.synthetic:
        raise MMMError(
            "MIXED_DATA_ORIGINS", "Model and experiment origins must both be synthetic or both real"
        )
    if request.channel not in model["request"]["media_columns"]:
        raise MMMError("CHANNEL_MISMATCH", "Experiment channel is not modeled")
    if not model.get("coefficient_draws"):
        raise MMMError(
            "UNCERTAINTY_REQUIRED", "Train with bootstrap_samples >= 20 before calibration"
        )
    if len(model["coefficient_draws"]) < 20:
        raise MMMError("UNCERTAINTY_REQUIRED", "At least 20 bootstrap samples are required")
    p = model["media_parameters"][request.channel]

    def curve(spend):
        return hill(
            adstock(np.full(request.horizon, spend), p["decay"], request.initial_adstock),
            p["half_saturation"],
        ).sum()

    contrast = float(curve(request.treatment_spend) - curve(request.control_spend))
    if abs(contrast) < 1e-12:
        raise MMMError(
            "UNINFORMATIVE_EXPERIMENT", "Treatment and control imply zero modeled contrast"
        )
    index = model["feature_names"].index(request.channel)
    predicted = np.asarray(model["coefficient_draws"])[:, index] * contrast
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        logw = -0.5 * ((predicted - request.lift_mean) / request.lift_sd) ** 2
    if not np.isfinite(logw).all():
        raise MMMError(
            "CALIBRATION_NUMERIC_RANGE",
            "Experiment precision or distance from model support exceeds numeric range",
        )
    weights = np.exp(logw - logw.max())
    weights /= weights.sum()
    effective = float(1 / np.sum(weights**2))
    ordered = np.argsort(predicted)
    cumulative = np.cumsum(weights[ordered])
    interval = np.interp([0.05, 0.95], cumulative, predicted[ordered]).tolist()
    return {
        "model_id": request.model_id,
        "experiment_id": request.experiment_id,
        "method": "Gaussian importance reweighting of conditional bootstrap draws",
        "synthetic": request.synthetic,
        "model_synthetic": model["synthetic"],
        "experiment_synthetic": request.synthetic,
        "observed_lift": request.lift_mean,
        "lift_sd": request.lift_sd,
        "uncalibrated_lift_mean": float(predicted.mean()),
        "calibrated_lift_mean": float(weights @ predicted),
        "calibrated_lift_interval_90": interval,
        "effective_samples": effective,
        "weights": weights.tolist(),
        "model_changed": False,
        "warnings": [
            "EXPERIMENT_ASSUMPTIONS_REQUIRED: no verification of randomization or transportability",
            "CONDITIONAL_REWEIGHTING: not a full Bayesian refit; requires fixed-shape support",
            *(
                ["LOW_EFFECTIVE_SAMPLES: experiment conflicts with conditional model support"]
                if effective < 20
                else []
            ),
        ],
    }
