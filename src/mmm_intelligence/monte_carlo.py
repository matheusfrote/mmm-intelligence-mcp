"""Known-truth repeated DGPs; conditional Ridge intervals are not Bayesian intervals."""

from datetime import date, timedelta
from importlib.metadata import version

import numpy as np
from scipy.stats import norm

from .datasets import MEDIA, validate
from .errors import MMMError
from .experiments import wilson
from .inference import linear_contrast
from .modeling import adstock, hill, train
from .schemas import TrainRequest
from .storage import digest


def generate_dgp(config, seed, scenario):
    rng = np.random.default_rng(seed)
    n = config.periods
    cutoff = n - int(np.ceil(n * 0.2))
    time = np.arange(n)
    latent = np.empty(n)
    state = 0.0
    for i in range(n):
        state = 0.6 * state + rng.normal()
        latent[i] = state
    spend = rng.uniform(300, 2500, (n, 3))
    if scenario == "constant_spend":
        spend[:] = 1000
    if scenario == "collinear":
        spend[:, 1] = spend[:, 0]
    if scenario == "omitted_confounder":
        spend[:, 0] *= np.exp(0.3 * latent)
    if scenario == "weak_signal":
        spend = 1000 + 0.001 * (spend - 1000)
    price = rng.normal(1, 0.05, n)
    promotion = rng.binomial(1, 0.2, n)
    decay = 0.85 if scenario == "misspecified_adstock" else 0.5
    beta = np.array([2000.0, 1500.0, 1000.0])
    if scenario == "null_effect":
        beta *= 0
    stocks = np.column_stack([adstock(spend[:, j], decay) for j in range(3)])
    half = np.median(stocks[8:cutoff], axis=0)
    media = np.column_stack([hill(stocks[:, j], half[j]) for j in range(3)])
    baseline = (
        7000
        + 300 * np.sin(2 * np.pi * time * 7 / 365.25)
        + 2 * time
        - 1200 * (price - 1)
        + 300 * promotion
    )
    mean = baseline + media @ beta
    if scenario == "omitted_confounder":
        mean += 800 * latent
    scale = np.ones(n)
    if scenario == "tracking_break":
        scale[cutoff:] = 1.4
    noise = rng.standard_t(3, n) * 120 if scenario == "heavy_tailed" else rng.normal(0, 120, n)
    observed = (mean + noise) * scale
    dataset = {
        "schema_version": 1,
        "synthetic": True,
        "source": "scientific-dgp-v1",
        "frequency": "weekly",
        "target_type": "revenue",
        "seed": int(seed),
        "units": {"spend": "synthetic_currency_per_period", "target": "synthetic_revenue"},
        "data_context": {
            "source_reference": "scientific-dgp-v1",
            "kpi_definition": "constructed outcome",
        },
        "rows": [
            {
                "date": (date(2020, 1, 6) + timedelta(weeks=i)).isoformat(),
                "revenue": float(observed[i]),
                "price_index": float(price[i]),
                "promotion": int(promotion[i]),
                **{c: float(spend[i, j]) for j, c in enumerate(MEDIA)},
            }
            for i in range(n)
        ],
    }
    effect = {
        c: float(
            np.mean(
                (hill(stocks[cutoff:, j] * 1.1, half[j]) - media[cutoff:, j])
                * beta[j]
                * scale[cutoff:]
            )
        )
        for j, c in enumerate(MEDIA)
    }
    if scenario == "missing_target":
        dataset["rows"][-1]["revenue"] = None
    return dataset, {
        "effect": effect,
        "effect_by_date": {
            c: dict(
                zip(
                    [r["date"] for r in dataset["rows"]],
                    ((hill(stocks[:, j] * 1.1, half[j]) - media[:, j]) * beta[j] * scale).tolist(),
                )
            )
            for j, c in enumerate(MEDIA)
        },
        "decay": decay,
        "half_saturation": half.tolist(),
        "beta": beta.tolist(),
        "scenario": scenario,
        "estimand": "heldout_mean_outcome_difference_for_10pct_increase_to_one_channel_over_entire_history",
        "evaluation_dates": [r["date"] for r in dataset["rows"][cutoff:]],
    }


def run_study(config):
    if config.replications * len(config.scenarios) * config.bootstrap_samples > 100000:
        raise MMMError(
            "RESOURCE_LIMIT",
            "Split the Monte Carlo protocol into batches of at most 100000 bootstrap fits",
        )
    roots = np.random.SeedSequence(config.seed).spawn(config.replications * len(config.scenarios))
    records = []
    for scenario in config.scenarios:
        for replication in range(config.replications):
            child = roots[len(records)]
            seed = int(child.generate_state(1)[0] % (2**31 - 1))
            dataset, truth = generate_dgp(config, seed, scenario)
            record = {
                "scenario": scenario,
                "replication": replication,
                "seed": seed,
                "seed_spawn_key": list(child.spawn_key),
                "dataset_sha256": digest(dataset),
                "truth": truth,
            }
            spec = TrainRequest(
                dataset_id="monte-carlo",
                ridge_alpha=0.1,
                bootstrap_samples=config.bootstrap_samples,
                bootstrap_seed=seed,
                adstock_decay=0.5,
                saturation_multiplier=1.0,
            )
            try:
                quality = validate(dataset, spec, 100000)
                if not quality["valid"]:
                    raise MMMError("DATASET_INVALID", "; ".join(quality["issues"]))
                fitted = train(dataset, spec, "monte-carlo", quality)
                cutoff = len(dataset["rows"]) - fitted["split"]["test_rows"]
                effects = {}
                for c in MEDIA:
                    parameter = fitted["media_parameters"][c]
                    stock = adstock([r[c] for r in dataset["rows"]], parameter["decay"])
                    contrast = float(
                        np.mean(
                            hill(stock[cutoff:] * 1.1, parameter["half_saturation"])
                            - hill(stock[cutoff:], parameter["half_saturation"])
                        )
                    )
                    index = fitted["feature_names"].index(c)
                    estimates = np.asarray(fitted["coefficient_draws"])[:, index] * contrast
                    low, high = np.quantile(estimates, [0.05, 0.95])
                    alternatives = {
                        "legacy_percentile": {
                            "available": True,
                            "lower": float(low),
                            "upper": float(high),
                        }
                    }
                    vector = np.zeros(len(fitted["feature_names"]))
                    vector[index] = contrast
                    for method in ("hc3", "hac"):
                        alternatives["projected_" + method] = linear_contrast(
                            fitted["linear_inference"], vector, nonnegative=True, covariance=method
                        )
                    chosen = alternatives[config.interval_method]
                    effects[c] = {
                        "truth": truth["effect"][c],
                        "estimate": fitted["coefficients"][c] * contrast,
                        "lower": chosen.get("lower"),
                        "upper": chosen.get("upper"),
                        "interval_available": chosen["available"],
                        "interval_reason": chosen.get("reason"),
                        "alternatives": alternatives,
                        "covered": bool(
                            chosen["available"]
                            and chosen["lower"] <= truth["effect"][c] <= chosen["upper"]
                        ),
                    }
                record.update(
                    status="executed",
                    effects=effects,
                    configuration=spec.model_dump(mode="json"),
                    rank_deficient=fitted["diagnostics"]["standardized_matrix_rank"]
                    < fitted["diagnostics"]["feature_count"],
                    solver=fitted["solver"],
                    metrics=fitted["metrics"]["test"],
                )
            except MMMError as error:
                record.update(
                    status="failed", code=error.code, configuration=spec.model_dump(mode="json")
                )
            records.append(record)
    summaries = summarize_records(records, config.scenarios, config.interval_method)
    result = {
        "schema_version": "monte-carlo-v2",
        "backend": "ridge",
        "synthetic": True,
        "configuration": config.model_dump(mode="json"),
        "attempted": len(records),
        "versions": {p: version(p) for p in ("numpy", "scipy", "mmm-intelligence-mcp")},
        "replications": records,
        "summaries": summaries,
        "method_comparisons": [
            row
            for method in ("legacy_percentile", "projected_hc3", "projected_hac")
            for row in summarize_records(records, config.scenarios, method)
        ],
        "causal_identification": False,
        "limitations": [
            "Legacy conditional constrained bootstrap retained for comparison; not repaired by relabeling",
            "Projected HC3/HAC sets use unpenalized full-rank inference with fixed shapes, not a Bayesian posterior",
            "HC3 assumes independent/martingale errors; HAC requires weak dependence and sufficient history",
            "No sandwich correction identifies omitted confounders or repairs tracking breaks",
            "Rank-deficient designs retain point results but refuse effect intervals",
            "Failures remain in attempted denominators; interval coverage counts available intervals only",
            "Synthetic recovery cannot establish effects in real campaigns",
        ],
    }
    result["acceptance"] = assess_study(result, config)
    return result


def summarize_records(records, scenarios, method):
    summaries = []
    for scenario in scenarios:
        selected = [r for r in records if r["scenario"] == scenario]
        successful = [r for r in selected if r["status"] == "executed"]
        for c in MEDIA:
            errors = np.asarray(
                [r["effects"][c]["estimate"] - r["effects"][c]["truth"] for r in successful]
            )
            count = len(errors)
            intervals = [
                (
                    r["effects"][c],
                    r["effects"][c].get("alternatives", {}).get(method, r["effects"][c]),
                )
                for r in successful
            ]
            available = [
                (effect, interval)
                for effect, interval in intervals
                if interval.get("available", interval.get("interval_available", True))
            ]
            interval_count = len(available)
            covered = sum(
                interval["lower"] <= effect["truth"] <= interval["upper"]
                for effect, interval in available
            )
            coverage = covered / interval_count if interval_count else None
            summaries.append(
                {
                    "scenario": scenario,
                    "channel": c,
                    "attempted": len(selected),
                    "successful": count,
                    "interval_method": method,
                    "intervals_available": interval_count,
                    "mean_interval_width": float(
                        np.mean(
                            [interval["upper"] - interval["lower"] for _, interval in available]
                        )
                    )
                    if interval_count
                    else None,
                    "failed": len(selected) - count,
                    "bias": float(errors.mean()) if count else None,
                    "bias_mcse": float(errors.std(ddof=1) / np.sqrt(count)) if count > 1 else None,
                    "rmse": float(np.sqrt(np.mean(errors**2))) if count else None,
                    "interval_coverage": coverage,
                    "coverage_mcse": float(np.sqrt(coverage * (1 - coverage) / interval_count))
                    if interval_count
                    else None,
                    "coverage_interval_95": list(
                        wilson(coverage, interval_count, 1.959963984540054)
                    )
                    if interval_count
                    else None,
                    "nominal_coverage": 0.9,
                    "rank_deficient_runs": sum(r.get("rank_deficient", False) for r in successful),
                }
            )
    return summaries


def assess_study(study, config):
    """Assess prespecified core scenarios, retaining adverse scenarios separately.

    Bonferroni-adjusted Wilson bounds screen undercoverage across core channel
    estimands. Bias/RMSE tolerances are explicit KPI-unit choices, never inferred
    from fitted R2 or silently optimized from observed study results.
    """
    core = [
        row for row in study["summaries"] if row["scenario"] in {"well_specified", "null_effect"}
    ]
    failed, missing, undercoverage, checks = [], [], [], []
    if {row["scenario"] for row in core} != {"well_specified", "null_effect"}:
        missing.append("core_scenarios_missing")
    if config.max_absolute_bias is None:
        missing.append("absolute_bias_tolerance_missing")
    if config.max_rmse is None:
        missing.append("rmse_tolerance_missing")
    z = float(norm.isf(0.05 / (2 * max(1, len(core)))))
    target = 0.9 - config.coverage_tolerance
    for row in core:
        key = row["scenario"] + ":" + row["channel"]
        if row["failed"]:
            failed.append("core_estimation_failure:" + key)
        count, coverage = (
            row.get("intervals_available", 0),
            row["interval_coverage"],
        )
        if count < row["successful"]:
            missing.append("incomplete_interval_availability:" + key)
        if count < config.minimum_replications_for_assessment or coverage is None:
            missing.append("insufficient_replications_or_intervals:" + key)
            continue
        lower, upper = wilson(coverage, count, z)
        checks.append(
            {
                "estimand": key,
                "successful": row["successful"],
                "intervals_available": count,
                "coverage": coverage,
                "simultaneous_coverage_bounds": [lower, upper],
                "minimum_coverage_policy": target,
            }
        )
        if upper < target:
            undercoverage.append(key)
            failed.append("interval_undercoverage:" + key)
        elif lower < target:
            missing.append("coverage_precision_inconclusive:" + key)
        if config.max_absolute_bias is not None and abs(row["bias"]) > config.max_absolute_bias:
            failed.append("bias_exceeds_policy:" + key)
        if config.max_rmse is not None and row["rmse"] > config.max_rmse:
            failed.append("rmse_exceeds_policy:" + key)
    return {
        "status": "failed" if failed else "inconclusive" if missing else "passed_for_studied_DGPs",
        "failed": failed,
        "missing": missing,
        "undercoverage": undercoverage,
        "coverage_checks": checks,
        "policy": {
            "core_scenarios": ["well_specified", "null_effect"],
            "minimum_replications": config.minimum_replications_for_assessment,
            "require_intervals_for_all_successful_fits": True,
            "coverage_tolerance": config.coverage_tolerance,
            "max_absolute_bias": config.max_absolute_bias,
            "max_rmse": config.max_rmse,
            "coverage_family_size": len(core),
            "family_alpha": 0.05,
        },
        "causal_identification": False,
        "scope": "Core DGP conditional-interval screening only; inspect all adverse scenarios, failures and width; cannot certify real effects",
    }
