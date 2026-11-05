"""Bounded native diagnostics. Imported inside the isolated engine runtime."""

import math
from datetime import date

import numpy as np


def meridian_sampler_options(request):
    """Translate the public acceptance target into Meridian's documented NUTS API."""
    from immutabledict import immutabledict

    return {
        "dual_averaging_kwargs": immutabledict(
            target_accept_prob=request.get("target_accept", 0.85)
        ),
        "max_tree_depth": 8,
    }


def compressed_netcdf_encoding(idata):
    """Losslessly compress every numeric array; retain all groups, chains and draws."""
    return {
        group.path: {
            name: {"zlib": True, "complevel": 4, "shuffle": True}
            for name, variable in group.data_vars.items()
            if variable.ndim and variable.dtype.kind in "fiu"
        }
        for group in idata.subtree
    }


def calendar_design(rows, date_column, *, seasonal=False, policy=None):
    policy = policy or {
        "origin": rows[0][date_column],
        "columns": ["mmm_trend_years", *(["mmm_sin_year", "mmm_cos_year"] if seasonal else [])],
    }
    origin = date.fromisoformat(policy["origin"])
    output = []
    for row in rows:
        if set(policy["columns"]) & set(row):
            raise ValueError("Reserved native calendar column already present")
        years = (date.fromisoformat(row[date_column]) - origin).days / 365.25
        values = [years, math.sin(2 * math.pi * years), math.cos(2 * math.pi * years)]
        output.append({**row, **dict(zip(policy["columns"], values))})
    return output, policy


def scale_controls(rows, columns, cutoff, policy=None):
    if policy is None:
        policy = {}
        for name in columns:
            values = np.asarray([row[name] for row in rows[:cutoff]], float)
            policy[name] = {"mean": float(values.mean()), "scale": max(float(values.std()), 1e-12)}
    output = [
        {
            **row,
            **{name: (row[name] - spec["mean"]) / spec["scale"] for name, spec in policy.items()},
        }
        for row in rows
    ]
    return output, policy


def verified_fixed(variables, fixed):
    result = {}
    for name, declaration in (fixed or {}).items():
        if name not in variables:
            continue
        values = np.asarray(variables[name], float)
        if not np.isfinite(values).all() or not np.allclose(
            values, declaration["value"], rtol=0, atol=1e-12
        ):
            raise ValueError("Posterior disagrees with declared fixed parameter: " + name)
        result[name] = {**declaration, "verified_against_posterior": True}
    return result


def meridian_fixed(model):
    """Use native declared deterministic priors, never infer fixing from zero SD."""
    fixed = {}
    for name in model.inference_data["posterior"].data_vars:
        if model.prior_broadcast.has_deterministic_param(name):
            prior = getattr(model.prior_broadcast, name).distribution
            fixed[name] = {
                "value": np.asarray(prior.loc).tolist(),
                "basis": "Native broadcast Deterministic prior",
            }
    if model.is_national:
        fixed["tau_g"] = {
            "value": 0,
            "basis": "Native national model reference geo is fixed at zero",
        }
    variables = {
        name: np.asarray(var) for name, var in model.inference_data["posterior"].data_vars.items()
    }
    return verified_fixed(variables, fixed)


def finite(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def paired_effect(baseline, scenario, cutoff):
    baseline, scenario = np.asarray(baseline, float), np.asarray(scenario, float)
    if (
        baseline.ndim != 2
        or baseline.shape != scenario.shape
        or not 0 <= cutoff < baseline.shape[1]
        or not np.isfinite(baseline).all()
        or not np.isfinite(scenario).all()
    ):
        raise ValueError("Matching finite joint posterior means and holdout required")
    effects = (scenario[:, cutoff:] - baseline[:, cutoff:]).mean(axis=1)
    lower, upper = np.quantile(effects, [0.05, 0.95])
    return {
        "estimate": float(effects.mean()),
        "lower": float(lower),
        "upper": float(upper),
        "available": True,
        "interval_type": "posterior_conditional_effect",
        "draws": len(effects),
        "estimand": "heldout_mean_outcome_difference_for_10pct_increase_to_one_channel_over_entire_history",
        "causal_identification": False,
    }


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


def chain_report(statistics, variables, fixed=None):
    fixed = verified_fixed(variables, fixed)
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
        is_fixed = str(row["parameter"]).split("[", 1)[0] in fixed
        item["diagnostic_status"] = "not_applicable_fixed" if is_fixed else "sampled"
        if ratio is None and not is_fixed:
            undefined += 1
        elif ratio is not None and not is_fixed:
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
        "fixed_parameters": fixed,
        "mcse_sd_ratio_max": max(ratios) if ratios else None,
        "undefined_mcse_count": undefined,
        "trace_series": traces,
        "total_trace_parameters": total,
        "truncated": total > len(traces),
        "trace_scope": "Up to 128 actual unrounded draw positions per chain, at most 64 scalar parameters; visual review remains a human task",
        "diagnostics_use_full_draws": True,
        "convergence_certified": False,
    }


def collect_chains(idata, backend, fixed=None):
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
    result = chain_report(rows, variables, fixed)
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
