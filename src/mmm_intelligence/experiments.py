"""Explicit two-arm unit-level statistical analyses; no campaign execution."""

import math
from datetime import date

import numpy as np
from scipy.stats import binomtest, fisher_exact, norm, t, ttest_ind

from .errors import MMMError
from .storage import digest


def plan_experiment(request):
    if request.comparison_family_size < 1 + len(request.guardrail_specs):
        raise MMMError(
            "EXPERIMENT_DESIGN", "Comparison family must include KPI and specified guardrails"
        )
    if (
        not set(request.guardrail_specs).issubset(request.guardrails)
        or request.kpi in request.guardrails
    ):
        raise MMMError(
            "EXPERIMENT_DESIGN", "Guardrail specifications must refer to distinct planned metrics"
        )
    if request.randomization_unit and request.randomization_unit != request.unit_column:
        raise MMMError(
            "EXPERIMENT_DESIGN",
            "Aggregate outcomes to one row per randomization unit; cluster replication is not supported",
        )
    window = [request.observation_start, request.observation_end, request.date_column]
    if any(window) and not all(window):
        raise MMMError("EXPERIMENT_DESIGN", "Declare start, end and date column together")
    if request.observation_start and request.observation_end < request.observation_start:
        raise MMMError("EXPERIMENT_DESIGN", "Observation window end precedes start")
    if bool(request.population_column) != bool(request.population_value):
        raise MMMError("EXPERIMENT_DESIGN", "Declare population column and eligible value together")
    if request.cost_column and request.outcome_type != "binary":
        raise MMMError(
            "EXPERIMENT_DESIGN", "Cost per conversion requires a binary conversion outcome"
        )
    if (
        request.treatment == request.control
        or len({request.kpi, request.unit_column, request.group_column}) != 3
    ):
        raise MMMError("EXPERIMENT_DESIGN", "Distinct arms and unit/group/outcome columns required")
    alpha = request.alpha / request.comparison_family_size
    q = request.expected_treatment_fraction
    if request.outcome_type == "binary":
        p0 = request.baseline
        p1 = p0 + request.minimum_effect
        if not 0 < p0 < 1 or not 0 < p1 < 1:
            raise MMMError(
                "EXPERIMENT_DESIGN",
                "Binary baseline and baseline+MDE must be strictly between zero and one",
            )
        variance = p0 * (1 - p0) / (1 - q) + p1 * (1 - p1) / q
    else:
        if request.standard_deviation is None:
            raise MMMError(
                "EXPERIMENT_DESIGN", "Continuous planning requires a declared standard deviation"
            )
        variance = request.standard_deviation * request.standard_deviation / (q * (1 - q))
    squared_effect = request.minimum_effect * request.minimum_effect
    critical = float(norm.isf(alpha / 2)) + float(norm.ppf(request.power))
    if (
        not math.isfinite(variance)
        or variance <= 0
        or squared_effect == 0
        or not math.isfinite(critical)
    ):
        raise MMMError(
            "EXPERIMENT_RANGE",
            "Planning variance, effect or tail probability exceeds supported floating-point range",
        )
    required = critical * critical * variance / squared_effect
    if not math.isfinite(required):
        raise MMMError(
            "EXPERIMENT_RANGE", "Required sample size exceeds supported floating-point range"
        )
    total = max(math.ceil(5 / min(q, 1 - q)), math.ceil(required))
    return {
        **request.model_dump(mode="json"),
        "synthetic": True,
        "adjusted_alpha": alpha,
        "sample_size_treatment": math.ceil(total * q),
        "sample_size_control": math.ceil(total * (1 - q)),
        "sample_size_per_arm": max(math.ceil(total * q), math.ceil(total * (1 - q))),
        "power_method": "two-sided normal approximation, declared independent units, Bonferroni alpha",
        "estimand": "difference in marginal unit-level outcome means",
        "protocol_complete": all(
            [
                request.hypothesis,
                request.analysis_plan,
                request.randomization_unit,
                request.duration_days,
                request.conversion_window_days is not None,
                request.observation_start,
                request.population_column,
                request.exclusion_criteria,
                request.operational_constraints,
            ]
        ),
        "warnings": [
            "Approximate sample-size planning; cluster designs require cluster-level variance and units.",
            "Duration and conversion-window adequacy require substantive review.",
            "Minimum five units per arm; approximate normal planning is not a power guarantee for exact or Welch tests.",
        ],
    }


def wilson(p, n, z):
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return center - half, center + half


def analyze_experiment(artifact, plan, *, _guardrail=False):
    arms = {plan["treatment"]: [], plan["control"]: []}
    assigned = {}
    losses = {k: 0 for k in arms}
    for row in artifact["rows"]:
        if (
            plan.get("population_column")
            and row.get(plan["population_column"]) != plan["population_value"]
        ):
            raise MMMError(
                "EXPERIMENT_POPULATION",
                "Result includes units outside the declared eligible population",
            )
        if plan.get("date_column"):
            try:
                day = date.fromisoformat(row[plan["date_column"]])
                if (
                    not date.fromisoformat(plan["observation_start"])
                    <= day
                    <= date.fromisoformat(plan["observation_end"])
                ):
                    raise ValueError("outside window")
            except (KeyError, ValueError, TypeError) as exc:
                raise MMMError(
                    "EXPERIMENT_WINDOW",
                    "Every result must have a valid date within the planned window",
                ) from exc
        if plan.get("cost_column"):
            cost = row.get(plan["cost_column"])
            if (
                isinstance(cost, bool)
                or not isinstance(cost, (float, int))
                or not math.isfinite(cost)
                or cost < 0
            ):
                raise MMMError(
                    "EXPERIMENT_COST", "Costs must be complete finite nonnegative values"
                )
        if any(k not in row for k in [plan["unit_column"], plan["group_column"], plan["kpi"]]):
            raise MMMError("EXPERIMENT_FIELDS", "Unit, arm and outcome columns are required")
        unit = row[plan["unit_column"]]
        arm = row[plan["group_column"]]
        if unit is None or arm not in arms:
            raise MMMError("EXPERIMENT_DESIGN", "Unknown arm or missing unit")
        if unit in assigned:
            raise MMMError(
                "EXPERIMENT_UNIT",
                "One aggregate outcome per independent/randomization unit is required; repeated measures need a paired/cluster design",
            )
        assigned[unit] = arm
        value = row[plan["kpi"]]
        if value is None:
            losses[arm] += 1
            continue
        if (
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            or plan["outcome_type"] == "continuous"
            and isinstance(value, bool)
        ):
            raise MMMError("EXPERIMENT_OUTCOME", "Outcome must be a finite number")
        if plan["outcome_type"] == "binary" and value not in {0, 1}:
            raise MMMError("EXPERIMENT_OUTCOME", "Binary outcomes must be zero or one")
        arms[arm].append(float(value))
    treatment = np.array(arms[plan["treatment"]])
    control = np.array(arms[plan["control"]])
    n1 = len(treatment)
    n0 = len(control)
    if min(n1, n0) < 5:
        raise MMMError(
            "EXPERIMENT_SAMPLE", "At least five observed independent units per arm required"
        )
    alpha = plan["adjusted_alpha"]
    z = float(norm.isf(alpha / 2))
    m1 = float(np.mean(treatment))
    m0 = float(np.mean(control))
    difference = m1 - m0
    if plan["outcome_type"] == "binary":
        l1, u1 = wilson(m1, n1, z)
        l0, u0 = wilson(m0, n0, z)
        interval = [
            difference - math.sqrt((m1 - l1) ** 2 + (u0 - m0) ** 2),
            difference + math.sqrt((u1 - m1) ** 2 + (m0 - l0) ** 2),
        ]
        pvalue = float(
            fisher_exact(
                [
                    [int(sum(treatment)), n1 - int(sum(treatment))],
                    [int(sum(control)), n0 - int(sum(control))],
                ]
            ).pvalue
        )
        method = "risk difference, Newcombe Wilson interval; Fisher exact two-sided p-value"
    else:
        v1 = float(np.var(treatment, ddof=1))
        v0 = float(np.var(control, ddof=1))
        variance = v1 / n1 + v0 / n0
        if variance <= 0:
            raise MMMError("EXPERIMENT_VARIANCE", "Positive sampling variance is required")
        df = variance**2 / ((v1 / n1) ** 2 / (n1 - 1) + (v0 / n0) ** 2 / (n0 - 1))
        margin = float(t.isf(alpha / 2, df)) * math.sqrt(variance)
        interval = [difference - margin, difference + margin]
        pvalue = float(ttest_ind(treatment, control, equal_var=False, nan_policy="raise").pvalue)
        method = "independent-unit Welch mean difference and t interval"
    assigned_t = sum(v == plan["treatment"] for v in assigned.values())
    srm = (
        float(binomtest(assigned_t, len(assigned), plan["expected_treatment_fraction"]).pvalue)
        if plan["method"] == "randomized"
        else None
    )
    guardrails = {}
    for metric in plan["guardrails"]:
        spec = plan.get("guardrail_specs", {}).get(metric)
        if spec is None:
            guardrails[metric] = {
                "status": "not_evaluated",
                "reason": "Specify outcome, adverse direction and acceptable change",
            }
        elif any(row.get(metric) is None for row in artifact["rows"]):
            guardrails[metric] = {
                "status": "insufficient",
                "reason": "Missing guardrail values; no imputation",
            }
        else:
            subplan = {
                **plan,
                "kpi": metric,
                "outcome_type": spec["outcome_type"],
                "guardrails": [],
                "cost_column": None,
                "guardrail_specs": {},
            }
            try:
                estimate = analyze_experiment(artifact, subplan, _guardrail=True)["estimate"]
            except MMMError as exc:
                if exc.code not in {"EXPERIMENT_VARIANCE", "EXPERIMENT_SAMPLE"}:
                    raise
                guardrails[metric] = {"status": "insufficient", "reason": str(exc)}
                continue
            lo, hi = estimate["interval"]
            if spec["direction"] == "decrease":
                lo, hi = -hi, -lo
            threshold = spec["max_adverse_change"]
            status = (
                "harm_detected"
                if lo > threshold
                else "compatible_with_threshold"
                if hi <= threshold
                else "inconclusive"
            )
            guardrails[metric] = {"status": status, "estimate": estimate, "specification": spec}
    cost_ratio = None
    if plan.get("cost_column"):
        # Ratios of totals, complete outcomes only. No unsupported ratio confidence interval.
        totals = {
            arm: sum(
                row[plan["cost_column"]]
                for row in artifact["rows"]
                if row[plan["group_column"]] == arm and row[plan["kpi"]] is not None
            )
            for arm in arms
        }
        cost_ratio = {
            "treatment": totals[plan["treatment"]] / sum(treatment) if sum(treatment) else None,
            "control": totals[plan["control"]] / sum(control) if sum(control) else None,
            "method": "ratio of arm cost totals to conversion totals among observed outcomes",
            "interval": None,
            "limitation": "Descriptive ratio only; zero conversions abstains; no ratio inference",
        }
    if _guardrail:
        planned_variance = None
    elif plan["outcome_type"] == "binary":
        p0 = plan["baseline"]
        p1 = p0 + plan["minimum_effect"]
        planned_variance = p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0
    else:
        planned_variance = plan["standard_deviation"] ** 2 * (1 / n1 + 1 / n0)
    if planned_variance is not None:
        noncentral = plan["minimum_effect"] / math.sqrt(planned_variance)
        planned_power = float(norm.sf(z - noncentral) + norm.cdf(-z - noncentral))
    else:
        planned_power = None
    return {
        "synthetic": artifact["synthetic"],
        "source_ids": [artifact["artifact_id"], plan["artifact_id"]],
        "source_hashes": {
            artifact["artifact_id"]: digest(artifact),
            plan["artifact_id"]: digest(plan),
        },
        "plan_id": plan["artifact_id"],
        "kpi": plan["kpi"],
        "protocol": {
            k: plan.get(k)
            for k in (
                "treatment",
                "control",
                "population",
                "measurement_window",
                "observation_start",
                "observation_end",
                "unit_column",
            )
        },
        "method": plan["method"],
        "estimator": method,
        "estimate": {
            "difference": difference,
            "relative_difference": difference / m0 if m0 else None,
            "interval": interval,
            "confidence_level": 1 - alpha,
            "pvalue": pvalue,
            "pvalue_bonferroni": min(1, pvalue * plan["comparison_family_size"]),
            "treatment_mean": m1,
            "control_mean": m0,
            "treatment_n": n1,
            "control_n": n0,
        },
        "losses": losses,
        "sample_ratio_mismatch_pvalue": srm,
        "guardrails": guardrails,
        "cost_per_conversion": cost_ratio,
        "power_at_planned_effect": planned_power,
        "power_interpretation": "Normal approximation at prespecified baseline/MDE and observed sample sizes, not post-hoc observed-effect power",
        "population_verified": bool(plan.get("population_column")),
        "measurement_window_verified": bool(plan.get("date_column")),
        "verification_scope": "Declared eligibility values and date containment only; not authenticated assignment, population completeness, follow-up adequacy or compliance with stopping rules",
        "causal_identification": False,
        "warnings": [
            "Imported group labels do not prove random assignment, population or measurement-window compliance.",
            "Complete-case analysis may be biased by missing outcomes; inspect attrition.",
            "Observational/before-after results are unadjusted associations, not randomized effects.",
            "No automatic model calibration or live action is performed.",
        ],
    }
