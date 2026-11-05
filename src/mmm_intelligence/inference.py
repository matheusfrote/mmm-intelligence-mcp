"""Unpenalized conditional inference, separate from constrained point estimation.

Projection of a confidence set onto the assumed nonnegative parameter space
preserves its coverage whenever the original set covers the true parameter.
HC3/HAC are sandwich approximations, not exact finite-sample guarantees.
"""

import numpy as np
from scipy.stats import t


def fit_linear_inference(design, target, hac_lags=3):
    x, y = np.asarray(design, float), np.asarray(target, float)
    if (
        x.ndim != 2
        or y.shape != (len(x),)
        or x.shape[1] < 2
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or not np.all(x[:, 0] == 1)
        or not isinstance(hac_lags, int)
        or not 0 <= hac_lags < len(x)
    ):
        raise ValueError(
            "Finite design with intercept, matching target and bounded HAC lag required"
        )
    n, p = x.shape
    if n <= p + 1:
        return {"available": False, "reason": "insufficient_residual_degrees_of_freedom"}
    mean, scale = x.mean(axis=0), x.std(axis=0)
    mean[0], scale[0] = 0, 1
    scale[scale < 1e-12] = 1
    transform = np.diag(1 / scale)
    transform[0] -= mean / scale
    z = x @ transform
    u, singular, vt = np.linalg.svd(z, full_matrices=False)
    rank = int(np.sum(singular > singular[0] * max(z.shape) * np.finfo(float).eps))
    if rank < p:
        return {"available": False, "reason": "rank_deficient", "rank": rank, "features": p}
    inverse = (vt.T / singular) @ u.T
    beta = inverse @ y
    residual = y - z @ beta
    leverage = np.sum(u**2, axis=1)
    if np.max(leverage) >= 1 - 1e-8:
        return {"available": False, "reason": "extreme_leverage"}
    adjusted = residual / (1 - leverage)
    weighted_inverse = inverse * adjusted
    hc3 = weighted_inverse @ weighted_inverse.T
    scores = z * adjusted[:, None]
    meat = scores.T @ scores
    for lag in range(1, hac_lags + 1):
        cross = scores[lag:].T @ scores[:-lag]
        meat += (1 - lag / (hac_lags + 1)) * (cross + cross.T)
    bread = inverse @ inverse.T
    hac = bread @ meat @ bread
    return {
        "available": True,
        "point_estimator": "unpenalized_OLS",
        "coefficients": (transform @ beta).tolist(),
        "covariances": {
            "hc3": (transform @ hc3 @ transform.T).tolist(),
            "hac": (transform @ hac @ transform.T).tolist(),
        },
        "degrees_of_freedom": n - p,
        "hac_lags": hac_lags,
        "maximum_leverage": float(leverage.max()),
        "scope": "Fixed media shapes; HC3 requires independent/martingale errors, HAC weak dependence and sufficient history. No omitted-confounder protection.",
        "coverage_certified": False,
        "causal_identification": False,
    }


def linear_contrast(inference, contrast, *, nonnegative=False, covariance="hc3"):
    if not inference.get("available"):
        return {"available": False, "reason": inference["reason"]}
    vector = np.asarray(contrast, float)
    beta = np.asarray(inference["coefficients"])
    if (
        vector.shape != beta.shape
        or not np.isfinite(vector).all()
        or covariance not in {"hc3", "hac"}
    ):
        raise ValueError("Matching finite contrast and HC3/HAC covariance required")
    matrix = np.asarray(inference["covariances"][covariance])
    estimate = float(vector @ beta)
    se = float(np.sqrt(max(0, vector @ matrix @ vector)))
    radius = float(t.ppf(0.95, inference["degrees_of_freedom"]) * se)
    lower, upper = estimate - radius, estimate + radius
    if nonnegative:
        lower, upper = max(0, lower), max(0, upper)
    return {
        "available": True,
        "estimate": max(0, estimate) if nonnegative else estimate,
        "unprojected_estimate": estimate,
        "standard_error": se,
        "lower": lower,
        "upper": upper,
        "nominal_level": 0.9,
        "method": "projected_OLS_" + covariance if nonnegative else "OLS_" + covariance,
        "boundary_policy": "Monotone projection of the whole confidence set; conservative at zero"
        if nonnegative
        else "unrestricted contrast",
        "coverage_certified": False,
    }
