"""Versioned scientific evidence; numerical adequacy never establishes causality."""

import math
import platform
from datetime import datetime, timezone
from importlib.metadata import version

import numpy as np

from .diagnostics import classify_bayesian
from .errors import MMMError
from .schemas import ScientificProtocol
from .storage import digest


def status(failed, missing):
    return "failed" if failed else "inconclusive" if missing else "passed_for_protocol"


def sampling_assessment(model, protocol):
    """Shared primary/refit numerical, precision and predictive screens."""
    failed, missing = [], []
    diagnostics = model.get("diagnostics", {})
    mcmc = classify_bayesian(
        diagnostics, max_rhat=protocol.max_rhat, min_ess_per_chain=protocol.min_ess_per_chain
    )
    failed.extend(mcmc["failed_screens"])
    missing.extend(mcmc["missing_or_insufficient"])
    if diagnostics.get("draws", 0) < protocol.min_draws:
        missing.append("analytical_sampling_budget")
    evidence = model.get("scientific_diagnostics", {})
    if not evidence.get("available"):
        missing.append("mcse_and_chain_evidence")
    else:
        ratio = evidence.get("mcse_sd_ratio_max")
        if ratio is None or not math.isfinite(ratio) or evidence.get("undefined_mcse_count", 0):
            missing.append("mcse_undefined")
        if ratio is not None and math.isfinite(ratio) and ratio > protocol.max_mcse_sd_ratio:
            failed.append("mcse_exceeds_precision_policy")
        if not evidence.get("trace_series") or evidence.get("truncated"):
            missing.append("complete_chain_inspection")
    predictive = model.get("posterior_predictive_check", {})
    if predictive.get("scope") != "observed_outcome" or not predictive.get("available"):
        missing.append("observed_posterior_predictive_check")
    elif predictive.get("degenerate"):
        failed.append("degenerate_predictive_distribution")
    elif predictive.get("discrepancy_flags"):
        failed.append("predictive_discrepancy")
    raw_metrics = {
        **{
            k: diagnostics.get(k)
            for k in (
                "r_hat_max",
                "ess_bulk_min",
                "ess_tail_min",
                "divergences",
                "chains",
                "draws",
                "tune",
            )
        },
        "mcse_sd_ratio_max": evidence.get("mcse_sd_ratio_max"),
        "undefined_mcse_count": evidence.get("undefined_mcse_count"),
        "ppc_coverage_90": predictive.get("coverage_90"),
    }
    metrics = {
        k: v
        if isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
        else None
        for k, v in raw_metrics.items()
    }
    return {
        "status": status(failed, missing),
        "failed": failed,
        "missing": missing,
        "mcmc": mcmc,
        "metrics": metrics,
    }


def search_assessment(model):
    """Native Robyn objective flags and search budget, never MCMC."""
    failed, missing = [], []
    native = model.get("diagnostics", {})
    trace = native.get("optimization_trace")
    if not isinstance(trace, list) or not trace:
        missing.append("native_optimization_trace")
    else:
        if not {"NRMSE", "DECOMP.RSSD"}.issubset({row["error_type"] for row in trace}):
            missing.append("native_optimization_objectives")
        for objective in {row["error_type"] for row in trace}:
            last = max(
                (row for row in trace if row["error_type"] == objective),
                key=lambda row: float(row["cuts"]),
            )
            if last.get("flag_med") is not True or last.get("flag_sd") is not True:
                failed.append("native_search_convergence_warning")
                break
    if native.get("trials", 0) < 5 or native.get("iterations", 0) < 2000:
        missing.append("prespecified_search_budget")
    return {"status": status(failed, missing), "failed": failed, "missing": missing}


def classify_scientific(model, dataset, *, backend, protocol=None, stability=None, causal=None):
    """Classify the actual supplied evidence, preserving unavailable observations."""
    protocol = protocol or ScientificProtocol()
    lineage = digest(dataset) == model.get("dataset_sha256")
    operational = {
        "status": "passed"
        if lineage
        and (
            model.get("solver", {}).get("success") is True
            if backend == "ridge"
            else model.get("restore_verified") is True
        )
        else "failed",
        "scope": "Immutable dataset lineage and successful solver/native restoration only",
        "dataset_lineage_verified": lineage,
    }
    failed, missing = [], []
    if backend in {"ridge", "meta_robyn"}:
        mcmc = {"status": "not_applicable", "reason": f"{backend} is not MCMC"}
        if backend == "ridge":
            diagnostic = model.get("diagnostics", {})
            rank, count = (
                diagnostic.get("standardized_matrix_rank"),
                diagnostic.get("feature_count"),
            )
            if rank is None or count is None:
                missing.append("design_rank")
            elif rank < count:
                failed.append("rank_deficient")
            if model.get("coefficient_draws"):
                missing.append("conditional_interval_validation_unavailable")
        if not stability or stability.get("status") != "executed":
            missing.append("stability_and_regularization_or_search")
        elif stability.get("unstable"):
            failed.append("unstable_estimates")
        if backend == "meta_robyn":
            assessment = search_assessment(model)
            failed.extend(assessment["failed"])
            missing.extend(assessment["missing"])
        if backend != "ridge" and stability and not stability.get("estimate_consistency_available"):
            missing.append("native_effect_parameter_stability")
    else:
        assessment = sampling_assessment(model, protocol)
        failed.extend(assessment["failed"])
        missing.extend(assessment["missing"])
        mcmc = assessment["mcmc"]
        if not stability or stability.get("status") != "executed":
            missing.append("specification_sensitivity")
        elif stability.get("unstable"):
            failed.append("unstable_estimates")
        if stability and not stability.get("estimate_consistency_available"):
            missing.append("native_effect_parameter_stability")
    if backend != "ridge" and stability and stability.get("status") == "executed":
        if stability.get("diagnostics_status") == "failed":
            failed.append("refit_diagnostics_failed")
        elif stability.get("diagnostics_status") != "passed_for_protocol":
            missing.append("refit_diagnostics_incomplete")
    causal = causal or {
        "status": "simulation_only" if dataset.get("synthetic") is True else "not_assessed",
        "causal_identification": False,
        "reason": "Synthetic evidence cannot establish campaign effects"
        if dataset.get("synthetic") is True
        else "No independently assessed experiment or identification design supplied",
    }
    return {
        "operational": operational,
        "statistical": {
            "status": status(failed, missing),
            "failed": failed,
            "missing": missing,
            "mcmc": mcmc,
            "convergence_certified": False,
            "scope": "Screened numerical and sensitivity diagnostics; model correctness is not guaranteed",
        },
        "causal": causal,
        "business_recommendation_eligible": False,
    }


def provenance(model, dataset, backend, protocol):
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": protocol.model_dump(mode="json"),
        "dataset_sha256": digest(dataset),
        "model_sha256": digest(model),
        "configuration": model["request"],
        "effective_configuration": model.get("effective_configuration", model["request"]),
        "backend": backend,
        "python": platform.python_version(),
        "versions": {p: version(p) for p in ("mmm-intelligence-mcp", "numpy", "scipy")},
        "native_version": model.get("backend_version"),
        "native_training_versions": model.get("native_runtime_versions"),
        "training_identity": model.get("scientific_training_identity"),
        "seeds": protocol.seeds,
    }


def native_estimates(fitted):
    """Collect available native contribution metrics; missing values are not zero."""
    estimates = dict(fitted.get("native_estimates", {}))
    for row in fitted.get("native_decomposition", []):
        for field in ("xDecompAgg", "xDecompPerc", "roi_total"):
            value = row.get(field)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            ):
                estimates[field + ":" + row["rn"]] = value
    return estimates


def stability_study(service, model, dataset, backend, protocol):
    """Prespecified alternatives; holdout scores are reported, never used to select a winner."""
    from .refits import fit_or_reuse

    configurations = []
    if backend == "ridge":
        for alpha in protocol.regularization:
            configurations.append(
                {**model["request"], "ridge_alpha": alpha, "bootstrap_samples": 0}
            )
    else:
        configurations = [
            {
                **model["request"],
                "baseline": model["request"].get("baseline", "legacy"),
                "seed": seed,
            }
            for seed in protocol.seeds
        ]
        if backend in {"google_meridian", "pymc_marketing"}:
            if protocol.refit_draws is not None:
                configurations = [{**c, "draws": protocol.refit_draws} for c in configurations]
            configurations.extend(
                {**configurations[0], "baseline": baseline}
                for baseline in protocol.baseline_variants
            )
            configurations.extend(
                {**configurations[0], "prior_scale_multiplier": multiplier}
                for multiplier in protocol.prior_scale_multipliers
            )
    controls = model["request"]["control_columns"]
    if controls:
        configurations.append({**configurations[0], "control_columns": controls[1:]})
    runs, failures = [], []
    for configuration in configurations:
        try:
            fitted, reused = fit_or_reuse(service, backend, dataset, configuration)
            if backend == "ridge":
                estimates = {
                    c: fitted["coefficients"][c] for c in fitted["request"]["media_columns"]
                }
                prediction = [p["predicted"] for p in fitted["predictions"] if p["split"] == "test"]
                metrics = fitted["metrics"]["test"]
            else:
                estimates = native_estimates(fitted)
                prediction = fitted["test"]["mean"]
                metrics = fitted["test"].get("metrics", {})
            refit_assessment = {
                "status": "not_applicable",
                "reason": "Ridge solver preflight already enforced",
            }
            if backend == "meta_robyn":
                refit_assessment = search_assessment(fitted)
            elif backend in {"google_meridian", "pymc_marketing"}:
                refit_assessment = assess_refit(service, backend, fitted, protocol)
            runs.append(
                {
                    "model_id": fitted["model_id"],
                    "reused": reused,
                    "numerical_assessment": refit_assessment,
                    "training_identity": fitted.get("scientific_training_identity"),
                    "configuration": configuration,
                    "model_sha256": digest(fitted),
                    "estimates": estimates,
                    "test_prediction": prediction,
                    "test_metrics": metrics,
                    "optimization": fitted.get("diagnostics", {}),
                    "effective_configuration": fitted.get("effective_configuration", configuration),
                }
            )
        except MMMError as error:
            failures.append({"configuration": configuration, "code": error.code})
    spread = {}
    for name in sorted(set.intersection(*(set(r["estimates"]) for r in runs))) if runs else []:
        values = [r["estimates"][name] for r in runs]
        spread[name] = float(np.ptp(values) / max(np.max(np.abs(values)), 1e-12))
    predictive_spread = None
    if len(runs) >= 2 and len({len(r["test_prediction"]) for r in runs}) == 1:
        values = np.asarray([r["test_prediction"] for r in runs])
        predictive_spread = float(
            np.mean(np.ptp(values, axis=0)) / max(np.mean(np.abs(values)), 1e-12)
        )
    return {
        "status": "executed" if not failures and len(runs) >= 2 else "incomplete",
        "runs": runs,
        "failures": failures,
        "relative_estimate_spread": spread,
        "relative_predictive_spread": predictive_spread,
        "estimate_consistency_available": bool(spread),
        "diagnostics_status": "not_applicable"
        if backend == "ridge"
        else "failed"
        if any(r["numerical_assessment"]["status"] == "failed" for r in runs)
        else "inconclusive"
        if failures
        or not runs
        or any(r["numerical_assessment"]["status"] != "passed_for_protocol" for r in runs)
        else "passed_for_protocol",
        "unstable": any(v > protocol.max_relative_spread for v in spread.values())
        or predictive_spread is not None
        and predictive_spread > protocol.max_relative_spread,
        "policy_threshold": protocol.max_relative_spread,
        "winner": None,
        "acceptance_basis": "Prespecified relative estimate/prediction spread; independent seeds, regularization and omission of first control where available",
        "limitations": [
            "Omitting a control is a stress test, not a recommendation to remove a confounder",
            "Stable predictions can coexist with unidentified channel effects",
            "No prior-sensitivity certification; defaults and effective priors are recorded",
        ],
    }


def assess_refit(service, backend, fitted, protocol):
    from .integrations.bridge import execute

    if not protocol.collect_native:
        return {
            "status": "inconclusive",
            "missing": ["native_refit_diagnostics_not_requested"],
            "failed": [],
        }
    try:
        evidence = execute(
            service.store,
            backend,
            {"operation": "diagnose", "model": fitted, "request": {"media_multiplier": {}}},
        )
    except MMMError as exc:
        return {
            "status": "inconclusive",
            "missing": ["native_refit_diagnostics:" + exc.code],
            "failed": [],
        }
    return sampling_assessment({**fitted, **evidence}, protocol)


def run_protocol(service, request):
    """Read immutable state and write a separate versioned validation report."""
    backend, protocol = request.backend, request.scientific
    if backend == "ridge":
        from .schemas import ModelRequest

        model = service.get_model(ModelRequest(model_id=request.model_id))
        dataset = service.load_dataset(model["dataset_id"])
    else:
        model = service.store.read("backend_models", request.model_id)
        service.authorize(model)
        dataset = model["dataset"]
        service.authorize(dataset)
        if model["backend"] != backend:
            raise MMMError("BACKEND_MISMATCH", "Model belongs to another engine")
    if digest(dataset) != model["dataset_sha256"]:
        raise MMMError("LINEAGE_MISMATCH", "Scientific evaluation requires original data")
    original_provenance = provenance(model, dataset, backend, protocol)
    from .causal_validation import load_evidence

    causal = load_evidence(service, model, protocol)
    if backend in {"google_meridian", "pymc_marketing"} and protocol.collect_native:
        from .integrations.bridge import execute

        model = {
            **model,
            **execute(
                service.store,
                backend,
                {"operation": "diagnose", "model": model, "request": {"media_multiplier": {}}},
            ),
        }
    stability = (
        stability_study(service, model, dataset, backend, protocol)
        if protocol.refit
        else {"status": "not_requested", "reason": "No independent refits executed"}
    )
    result = {
        "schema_version": "scientific-v1",
        "model_id": request.model_id,
        "backend": backend,
        "synthetic": dataset["synthetic"],
        "provenance": original_provenance,
        "classifications": classify_scientific(
            model, dataset, backend=backend, protocol=protocol, stability=stability, causal=causal
        ),
        "diagnostics": model.get("diagnostics", {}),
        "scientific_diagnostics": model.get("scientific_diagnostics", {}),
        "posterior_predictive_check": model.get("posterior_predictive_check", {}),
        "native_diagnostic_versions": model.get("diagnostic_runtime_versions"),
        "stability": stability,
        "source_ids": causal["source_ids"],
        "dataset_id": model["dataset_id"],
        "warnings": [
            "No automatic causal or investment certification; missing evidence remains inconclusive"
        ],
    }
    from .canonical import bundle
    from .schemas import AnalysisRequest

    canonical = bundle(model, dataset, AnalysisRequest(model_id=request.model_id, backend=backend))
    result["heldout_evaluation"] = {
        "metrics": canonical["metrics"],
        "baseline_metrics": canonical["baseline_metrics"],
        "series": canonical["evaluation"],
    }
    if backend == "ridge" and protocol.refit:
        from .scientific import audit

        result["ridge_audit"] = audit(dataset, model, request, service.settings.max_rows)
    if protocol.monte_carlo is not None:
        from .monte_carlo import run_study

        result["monte_carlo"] = run_study(protocol.monte_carlo)
        assessment = result["monte_carlo"]["acceptance"]
        statistical = result["classifications"]["statistical"]
        statistical["status_before_interval_assessment"] = statistical["status"]
        statistical["uncertainty_validation"] = assessment
        if protocol.monte_carlo.interval_method == "legacy_percentile":
            statistical["missing"] = [
                v
                for v in statistical["missing"]
                if v != "conditional_interval_validation_unavailable"
            ]
        statistical["uncertainty_validation_scope"] = protocol.monte_carlo.interval_method
        statistical["failed"].extend("monte_carlo:" + v for v in assessment["failed"])
        statistical["missing"].extend("monte_carlo:" + v for v in assessment["missing"])
        statistical["status"] = status(statistical["failed"], statistical["missing"])
    if protocol.calibration is not None:
        from .causal_validation import calibrate_evidence

        result["calibration"] = calibrate_evidence(service, model, backend, protocol)
        result["source_ids"].append(protocol.calibration.experiment_result_id)
    if protocol.native_monte_carlo is not None:
        from .native_recovery import run_native_study

        result["native_monte_carlo"] = run_native_study(
            service, backend, protocol.native_monte_carlo
        )
        assessment = result["native_monte_carlo"]["acceptance"]
        statistical = result["classifications"]["statistical"]
        statistical["native_recovery_validation"] = assessment
        statistical["failed"].extend("native_recovery:" + v for v in assessment["failed"])
        statistical["missing"].extend("native_recovery:" + v for v in assessment["missing"])
        statistical["status"] = status(statistical["failed"], statistical["missing"])
    return service._growth_save("scientific_validation", result)
