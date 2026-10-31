"""Bounded native diagnostics. Imported inside the isolated engine runtime."""

import math

import numpy as np


def finite(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def parameter_means(variables):
    """Native posterior means for within-engine stability, not cross-engine ROAS."""
    result = {}
    for name, raw in variables.items():
        if "beta" in name or "roi" in name:
            means = np.asarray(raw, float).mean(axis=(0, 1)).reshape(-1)
            for index, value in enumerate(means):
                if not np.isfinite(value):
                    raise ValueError("Nonfinite native effect parameter")
                result[f"{name}[{index}]"] = float(value)
    return result


def native_estimates(idata):
    return parameter_means(
        {
            name: np.asarray(
                var.transpose("chain", "draw", *[d for d in var.dims if d not in {"chain", "draw"}])
            )
            for name, var in idata["posterior"].data_vars.items()
            if {"chain", "draw"}.issubset(var.dims)
            and "date" not in var.dims
            and "time" not in var.dims
        }
    )


def chain_report(statistics, variables):
    parameters, ratios, undefined = [], [], 0
    for row in statistics:
        item = {
            key: finite(row.get(key))
            for key in ("mean", "sd", "mcse_mean", "mcse_sd", "r_hat", "ess_bulk", "ess_tail")
        }
        item["parameter"] = str(row["parameter"])
        sd, mcse = item["sd"], item["mcse_mean"]
        ratio = mcse / sd if sd is not None and sd > 0 and mcse is not None and mcse >= 0 else None
        item["mcse_sd_ratio"] = ratio
        if ratio is None:
            undefined += 1
        else:
            ratios.append(ratio)
        parameters.append(item)
    traces, total = [], 0
    for name, raw in variables.items():
        values = np.asarray(raw, float)
        if values.ndim < 2 or values.shape[0] < 2 or values.shape[1] < 4:
            raise ValueError("Posterior must retain independent chain and draw dimensions")
        flat = values.reshape(values.shape[0], values.shape[1], -1)
        total += flat.shape[2]
        for i in range(min(flat.shape[2], max(0, 64 - len(traces)))):
            draw_indices = np.unique(
                np.linspace(0, flat.shape[1] - 1, min(128, flat.shape[1]), dtype=int)
            )
            series = flat[:, :, i]
            traces.append(
                {
                    "parameter": f"{name}[{i}]",
                    "draw_indices": draw_indices.tolist(),
                    "chains": series[:, draw_indices].tolist(),
                    "chain_means": series.mean(axis=1).tolist(),
                    "chain_sd": series.std(axis=1, ddof=1).tolist(),
                }
            )
    return {
        "available": bool(parameters and traces),
        "parameters": parameters,
        "mcse_sd_ratio_max": max(ratios) if ratios else None,
        "undefined_mcse_count": undefined,
        "trace_series": traces,
        "total_trace_parameters": total,
        "truncated": total > len(traces),
        "trace_scope": "Up to 128 actual unrounded draw positions per chain, at most 64 scalar parameters; visual review remains a human task",
        "diagnostics_use_full_draws": True,
        "convergence_certified": False,
    }


def collect_chains(idata, backend):
    posterior = idata["posterior"]
    variables = {}
    for name, var in posterior.data_vars.items():
        if (
            "date" not in var.dims
            and "time" not in var.dims
            and {"chain", "draw"}.issubset(var.dims)
        ):
            extra = [d for d in var.dims if d not in {"chain", "draw"}]
            variables[name] = np.asarray(var.transpose("chain", "draw", *extra))
    if backend == "pymc_marketing":
        from arviz_stats import summary
    else:
        from arviz import summary
    table = summary(idata, var_names=list(variables), kind="all", round_to="none")
    rows = [{"parameter": str(name), **row.to_dict()} for name, row in table.iterrows()]
    result = chain_report(rows, variables)
    result["method"] = (
        "Native ArviZ rank-normalized split R-hat, bulk/tail ESS, MCSE; full posterior"
    )
    result["excluded_time_dependent_variables"] = [
        name for name in posterior.data_vars if name not in variables
    ]
    return result


def predictive_check(samples, observed, dates):
    values, y = np.asarray(samples, float), np.asarray(observed, float)
    if (
        values.ndim != 2
        or values.shape[0] < 2
        or y.ndim != 1
        or not y.size
        or values.shape[1] != len(y)
        or len(dates) != len(y)
        or not np.isfinite(values).all()
        or not np.isfinite(y).all()
    ):
        raise ValueError(
            "PPC requires finite observed outcomes and matching observed-scale replicate draws"
        )
    lower, upper = np.quantile(values, [0.05, 0.95], axis=0)
    mean = values.mean(axis=0)
    p_mean = float(np.mean(values.mean(axis=1) >= y.mean()))
    p_sd = float(np.mean(values.std(axis=1) >= y.std()))
    residual = y - mean
    flags = []
    for key, value in (("mean_discrepancy", p_mean), ("dispersion_discrepancy", p_sd)):
        if value < 0.01 or value > 0.99:
            flags.append(key)
    return {
        "available": True,
        "scope": "observed_outcome",
        "evaluation_window": "held_out",
        "replicates": values.shape[0],
        "periods": len(y),
        "coverage_90": float(np.mean((y >= lower) & (y <= upper))),
        "mean_interval_width": float(np.mean(upper - lower)),
        "replicated_mean_tail_probability": p_mean,
        "replicated_sd_tail_probability": p_sd,
        "discrepancy_flags": flags,
        "degenerate": bool(np.all(values.std(axis=0) == 0)),
        "residual_lag1": float(np.corrcoef(residual[:-1], residual[1:])[0, 1])
        if len(y) > 2 and np.std(residual[:-1]) > 0 and np.std(residual[1:]) > 0
        else None,
        "series": [
            {
                "date": d,
                "observed": float(o),
                "mean": float(m),
                "lower": float(lo),
                "upper": float(hi),
            }
            for d, o, m, lo, hi in zip(dates, y, mean, lower, upper)
        ],
        "interpretation": "Descriptive holdout posterior predictive checks; time points are dependent, tail probabilities are not frequentist p-values; no automatic model approval",
        "causal_identification": False,
    }


def meridian_ppc(model, expected, observed, dates, cutoff, seed):
    """Draw Gaussian observations using Meridian's own inverse KPI transformer.

    This adapter is national: retain the single geo axis during inverse scaling.
    The mean is already on KPI scale, so only transform a centered noise contrast.
    """
    sigma = np.asarray(model.inference_data["posterior"]["sigma"], float).reshape(-1, 1, 1)
    rng = np.random.default_rng(seed)
    noise_scaled = rng.normal(size=(len(sigma), 1, len(dates))) * sigma
    zero = np.zeros_like(noise_scaled)
    noise = np.asarray(model.kpi_transformer.inverse(noise_scaled)) - np.asarray(
        model.kpi_transformer.inverse(zero)
    )
    values = np.asarray(expected).reshape(-1, len(dates)) + noise.reshape(-1, len(dates))
    result = predictive_check(values[:, cutoff:], observed[cutoff:], dates[cutoff:])
    result["generation"] = (
        "Meridian Gaussian observation model, native posterior sigma and inverse KPI transformer; national adapter"
    )
    result["seed"] = seed
    return result
