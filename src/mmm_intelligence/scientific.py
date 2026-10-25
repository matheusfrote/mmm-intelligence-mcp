"""Inspectable model diagnostics and conservative decision support, never causal certification."""

from itertools import product

import numpy as np

from .datasets import validate
from .errors import MMMError
from .modeling import adstock, design_matrix, hill, metrics, train
from .schemas import TrainRequest
from .storage import digest


def decision_support(model: dict, warnings=()) -> dict:
    reasons = []
    diagnostic = model.get("diagnostics", {})
    if model.get("synthetic") is True:
        reasons.append("SYNTHETIC_DATA")
    if "standardized_matrix_rank" not in diagnostic:
        reasons.append("SCIENTIFIC_DIAGNOSTICS_UNAVAILABLE")
    elif diagnostic["standardized_matrix_rank"] < diagnostic["feature_count"]:
        reasons.append("RANK_DEFICIENT")
    if len(model.get("coefficient_draws", [])) < 20:
        reasons.append("CONDITIONAL_UNCERTAINTY_UNAVAILABLE")
    baseline = model.get("metrics", {}).get("test_train_mean_baseline", {}).get("mae")
    actual = model.get("metrics", {}).get("test", {}).get("mae")
    if baseline is None or actual is None or actual >= baseline:
        reasons.append("NO_HOLDOUT_IMPROVEMENT_OVER_MEAN_BASELINE")
    all_warnings = [*model.get("warnings", []), *warnings]
    for prefix in (
        "SHORT_HISTORY",
        "EXTRAPOLATION",
        "NEGATIVE_PREDICTIONS",
        "BOOTSTRAP_SHRINKAGE",
        "METADATA_MISSING",
    ):
        if any(w.startswith(prefix) for w in all_warnings):
            reasons.append(prefix)
    return {
        "status": "abstain_from_budget_change" if reasons else "human_review_required",
        "business_recommendation_eligible": False,
        "reasons": sorted(set(reasons)),
        "policy": "Conservative evidence screens, not universal statistical acceptance thresholds. Numeric optimization remains an exploratory candidate.",
        "required_next_step": "Review business context, causal assumptions, stability and experiment evidence before any budget change",
    }


def design_for_model(dataset: dict, model: dict) -> np.ndarray:
    req = TrainRequest.model_validate(model["request"])
    transformed = np.column_stack(
        [
            hill(
                adstock([r[c] for r in dataset["rows"]], model["media_parameters"][c]["decay"]),
                model["media_parameters"][c]["half_saturation"],
            )
            for c in req.media_columns
        ]
    )
    controls = np.array([[r[c] for c in req.control_columns] for r in dataset["rows"]])
    return design_matrix(
        transformed, controls, np.arange(len(dataset["rows"])), model["state"]["step_days"]
    )


def decomposition(dataset: dict, model: dict) -> dict:
    design = design_for_model(dataset, model)
    names = model["feature_names"]
    coef = np.array([model["coefficients"][c] for c in names])
    warmup = model["request"]["warmup_periods"]
    components = design[warmup:] * coef
    predicted = np.array([p["predicted"] for p in model["predictions"]])
    error = float(np.max(np.abs(components.sum(axis=1) - predicted)))
    if error > 1e-7 * max(1, float(np.max(np.abs(predicted)))):
        raise MMMError(
            "DECOMPOSITION_MISMATCH",
            "Component reconstruction does not match persisted predictions",
        )
    totals = dict(zip(names, components.sum(axis=0).tolist()))
    intervals = None
    if model.get("coefficient_draws"):
        draws = np.asarray(model["coefficient_draws"], float)
        if draws.ndim != 2 or draws.shape[1] != len(names) or not np.isfinite(draws).all():
            raise MMMError("CORRUPT_MODEL", "Invalid bootstrap coefficients")
        low, high = np.quantile(draws * design[warmup:].sum(axis=0), [0.05, 0.95], axis=0)
        intervals = {c: [float(low[j]), float(high[j])] for j, c in enumerate(names)}
    return {
        "definition": "Additive fitted components, including baseline, controls and historical carryover; not proven incremental causal effects",
        "period_start": model["predictions"][0]["date"],
        "period_end": model["predictions"][-1]["date"],
        "component_totals": totals,
        "predicted_total": float(predicted.sum()),
        "observed_total": float(sum(p["observed"] for p in model["predictions"])),
        "residual_total": float(sum(p["observed"] - p["predicted"] for p in model["predictions"])),
        "maximum_reconciliation_error": error,
        "conditional_component_intervals_90": intervals,
        "roi": None,
        "mroi": None,
        "roi_unavailable_reason": "No identified incremental profit or causal return; aggregate media component includes carryover and is not incremental future return",
        "units": model["units"],
    }


def backtest(dataset: dict, model: dict, folds: int) -> dict:
    base = TrainRequest.model_validate(model["request"])
    n = len(dataset["rows"])
    # Disjoint terminal test windows; tuned shapes are reselected inside each fold.
    minimum_training = base.warmup_periods + max(26, len(model["feature_names"]) + 5)
    horizon = min(
        int(np.ceil(n * base.test_fraction)),
        (n - minimum_training) // folds,
        int(np.floor(0.4 * n / (1 + 0.4 * (folds - 1)))),
    )
    if horizon < 5:
        return {
            "status": "insufficient_history",
            "folds": [],
            "reason": "Need >=5 disjoint test periods per fold plus valid initial training",
        }
    results = []
    for j in range(folds):
        end = n - horizon * (folds - j - 1)
        fraction = horizon / end
        if not 0.1 <= fraction <= 0.4:
            return {
                "status": "insufficient_history",
                "folds": [],
                "reason": "Available windows exceed supported temporal split proportions",
            }
        # Tiny downward rounding protects an exact integer cutoff from ceil's FP overshoot.
        fraction = float(np.nextafter(fraction, 0)) if fraction > 0.1 else fraction
        req = base.model_copy(update={"test_fraction": fraction, "bootstrap_samples": 0})
        prefix = {**dataset, "rows": dataset["rows"][:end]}
        quality = validate(prefix, req, 100000)
        if not quality["valid"]:
            return {
                "status": "insufficient_history",
                "folds": [],
                "reason": "; ".join(quality["issues"]),
            }
        if model.get("shape_selection"):
            from .analysis import tune
            from .schemas import TuneRequest

            rankings = model["shape_selection"]["rankings"]
            nested = TuneRequest(
                **req.model_dump(),
                decays=sorted({r["decay"] for r in rankings}),
                multipliers=sorted({r["saturation_multiplier"] for r in rankings}),
            )
            try:
                fitted = tune(prefix, nested, "backtest", 100000)
            except MMMError as exc:
                if exc.code != "INSUFFICIENT_TUNING_HISTORY":
                    raise
                return {
                    "status": "insufficient_history",
                    "folds": [],
                    "reason": "Nested shape selection needs additional pre-test history",
                }
        else:
            fitted = train(prefix, req, "backtest", quality)
        test = [p for p in fitted["predictions"] if p["split"] == "test"]
        last_train = prefix["rows"][end - len(test) - 1][req.target_column]
        naive = metrics([p["observed"] for p in test], np.full(len(test), last_train))
        results.append(
            {
                "shape_policy": "nested_selection_within_fold"
                if model.get("shape_selection")
                else "fixed_declared_shapes",
                "adstock_decay": fitted["request"]["adstock_decay"],
                "saturation_multiplier": fitted["request"]["saturation_multiplier"],
                "train_end": fitted["split"]["train_end"],
                "test_start": fitted["split"]["test_start"],
                "test_end": test[-1]["date"],
                "test_rows": len(test),
                "metrics": fitted["metrics"]["test"],
                "mean_baseline": fitted["metrics"]["test_train_mean_baseline"],
                "last_observation_baseline": naive,
            }
        )
    return {
        "status": "executed",
        "method": "expanding origin, disjoint test windows; fixed declared shapes or nested selection within each fold; no refit on test",
        "folds": results,
    }


def audit(dataset: dict, model: dict, request, max_rows: int) -> dict:
    from .optimization import optimize
    from .schemas import OptimizeRequest

    if digest(dataset) != model["dataset_sha256"]:
        raise MMMError("LINEAGE_MISMATCH", "Dataset content differs from model lineage")
    spec = TrainRequest.model_validate(model["request"])
    quality = validate(dataset, spec, max_rows)
    if not quality["valid"]:
        raise MMMError("DATASET_INVALID", "; ".join(quality["issues"]))
    n = len(dataset["rows"])
    cutoff = n - int(np.ceil(n * spec.test_fraction))
    variables = [*spec.media_columns, *spec.control_columns]
    raw = np.array(
        [[r[c] for c in variables] for r in dataset["rows"][spec.warmup_periods : cutoff]]
    )
    correlations = []
    for j, a in enumerate(variables):
        for k, b in enumerate(variables[j + 1 :], j + 1):
            value = (
                float(np.corrcoef(raw[:, j], raw[:, k])[0, 1])
                if np.std(raw[:, j]) > 0 and np.std(raw[:, k]) > 0
                else None
            )
            correlations.append(
                {
                    "a": a,
                    "b": b,
                    "correlation": value if value is None or np.isfinite(value) else None,
                }
            )
    total = sum(model["state"]["reference_spend_per_period"].values()) * 13
    sensitivity = []
    for decay, multiplier in product(request.decays, request.multipliers):
        changed = spec.model_copy(
            update={
                "adstock_decay": decay,
                "saturation_multiplier": multiplier,
                "bootstrap_samples": 0,
            }
        )
        fitted = train(dataset, changed, "sensitivity", quality)
        candidate = optimize(
            fitted, OptimizeRequest(model_id="sensitivity", total_budget=float(total))
        )
        sensitivity.append(
            {
                "decay": decay,
                "half_saturation_multiplier": multiplier,
                "holdout_metrics": fitted["metrics"]["test"],
                "conditional_media_coefficients": {
                    c: fitted["coefficients"][c] for c in spec.media_columns
                },
                "candidate_allocation": candidate["scenario"]["allocation"],
            }
        )
    ranges = {
        c: [
            min(s["candidate_allocation"][c] for s in sensitivity),
            max(s["candidate_allocation"][c] for s in sensitivity),
        ]
        for c in spec.media_columns
    }
    temporal = backtest(dataset, model, request.folds)
    support = decision_support(model)
    central = optimize(model, OptimizeRequest(model_id=request.model_id, total_budget=float(total)))
    support["sensitivity_allocation_ranges"] = ranges
    unstable = [
        c
        for c, interval in ranges.items()
        if interval[1] - interval[0] > request.max_allocation_spread
    ]
    if unstable:
        support["reasons"].append("SPECIFICATION_SENSITIVITY")
        support["status"] = "abstain_from_budget_change"
    if temporal["status"] != "executed":
        support["reasons"].append("BACKTEST_UNAVAILABLE")
        support["status"] = "abstain_from_budget_change"
    return {
        "model_id": request.model_id,
        "synthetic": model["synthetic"],
        "source": {
            "dataset_id": model["dataset_id"],
            "dataset_sha256": model["dataset_sha256"],
            "rows": n,
            "start_date": quality["start_date"],
            "end_date": quality["end_date"],
            "frequency": quality["frequency"],
            "data_context": dataset.get("data_context", {}),
            "target_type": dataset.get("target_type", "unspecified"),
        },
        "data_quality": quality,
        "diagnostics": model["diagnostics"],
        "training_correlations": correlations,
        "decomposition": decomposition(dataset, model),
        "backtest": temporal,
        "sensitivity": {
            "specifications": sensitivity,
            "allocation_ranges": ranges,
            "allocation_spread_screen": request.max_allocation_spread,
            "screen_scope": "Operational warning only; absence of this warning does not certify validity",
            "channels_exceeding_screen": unstable,
            "interpretation": "Sensitivity of conditional numeric optima, not confidence intervals or selection of a preferred model; outer test not used to choose a winner",
        },
        "decision_support": support,
        "insight": {
            "diagnosis": f"Holdout MAE {model['metrics']['test']['mae']:.6g} versus training-mean baseline {model['metrics']['test_train_mean_baseline']['mae']:.6g}; standardized rank {model['diagnostics'].get('standardized_matrix_rank', 'unavailable')}/{len(model['feature_names'])}",
            "evidence": {
                "holdout": model["metrics"]["test"],
                "reasons": support["reasons"],
                "allocation_ranges": ranges,
            },
            "interpretation": "Correlated channels, omitted variables, tracking and model shapes can explain apparent channel differences",
            "uncertainty": model.get("uncertainty", {"method": "unavailable"}),
            "action": "Maintain the business allocation pending review; investigate correlated channels and use controlled incrementality experiments before reallocation",
            "expected_impact": {
                "scope": "Conditional model scenario only, not a validated business effect",
                **central["comparison_same_total"],
            },
            "business_impact": None,
            "impact_unavailable_reason": "No validated causal business effect; model-only opportunity is shown separately",
            "conditions": "Authorized complete KPI and spend, comparable currency/periods, defensible controls, stable specifications and adequate experimental support",
            "validation": "Predeclare population, period, KPI and uncertainty for a randomized geo/lift test; account for carryover and compare with model over matching scope",
        },
        "warnings": [
            *model["warnings"],
            "AUDIT_NOT_CERTIFICATION: forecasts, parameter stability and causal assumptions require contextual review",
        ],
    }
