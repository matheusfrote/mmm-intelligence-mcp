"""Exploratory constrained ridge. Hyperparameters are explicit, never tuned on test data."""

import math
from datetime import datetime, timezone
from importlib.metadata import version

import numpy as np
from scipy.optimize import lsq_linear

from .errors import MMMError
from .schemas import DISCLAIMER, TrainRequest
from .storage import digest


def adstock(values, decay: float, initial: float = 0.0) -> np.ndarray:
    """Normalized geometric recurrence a[t]=(1-decay)*x[t]+decay*a[t-1]."""
    x = np.asarray(values, dtype=float)
    if (
        x.ndim != 1
        or not np.isfinite(x).all()
        or (x < 0).any()
        or not 0 <= decay < 1
        or not np.isfinite(initial)
        or initial < 0
    ):
        raise ValueError("Adstock requires finite nonnegative values, state and decay in [0,1)")
    result = np.empty_like(x)
    state = initial
    for i, value in enumerate(x):
        state = (1 - decay) * value + decay * state
        result[i] = state
    return result


def hill(values, half_saturation: float) -> np.ndarray:
    """Hill with fixed exponent one: x/(K+x), with stable zero handling."""
    x = np.asarray(values, dtype=float)
    if (
        not np.isfinite(x).all()
        or (x < 0).any()
        or not np.isfinite(half_saturation)
        or half_saturation <= 0
    ):
        raise ValueError("Hill requires finite x>=0 and K>0")
    return x / (half_saturation + x)


def metrics(observed, predicted) -> dict:
    y, p = np.asarray(observed, float), np.asarray(predicted, float)
    if y.ndim != 1 or y.shape != p.shape or not len(y) or not np.isfinite([y, p]).all():
        raise ValueError("Metrics require matching nonempty finite vectors")
    error = y - p
    total = float(np.abs(y).sum())
    variance = float(np.sum((y - y.mean()) ** 2))
    return {
        "mae": float(np.abs(error).mean()),
        "wape_percent": float(np.abs(error).sum() / total * 100) if total > 0 else None,
        "r2": float(1 - np.sum(error**2) / variance) if variance > 0 else None,
    }


def fit_ridge(design, target, media_count: int, alpha: float):
    """Train-only scaling; intercept unpenalized, only media sign-constrained."""
    x, y = np.asarray(design, float), np.asarray(target, float)
    if (
        x.ndim != 2
        or y.ndim != 1
        or x.shape[0] != len(y)
        or not len(y)
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or not np.isfinite(alpha)
        or alpha <= 0
        or not 1 <= media_count < x.shape[1]
    ):
        raise ValueError("Invalid regression inputs")
    mean, scale = x.mean(axis=0), x.std(axis=0)
    mean[0], scale[0] = 0, 1
    scale[scale < 1e-12] = 1
    z = (x - mean) / scale
    penalty = np.eye(x.shape[1]) * math.sqrt(alpha)
    penalty[0, 0] = 0
    lower = np.full(x.shape[1], -np.inf)
    lower[1 : 1 + media_count] = 0
    fit = lsq_linear(
        np.vstack([z, penalty]),
        np.r_[y, np.zeros(x.shape[1])],
        bounds=(lower, np.inf),
        tol=1e-10,
        max_iter=500,
    )
    if not fit.success or not np.isfinite(fit.x).all():
        raise MMMError("SOLVER_FAILED", "Constrained ridge did not converge")
    coefficients = fit.x / scale
    coefficients[0] -= mean @ coefficients
    return coefficients, {
        "success": True,
        "status": int(fit.status),
        "iterations": int(fit.nit),
        "cost": float(fit.cost),
        "feature_means": mean.tolist(),
        "feature_scales": scale.tolist(),
    }


def design_matrix(media, controls, indices, step_days):
    time_days = np.asarray(indices) * step_days
    return np.column_stack(
        [
            np.ones(len(indices)),
            media,
            time_days / 365.25,
            np.sin(2 * np.pi * time_days / 365.25),
            np.cos(2 * np.pi * time_days / 365.25),
            controls,
        ]
    )


def train(dataset: dict, request: TrainRequest, model_id: str, report: dict) -> dict:
    rows = dataset["rows"]
    n, m = len(rows), len(request.media_columns)
    cutoff = n - int(np.ceil(n * request.test_fraction))
    warmup = request.warmup_periods
    spend = np.array([[r[c] for c in request.media_columns] for r in rows])
    controls = np.array([[r[c] for c in request.control_columns] for r in rows]).reshape(n, -1)
    y = np.array([r[request.target_column] for r in rows])
    transformed, parameters, terminal = [], {}, {}
    for j, name in enumerate(request.media_columns):
        training_spend = spend[warmup:cutoff, j]
        if np.ptp(training_spend) <= 1e-12:
            raise MMMError("UNIDENTIFIABLE_MEDIA", f"Training media must vary: {name}")
        stock = adstock(spend[:, j], request.adstock_decay)
        positive = stock[warmup:cutoff][stock[warmup:cutoff] > 0]
        k = float(np.median(positive) * request.saturation_multiplier)
        parameters[name] = {
            "decay": request.adstock_decay,
            "half_saturation": k,
            "hill_exponent": 1,
            "normalized_adstock": True,
            "training_spend_min": float(training_spend.min()),
            "training_spend_max": float(training_spend.max()),
        }
        transformed.append(hill(stock, k))
        terminal[name] = float(stock[-1])
    step = 7 if dataset["frequency"] == "weekly" else 1
    x = design_matrix(np.column_stack(transformed), controls, np.arange(n), step)
    coefficients, solver = fit_ridge(x[warmup:cutoff], y[warmup:cutoff], m, request.ridge_alpha)
    prediction = x @ coefficients
    train_metrics = metrics(y[warmup:cutoff], prediction[warmup:cutoff])
    test_metrics = metrics(y[cutoff:], prediction[cutoff:])
    residual = y[warmup:cutoff] - prediction[warmup:cutoff]
    lag1 = float(np.corrcoef(residual[:-1], residual[1:])[0, 1]) if np.std(residual) > 0 else None
    if lag1 is not None and not np.isfinite(lag1):
        lag1 = None
    condition = float(np.linalg.cond(x[warmup:cutoff]))
    warnings = [
        *report["warnings"],
        "FIXED_SHAPE: decay and Hill multiplier supplied, not estimated",
        "NO_UNCERTAINTY: point estimates only; no causal identification or calibration",
        "CONDITIONAL_HOLDOUT: test predictions use observed test spend and controls",
        "ZERO_INITIAL_STATE: prehistory unknown; warmup only approximates its removal",
    ]
    if any(name.startswith("CONSTANT_COLUMN") for name in warnings):
        warnings.append("RANK_WARNING: constant regressors reduce identifiability")
    if lag1 is not None and abs(lag1) > 0.3:
        warnings.append("RESIDUAL_AUTOCORRELATION: absolute training lag-one correlation > 0.3")
    if not np.isfinite(condition) or condition > 1e8:
        warnings.append("ILL_CONDITIONED: regressors may not separate channel associations")
    if np.any(prediction < 0):
        warnings.append(
            "NEGATIVE_PREDICTIONS: linear baseline is not constrained; no clipping applied"
        )
    feature_names = [
        "intercept",
        *request.media_columns,
        "trend_years",
        "sin_year",
        "cos_year",
        *request.control_columns,
    ]
    result = {
        "schema_version": 1,
        "engine": "constrained-ridge-v1",
        "model_id": model_id,
        "dataset_id": request.dataset_id,
        "dataset_sha256": digest(dataset),
        "synthetic": dataset.get("synthetic") is True,
        "exploratory": True,
        "disclaimer": DISCLAIMER,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "versions": {p: version(p) for p in ("mmm-intelligence-mcp", "numpy", "scipy", "mcp")},
        "request": request.model_dump(mode="json"),
        "feature_names": feature_names,
        "coefficients": dict(zip(feature_names, coefficients.tolist())),
        "media_parameters": parameters,
        "solver": solver,
        "split": {
            "train_end": rows[cutoff - 1][request.date_column],
            "test_start": rows[cutoff][request.date_column],
            "train_rows": cutoff - warmup,
            "test_rows": n - cutoff,
            "warmup_rows": warmup,
            "refit_on_test": False,
        },
        "metrics": {
            "train": train_metrics,
            "test": test_metrics,
            "test_train_mean_baseline": metrics(
                y[cutoff:], np.full(n - cutoff, y[warmup:cutoff].mean())
            ),
        },
        "diagnostics": {
            "train_residual_lag1": lag1,
            "condition_number": condition if np.isfinite(condition) else None,
            "matrix_rank": int(np.linalg.matrix_rank(x[warmup:cutoff])),
        },
        "state": {
            "last_date": rows[-1][request.date_column],
            "history_periods": n,
            "step_days": step,
            "terminal_adstock": terminal,
            "last_controls": dict(zip(request.control_columns, controls[-1].tolist())),
            "reference_spend_per_period": dict(
                zip(request.media_columns, spend[-min(n, 13) :].mean(axis=0).tolist())
            ),
        },
        "units": dataset.get("units", {}),
        "warnings": warnings,
        "predictions": [
            {
                "date": rows[i][request.date_column],
                "observed": float(y[i]),
                "predicted": float(prediction[i]),
                "split": "train" if i < cutoff else "test",
            }
            for i in range(warmup, n)
        ],
    }
    if request.bootstrap_samples:
        if request.bootstrap_block_size > len(residual):
            raise MMMError("INVALID_BLOCK_SIZE", "Bootstrap block exceeds training observations")
        rng = np.random.default_rng(request.bootstrap_seed)
        residual = residual - residual.mean()
        draws = []
        block = request.bootstrap_block_size
        for _ in range(request.bootstrap_samples):
            starts = rng.integers(0, len(residual) - block + 1, math.ceil(len(residual) / block))
            sampled = np.concatenate([residual[s : s + block] for s in starts])[: len(residual)]
            b, _ = fit_ridge(
                x[warmup:cutoff], prediction[warmup:cutoff] + sampled, m, request.ridge_alpha
            )
            draws.append(b.tolist())
        result["coefficient_draws"] = draws
        result["uncertainty"] = {
            "method": "moving_block_residual_bootstrap",
            "samples": len(draws),
            "block_size": block,
            "seed": request.bootstrap_seed,
            "scope": "conditional mean; fixed shape and inputs; not causal or predictive noise",
        }
        result["warnings"] = [w for w in warnings if not w.startswith("NO_UNCERTAINTY")]
        result["warnings"].append(
            "CONDITIONAL_UNCERTAINTY: excludes shape, confounding and future input uncertainty"
        )
    return result
