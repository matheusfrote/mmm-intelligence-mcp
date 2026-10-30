"""Explicit numerical screens, distinct from identification or business validity."""

import math

import numpy as np

ABSTENTION = (
    "Não há evidência suficiente para sustentar uma recomendação de investimento "
    "confiável com os dados e as condições atuais."
)


def classify_bayesian(diagnostics: dict, *, max_rhat=1.01, min_ess_per_chain=100) -> dict:
    if not 1 < max_rhat <= 1.2 or not 10 <= min_ess_per_chain <= 10000:
        raise ValueError("Invalid diagnostic policy")
    missing, failures = [], []
    required = (
        "chains",
        "draws",
        "tune",
        "r_hat_max",
        "ess_bulk_min",
        "ess_tail_min",
        "divergences",
        "r_hat_undefined_count",
        "ess_bulk_undefined_count",
        "ess_tail_undefined_count",
    )
    for key in required:
        value = diagnostics.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            missing.append(key)
    for key in ("r_hat_undefined_count", "ess_bulk_undefined_count", "ess_tail_undefined_count"):
        if key not in missing and diagnostics[key] > 0:
            missing.append(key + ":undefined_parameters")
    checks = {"r_hat_max": lambda v: v >= max_rhat, "divergences": lambda v: v != 0}
    for key, fails in checks.items():
        if key not in missing and fails(diagnostics[key]):
            failures.append(key)
    chains = diagnostics.get("chains")
    if "chains" not in missing and isinstance(chains, (int, float)):
        if chains < 4:
            missing.append("fewer_than_four_chains")
        for key in ("ess_bulk_min", "ess_tail_min"):
            if key not in missing and diagnostics[key] < min_ess_per_chain * chains:
                failures.append(key)
    for key in ("draws", "tune"):
        if key not in missing and diagnostics[key] < 400:
            missing.append(key + ":short_run")
    status = (
        "not_estimable"
        if diagnostics.get("estimation_failed")
        else "inadequate"
        if failures
        else "inconclusive"
        if missing
        else "adequate_for_screened_diagnostics"
    )
    return {
        "status": status,
        "failed_screens": failures,
        "missing_or_insufficient": missing,
        "policy": {
            "max_rhat_exclusive": max_rhat,
            "minimum_ess_per_chain": min_ess_per_chain,
            "minimum_chains": 4,
            "minimum_draws_and_tune_screen": 400,
        },
        "reference": "https://mc-stan.org/learn-stan/diagnostics-warnings.html",
        "scope": "Rank R-hat, bulk/tail ESS and divergences only; inspect mixing, PPC, priors and identification separately. Sample-count screens are operational, not universal guarantees.",
        "business_recommendation_eligible": False,
        "convergence_certified": False,
    }


def interval_coverage(truth, lower, upper, estimand: str) -> dict:
    actual, lo, hi = (np.asarray(v, float) for v in (truth, lower, upper))
    if (
        actual.ndim != 1
        or not actual.size
        or actual.shape != lo.shape
        or lo.shape != hi.shape
        or not np.isfinite([actual, lo, hi]).all()
        or (lo > hi).any()
        or estimand not in {"conditional_mean", "observed", "parameter"}
    ):
        raise ValueError("Finite matching vectors, ordered bounds and explicit estimand required")
    covered = (actual >= lo) & (actual <= hi)
    return {
        "estimand": estimand,
        "count": actual.size,
        "covered": int(covered.sum()),
        "empirical_coverage": float(covered.mean()),
        "mean_width": float((hi - lo).mean()),
        "coverage_certified": False,
        "scope": "Descriptive frequency for the supplied experiment; dependence and Monte Carlo error require study",
    }
