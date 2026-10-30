"""Comparable evidence without flattening distinct engine semantics."""

import numpy as np

from .diagnostics import ABSTENTION, classify_bayesian
from .errors import MMMError
from .modeling import metrics
from .scientific import decision_support
from .storage import digest


def capabilities(backend):
    future = backend in {"ridge", "pymc_marketing"}
    return {
        "training": {"available": True, "runtime": "base" if backend == "ridge" else "optional"},
        "historical_evaluation": {"available": True},
        "future_projection": {
            "available": future,
            "reason": "Explicit future plan and controls, conditional on fixed fitted parameters"
            if future
            else "Adapter exposes historical responses only; future baseline/carryover semantics not implemented and verified",
        },
        "optimization": {
            "available": backend == "ridge",
            "reason": "Constrained concave Hill-one candidate"
            if backend == "ridge"
            else "Native optimizer integration and uncertainty propagation not verified; no Ridge fallback",
        },
        "calibration": {
            "available": backend == "ridge",
            "reason": "Conditional bootstrap reweighting only; not a full experimental refit",
        },
        "multigeography": {"available": False, "reason": "Current API is one national time series"},
        "causal_recommendation": {"available": False, "reason": ABSTENTION},
    }


def require_operation(backend, operation):
    """An unavailable adapter never silently substitutes another statistical engine."""
    capability = capabilities(backend)[operation]
    if not capability["available"]:
        raise MMMError(
            "OPERATION_UNAVAILABLE",
            capability["reason"]
            + ". Select Ridge explicitly for its constrained exploratory optimizer, or use the native package with its own validated allocation design.",
        )


def bundle(model, dataset, request):
    if digest(dataset) != model["dataset_sha256"]:
        raise MMMError("LINEAGE_MISMATCH", "Model and dataset lineage differ")
    backend = request.backend
    req = model["request"]
    rows = dataset["rows"]
    if backend == "ridge":
        prediction = [dict(p) for p in model["predictions"] if p["split"] == "test"]
        first_test = prediction[0]["date"]
        train_dates = [
            r[req["date_column"]]
            for r in rows[req["warmup_periods"] :]
            if r[req["date_column"]] < first_test
        ]
        interval = model.get("uncertainty", {"method": "unavailable"})
        framework_version = model.get("versions", {})
        support = decision_support(model)
        assessment = {"status": "not_applicable", "reason": "Ridge is not MCMC"}
    else:
        if model["backend"] != backend:
            raise MMMError("BACKEND_MISMATCH", "Model belongs to a different backend")
        test = model["test"]
        actual = {r[req["date_column"]]: r[req["target_column"]] for r in rows}
        if (
            len(test["dates"]) != len(test["mean"])
            or len(set(test["dates"])) != len(test["dates"])
            or any(d not in actual for d in test["dates"])
        ):
            raise MMMError("CORRUPT_MODEL", "Invalid native evaluation dates")
        prediction = [
            {"date": d, "observed": actual[d], "predicted": v}
            for d, v in zip(test["dates"], test["mean"])
        ]
        if backend == "meta_robyn":
            train_dates = model.get("temporal_split", test.get("temporal_split", {})).get(
                "train_dates", []
            )
        else:
            train_dates = [r[req["date_column"]] for r in rows[: model["cutoff"]]]
        interval = {
            "type": test.get("interval_type"),
            "level": test.get("interval_level"),
            "lower": test.get("lower_90"),
            "upper": test.get("upper_90"),
        }
        framework_version = model["backend_version"]
        assessment = (
            classify_bayesian(
                model.get("diagnostics", {}),
                max_rhat=request.max_rhat,
                min_ess_per_chain=request.min_ess_per_chain,
            )
            if backend != "meta_robyn"
            else {
                "status": "not_applicable",
                "reason": "Robyn search is not MCMC; review trials, validation and stability",
            }
        )
        support = {
            "status": "abstain_from_budget_change",
            "message": ABSTENTION,
            "business_recommendation_eligible": False,
            "reasons": [
                "CAUSAL_VALIDATION_REQUIRED",
                *(["SYNTHETIC_DATA"] if model["synthetic"] else []),
            ],
        }
    observed = [p["observed"] for p in prediction]
    predicted = [p["predicted"] for p in prediction]
    train_set = set(train_dates)
    training_y = [r[req["target_column"]] for r in rows if r[req["date_column"]] in train_set]
    baseline = float(np.mean(training_y)) if training_y else None
    return {
        "schema_version": "1.0",
        "backend": backend,
        "framework_version": framework_version,
        "model_id": model["model_id"],
        "source": {
            "dataset_id": model["dataset_id"],
            "dataset_sha256": model["dataset_sha256"],
            "synthetic": model["synthetic"],
            "frequency": dataset["frequency"],
            "target_column": req["target_column"],
            "target_type": dataset.get("target_type", "unspecified"),
            "units": dataset.get("units", {}),
            "data_context": dataset.get("data_context", {}),
            "media_columns": req["media_columns"],
        },
        "effective_configuration": model.get("effective_configuration", req),
        "request": req,
        "training_dates": train_dates,
        "evaluation": prediction,
        "metrics": metrics(observed, predicted),
        "training_mean": baseline,
        "baseline_metrics": metrics(observed, [baseline] * len(observed))
        if baseline is not None
        else None,
        "diagnostics": model.get("diagnostics", {}),
        "diagnostic_assessment": assessment,
        "intervals": interval,
        "decision_support": support,
        "capabilities": capabilities(backend),
        "warnings": model.get("warnings", []),
        "native_outputs_preserved": True,
        "exploratory": True,
    }


def compare(models, policy):
    first = models[0]["source"]
    for model in models[1:]:
        if any(
            model["source"][key] != first[key]
            for key in (
                "dataset_sha256",
                "target_column",
                "target_type",
                "units",
                "frequency",
                "media_columns",
            )
        ):
            raise MMMError(
                "INCOMPARABLE_MODELS",
                "Comparison requires identical dataset lineage, KPI, media, units and frequency",
            )
    windows = [[p["date"] for p in m["evaluation"]] for m in models]
    if policy == "exact" and any(dates != windows[0] for dates in windows):
        raise MMMError(
            "INCOMPARABLE_WINDOWS",
            "Test dates differ; explicitly request intersection to compare their overlap",
        )
    dates = sorted(set.intersection(*(set(w) for w in windows)))
    if len(dates) < 5:
        raise MMMError("INCOMPARABLE_WINDOWS", "Need at least five common test periods")
    results = []
    for model in models:
        lookup = {p["date"]: p for p in model["evaluation"]}
        y = [lookup[d]["observed"] for d in dates]
        p = [lookup[d]["predicted"] for d in dates]
        intervals = model["intervals"]
        aligned = None
        if intervals.get("lower") is not None and intervals.get("upper") is not None:
            if any(len(intervals[k]) != len(model["evaluation"]) for k in ("lower", "upper")):
                raise MMMError("CORRUPT_MODEL", "Interval lengths differ from evaluation dates")
            indices = {p["date"]: i for i, p in enumerate(model["evaluation"])}
            aligned = {
                "dates": dates,
                **{k: [intervals[k][indices[d]] for d in dates] for k in ("lower", "upper")},
            }
        results.append(
            {
                "backend": model["backend"],
                "model_id": model["model_id"],
                "framework_version": model["framework_version"],
                "training_dates": model["training_dates"],
                "metrics": metrics(y, p),
                "baseline_metrics": metrics(y, [model["training_mean"]] * len(y))
                if model["training_mean"] is not None
                else None,
                "diagnostic_assessment": model["diagnostic_assessment"],
                "interval_semantics": {
                    k: v for k, v in intervals.items() if k not in {"lower", "upper"}
                },
                "evaluation_intervals": aligned,
                "configuration": model["effective_configuration"],
                "warnings": model["warnings"],
            }
        )
    training_differ = any(m["training_dates"] != models[0]["training_dates"] for m in models)
    return {
        "schema_version": "1.0",
        "source": first,
        "models": results,
        "comparison_window": {"policy": policy, "dates": dates, "rows": len(dates)},
        "training_windows_differ": training_differ,
        "same_training_window": not training_differ,
        "fair_training_protocol": None,
        "fair_training_protocol_reason": "Matching dates alone cannot certify fairness of priors, feature information, search budgets or model selection",
        "winner": None,
        "business_recommendation_eligible": False,
        "warnings": [
            "Different training information, priors, shapes, search and interval semantics must be considered. Common evaluation dates do not establish universal superiority."
        ],
    }
