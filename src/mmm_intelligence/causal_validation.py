"""Falsification, design assumptions and experiment evidence without causal certification."""

import math

from .errors import MMMError
from .storage import digest

ASSUMPTIONS = (
    "random_assignment",
    "no_interference",
    "no_unmeasured_confounding",
    "no_post_treatment_controls",
    "positivity",
    "measurement_consistency",
    "prespecified_analysis",
    "complete_followup",
)


def falsification(results, margin):
    output = []
    for result in results:
        lower, upper = result["estimate"]["interval"]
        state = (
            "inconclusive"
            if margin is None
            else (
                "compatible_with_margin"
                if -margin <= lower and upper <= margin
                else "contradicted"
                if upper < -margin or lower > margin
                else "inconclusive"
            )
        )
        output.append(
            {
                "artifact_id": result.get("artifact_id"),
                "status": state,
                "interval": [lower, upper],
                "equivalence_margin": margin,
                "interpretation": "Interval containment screen using a prespecified substantive margin; non-significance alone is not evidence of equivalence",
            }
        )
    return output


def review_evidence(primary, placebos, negatives, protocol, *, synthetic):
    all_results = [*primary, *placebos, *negatives]
    synthetic = synthetic or any(r.get("synthetic") is True for r in all_results)
    violated = [k for k in ASSUMPTIONS if protocol.assumptions.get(k) == "violated"]
    unknown = [k for k in ASSUMPTIONS if protocol.assumptions.get(k) != "supported"]
    threats, missing, sensitivity = [], [], []
    for result in primary:
        if (p := result.get("sample_ratio_mismatch_pvalue")) is not None and p < 0.01:
            threats.append("sample_ratio_mismatch")
        if any(result.get("losses", {}).values()):
            threats.append("missing_outcomes")
        if result.get("method") != "randomized":
            missing.append("randomization_design_not_verified")
        if not result.get("population_verified") or not result.get("measurement_window_verified"):
            missing.append("population_or_measurement_window")
        lower, upper = result["estimate"]["interval"]
        if lower <= 0 <= upper:
            missing.append("effect_direction_inconclusive")
        if any(g.get("status") == "harm_detected" for g in result.get("guardrails", {}).values()):
            threats.append("guardrail_harm")
        if any(
            g.get("status") in {"not_evaluated", "insufficient", "inconclusive"}
            for g in result.get("guardrails", {}).values()
        ):
            missing.append("guardrail_evidence")
        sensitivity.append(
            {
                "artifact_id": result.get("artifact_id"),
                "definition": "Hypothetical additive bias in the same units as the arm mean difference; no bias estimated from observations",
                "bias_grid": [
                    {
                        "assumed_bias": bias,
                        "adjusted_estimate": result["estimate"]["difference"] - bias,
                        "adjusted_interval": [lower - bias, upper - bias],
                    }
                    for bias in protocol.confounding_bias_grid
                ],
            }
        )
    placebo = falsification(placebos, protocol.equivalence_margin)
    controls = falsification(negatives, protocol.equivalence_margin)
    if any(p["status"] == "contradicted" for p in [*placebo, *controls]):
        threats.append("falsification_contradiction")
    if not primary:
        missing.append("independent_incrementality_experiment")
    if not placebos or any(p["status"] != "compatible_with_margin" for p in placebo):
        missing.append("placebo_evidence")
    if not negatives or any(p["status"] != "compatible_with_margin" for p in controls):
        missing.append("negative_control_evidence")
    if unknown:
        missing.append("causal_assumptions_require_review")
    if not protocol.review_reference:
        missing.append("independent_design_review")
    state = (
        "simulation_only"
        if synthetic
        else "contradicted"
        if violated or threats
        else "not_assessed"
        if not primary
        else "inconclusive"
        if missing
        else "experimental_support_pending_external_review"
    )
    return {
        "status": state,
        "causal_identification": False,
        "source_ids": [r["artifact_id"] for r in all_results if r.get("artifact_id")],
        "assumptions": {k: protocol.assumptions.get(k, "unknown") for k in ASSUMPTIONS},
        "violated_assumptions": violated,
        "threats": sorted(set(threats)),
        "missing": sorted(set(missing)),
        "placebos": placebo,
        "negative_controls": controls,
        "confounding_sensitivity": sensitivity,
        "review_reference": protocol.review_reference,
        "review_reference_authenticated": False,
        "no_unmeasured_confounding_verified": False,
        "primary_effects": [
            {"artifact_id": r.get("artifact_id"), "estimate": r["estimate"], "method": r["method"]}
            for r in primary
        ],
        "limitations": [
            "Imported assignments and review declarations do not authenticate randomization or execution",
            "Compatible placebos and negative controls do not prove exchangeability",
            "No automatic causal claim, extrapolation across populations or budget action",
            "Geographic experiments require independent geo units; repeated days are not independent geos",
            "Multiplicity across separate experiments and transportability require a prespecified design review",
        ],
    }


def load_evidence(service, model, protocol):
    groups = []
    for ids in (
        protocol.experiment_result_ids,
        protocol.placebo_result_ids,
        protocol.negative_control_result_ids,
    ):
        results = []
        for artifact_id in ids:
            result = load_result(service, model, artifact_id)
            results.append(result)
        groups.append(results)
    if any(r["kpi"] != model["request"]["target_column"] for r in groups[0]):
        raise MMMError("ESTIMAND_MISMATCH", "Validation experiment KPI must match the modeled KPI")
    return review_evidence(*groups, protocol, synthetic=model["synthetic"])


def load_result(service, model, artifact_id):
    result = service._growth_read(artifact_id, {"experiment_result"})
    if result["synthetic"] is not model["synthetic"]:
        raise MMMError("MIXED_DATA_ORIGINS", "Scientific evidence and model must share origin type")
    for source_id, expected in result["source_hashes"].items():
        if digest(service._growth_read(source_id)) != expected:
            raise MMMError(
                "LINEAGE_MISMATCH", "Experiment source differs from its recorded evidence"
            )
    return result


def calibrate_evidence(service, model, backend, protocol):
    from .analysis import calibrate
    from .schemas import CalibrationRequest

    if backend != "ridge":
        raise MMMError(
            "OPERATION_UNAVAILABLE",
            "Verified native experimental refitting is unavailable; no substitute engine is used",
        )
    calibration = protocol.calibration
    evidence = load_result(service, model, calibration.experiment_result_id)
    if (
        evidence["kpi"] != model["request"]["target_column"]
        or calibration.outcome_unit != model.get("units", {}).get("target")
        or not calibration.matching_population
        or not calibration.matching_measurement_window
    ):
        raise MMMError(
            "ESTIMAND_MISMATCH",
            "Calibration requires matching declared KPI, units, population and measurement window",
        )
    se = evidence["estimate"].get("standard_error")
    if se is None or not math.isfinite(se) or se <= 0:
        raise MMMError(
            "EVIDENCE_INCOMPLETE",
            "Reanalyze experiment to persist a positive sampling standard error",
        )
    if (
        evidence["method"] != "randomized"
        or any(evidence["losses"].values())
        or evidence["sample_ratio_mismatch_pvalue"] is None
        or evidence["sample_ratio_mismatch_pvalue"] < 0.01
    ):
        raise MMMError(
            "EXPERIMENT_QUALITY",
            "Resolve assignment, missing-outcome and sample-ratio concerns before calibration",
        )
    if not model["synthetic"] and (
        not protocol.review_reference
        or any(protocol.assumptions.get(key) != "supported" for key in ASSUMPTIONS)
    ):
        raise MMMError(
            "EVIDENCE_INCOMPLETE",
            "Real-data calibration requires declared design review and supported assumptions",
        )
    lift_mean = float(evidence["estimate"]["difference"] * calibration.aggregate_multiplier)
    lift_sd = float(se * calibration.aggregate_multiplier)
    if (
        not math.isfinite(lift_mean)
        or not math.isfinite(lift_sd)
        or abs(lift_mean) > 1e12
        or not 0 < lift_sd <= 1e9
    ):
        raise MMMError(
            "CALIBRATION_NUMERIC_RANGE",
            "Scope transformation exceeds supported lift or uncertainty range",
        )
    result = calibrate(
        model,
        CalibrationRequest(
            model_id=model["model_id"],
            experiment_id=evidence["artifact_id"],
            channel=calibration.channel,
            treatment_spend=calibration.treatment_spend,
            control_spend=calibration.control_spend,
            horizon=calibration.horizon,
            initial_adstock=calibration.initial_adstock,
            lift_mean=lift_mean,
            lift_sd=lift_sd,
            synthetic=model["synthetic"],
        ),
    )
    result.update(
        evidence_sha256=digest(evidence),
        scope_transformation=calibration.model_dump(mode="json"),
        design_assumptions_authenticated=False,
        independent_validation_reused=False,
    )
    return result
