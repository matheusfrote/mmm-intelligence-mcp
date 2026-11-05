"""Known-truth recovery through real isolated workers; never substitute engines."""

import numpy as np

from .diagnostics import classify_bayesian
from .errors import MMMError
from .integrations.bridge import execute
from .monte_carlo import assess_study, generate_dgp, summarize_records
from .refits import fit_or_reuse
from .schemas import BackendRequest
from .storage import digest


def evaluate_effects(dates, channels, native_result, truth):
    """Validate native contracts against known DGP dates; never invent intervals."""
    if (
        not dates
        or len(set(dates)) != len(dates)
        or any(day not in truth["effect_by_date"][channels[0]] for day in dates)
    ):
        raise MMMError(
            "INVALID_NATIVE_EVIDENCE",
            "Native evaluation window is empty, duplicated or outside the known DGP",
        )
    effects = {}
    for channel in channels:
        try:
            native = native_result["effects"][channel]
            value = native.get("estimate")
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not np.isfinite(value)
            ):
                raise ValueError("Native effect estimate is not a finite scalar")
            if not isinstance(native["available"], bool):
                raise ValueError("Native availability is not a boolean")
            if native["available"] and (
                any(isinstance(native.get(key), bool) for key in ("lower", "upper"))
                or not np.isfinite([native.get("lower", np.nan), native.get("upper", np.nan)]).all()
                or native["lower"] > native["upper"]
            ):
                raise ValueError("Native confidence bounds are invalid")
        except (KeyError, TypeError, ValueError) as exc:
            raise MMMError("INVALID_NATIVE_EVIDENCE", "Native effect contract is invalid") from exc
        actual = float(np.mean([truth["effect_by_date"][channel][day] for day in dates]))
        effects[channel] = {
            **native,
            "truth": actual,
            "interval_available": native["available"],
            "covered": bool(native["available"] and native["lower"] <= actual <= native["upper"]),
        }
    return effects


def run_native_study(service, backend, config):
    if backend not in {"google_meridian", "pymc_marketing", "meta_robyn"}:
        raise MMMError("OPERATION_UNAVAILABLE", "Native recovery requires a native engine")
    if config.replications * len(config.scenarios) > 200:
        raise MMMError(
            "RESOURCE_LIMIT",
            "Use batches of at most 200 native fits; immutable refits survive retries",
        )
    seeds = np.random.SeedSequence(config.seed).spawn(config.replications * len(config.scenarios))
    records = []
    for scenario in config.scenarios:
        for replication in range(config.replications):
            child = seeds[len(records)]
            seed = int(child.generate_state(1)[0] % (2**31 - 1))
            dataset, truth = generate_dgp(config, seed, scenario)
            dataset_id = "recovery-data-" + digest(dataset)[:40]
            record = {
                "scenario": scenario,
                "replication": replication,
                "seed": seed,
                "seed_spawn_key": list(child.spawn_key),
                "dataset_sha256": digest(dataset),
            }
            try:
                if not service.store.path("datasets", dataset_id).is_file():
                    service.store.write("datasets", dataset_id, dataset)
                options = {
                    "backend": backend,
                    "dataset_id": dataset_id,
                    "draws": config.draws,
                    "tune": config.tune,
                    "chains": 4,
                    "seed": seed,
                    "baseline": "calendar",
                }
                if backend == "meta_robyn":
                    options.update(
                        robyn_trials=config.robyn_trials, robyn_iterations=config.robyn_iterations
                    )
                request = BackendRequest.model_validate(options)
                fitted, reused = fit_or_reuse(
                    service, backend, dataset, request.model_dump(mode="json")
                )
                effect_result = execute(
                    service.store,
                    backend,
                    {"operation": "effect", "model": fitted, "request": {"media_multiplier": {}}},
                )
                dates = fitted["test"]["dates"]
                effects = evaluate_effects(dates, request.media_columns, effect_result, truth)
                diagnostics = fitted["diagnostics"]
                numerical = {"status": "not_applicable", "reason": "Robyn is not MCMC"}
                predictive = {}
                if backend != "meta_robyn":
                    diagnostic_result = execute(
                        service.store,
                        backend,
                        {
                            "operation": "diagnose",
                            "model": fitted,
                            "request": {"media_multiplier": {}},
                        },
                    )
                    diagnostics = diagnostic_result["diagnostics"]
                    numerical = classify_bayesian(diagnostics)
                    predictive = {
                        k: v
                        for k, v in diagnostic_result["posterior_predictive_check"].items()
                        if k != "series"
                    }
                    numerical["mcse_sd_ratio_max"] = diagnostic_result[
                        "scientific_diagnostics"
                    ].get("mcse_sd_ratio_max")
                    numerical["undefined_mcse_count"] = diagnostic_result[
                        "scientific_diagnostics"
                    ].get("undefined_mcse_count")
                record.update(
                    status="executed",
                    model_id=fitted["model_id"],
                    model_sha256=digest(fitted),
                    reused=reused,
                    configuration=request.model_dump(mode="json"),
                    evaluation_dates=dates,
                    effects=effects,
                    diagnostics=diagnostics,
                    numerical_screen=numerical,
                    posterior_predictive_check=predictive,
                    native_version=fitted["backend_version"],
                    native_runtime_versions=fitted["native_runtime_versions"],
                    training_identity=fitted["scientific_training_identity"],
                    effective_configuration=fitted["effective_configuration"],
                    metrics=fitted["test"].get("metrics", {}),
                )
            except MMMError as exc:
                record.update(status="failed", code=exc.code, failure_kind="execution")
            records.append(record)
    summaries = summarize_records(records, config.scenarios, config.interval_method)
    result = {
        "schema_version": "native-recovery-v1",
        "backend": backend,
        "synthetic": True,
        "configuration": config.model_dump(mode="json"),
        "attempted": len(records),
        "replications": records,
        "summaries": summaries,
        "operational": {
            "all_executed": all(r["status"] == "executed" for r in records),
            "failures": sum(r["status"] != "executed" for r in records),
        },
        "causal_identification": False,
        "limitations": [
            "Reference DGP is fixed Hill: Logistic PyMC is a deliberate functional misspecification; finite native adstock also differs from the infinite reference",
            "Each engine is evaluated on its declared effective holdout dates, recorded explicitly; windows must be harmonized before cross-engine comparisons",
            "Positive continuous priors may exclude the exact zero boundary; posterior credible sets are not automatically frequentist confidence sets",
            "Robyn native search supplies point effects; search quantiles are not sampling uncertainty and coverage stays unavailable",
            "Small studies cannot certify coverage; execution failures remain in attempted denominators",
            "Synthetic results never establish effects in real markets",
        ],
    }
    return assess_native_study(result, backend, config)


def assess_native_study(result, backend, config):
    """Screen recorded evidence independently of the workers that generated it."""
    records = result["replications"]
    expected = {"missing_target": "DATASET_INVALID", "constant_spend": "UNIDENTIFIABLE_MEDIA"}
    rejected = sum(
        r["status"] == "failed" and r.get("code") == expected.get(r["scenario"], "")
        for r in records
    )
    unexpected = sum(r["status"] == "failed" for r in records) - rejected
    result["operational"].update(
        expected_rejections=rejected,
        unexpected_failures=unexpected,
        protocol_executed=unexpected == 0,
        scope="Actual fits and explicit rejection of prespecified invalid designs; all attempts remain in denominators",
    )
    result["acceptance"] = assess_study(result, config)
    fitted_ids = [r["model_id"] for r in records if r["status"] == "executed"]
    if len(fitted_ids) != len(set(fitted_ids)):
        result["acceptance"]["missing"].append("non_independent_replicates")
    if unexpected:
        result["acceptance"]["missing"].append("incomplete_native_execution")
        result["acceptance"]["failed"] = [
            v for v in result["acceptance"]["failed"] if not v.startswith("core_estimation_failure")
        ]
    unreliable = [
        r
        for r in records
        if r.get("numerical_screen", {}).get("status")
        not in {"adequate_for_screened_diagnostics", "not_applicable", None}
    ]
    if unreliable:
        result["acceptance"]["missing"].append("native_numerical_adequacy_unresolved")
    for record in records:
        screen = record.get("numerical_screen", {})
        if screen.get("status") == "inadequate":
            result["acceptance"]["failed"].append("native_mcmc_failed:" + record["model_id"])
        ratio = screen.get("mcse_sd_ratio_max")
        if record.get("status") == "executed" and backend != "meta_robyn" and ratio is None:
            result["acceptance"]["missing"].append("missing_native_mcse:" + record["model_id"])
        if ratio is not None and ratio > 0.05:
            result["acceptance"]["failed"].append("native_mcse_failed:" + record["model_id"])
        if screen.get("undefined_mcse_count"):
            result["acceptance"]["missing"].append("undefined_native_mcse:" + record["model_id"])
        if record.get("posterior_predictive_check", {}).get("discrepancy_flags"):
            result["acceptance"]["failed"].append(
                "native_predictive_discrepancy:" + record["model_id"]
            )
        if record.get("status") == "executed" and backend == "meta_robyn":
            trace = record["diagnostics"].get("optimization_trace", [])
            if not trace:
                result["acceptance"]["missing"].append(
                    "missing_native_optimization_trace:" + record["model_id"]
                )
            else:
                if not {"NRMSE", "DECOMP.RSSD"}.issubset({row["error_type"] for row in trace}):
                    result["acceptance"]["missing"].append(
                        "missing_native_optimization_objectives:" + record["model_id"]
                    )
                for objective in {row["error_type"] for row in trace}:
                    last = max(
                        (row for row in trace if row["error_type"] == objective),
                        key=lambda row: float(row["cuts"]),
                    )
                    if last.get("flag_med") is not True or last.get("flag_sd") is not True:
                        result["acceptance"]["failed"].append(
                            "native_search_warning:" + record["model_id"] + ":" + objective
                        )
    result["acceptance"]["status"] = (
        "failed"
        if result["acceptance"]["failed"]
        else "inconclusive"
        if result["acceptance"]["missing"]
        else "passed_for_studied_DGPs"
    )
    return result
