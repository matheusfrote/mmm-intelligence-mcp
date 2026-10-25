"""Constrained budget optimization of the local concave Hill-one model."""

import numpy as np
from scipy.optimize import minimize

from .errors import MMMError
from .schemas import OptimizeRequest, SimulateRequest
from .scientific import decision_support
from .simulation import check_model, plan_design, simulate


def optimize(model: dict, request: OptimizeRequest) -> dict:
    trained = check_model(model)
    names = trained.media_columns
    if set(request.lower) - set(names) or set(request.upper) - set(names):
        raise MMMError("CHANNEL_MISMATCH", "Bounds reference unmodeled channels")
    total = request.total_budget
    lower = np.array([request.lower.get(c, 0) for c in names], float)
    upper = np.array([request.upper.get(c, total) for c in names], float)
    if np.any(lower > upper) or lower.sum() > total + 1e-8 or upper.sum() < total - 1e-8:
        raise MMMError("INFEASIBLE_BUDGET", "Channel bounds cannot satisfy the total budget")
    if total == 0:
        fractions = np.full(len(names), 1 / len(names))
        success, message = True, "Zero budget feasible"
    else:
        lo, hi = lower / total, upper / total
        initial = lo.copy()
        room = hi - lo
        if room.sum() > 0:
            initial += (1 - initial.sum()) * room / room.sum()
        t = np.arange(1, request.horizon + 1)

        def value_gradient(weights):
            value, gradient = 0.0, []
            for j, c in enumerate(names):
                p = model["media_parameters"][c]
                retained = p["decay"] ** t
                factor = (1 - retained) * total / request.horizon
                stock = retained * model["state"]["terminal_adstock"][c] + factor * weights[j]
                k, b = p["half_saturation"], model["coefficients"][c]
                value += float(np.sum(b * stock / (k + stock)))
                gradient.append(float(np.sum(b * k / (k + stock) ** 2 * factor)))
            return -value, -np.array(gradient)

        scale = max(abs(value_gradient(initial)[0]), 1.0)
        result = minimize(
            lambda w: value_gradient(w)[0] / scale,
            initial,
            jac=lambda w: value_gradient(w)[1] / scale,
            method="SLSQP",
            bounds=list(zip(lo, hi)),
            constraints={
                "type": "eq",
                "fun": lambda w: w.sum() - 1,
                "jac": lambda w: np.ones(len(w)),
            },
            options={"maxiter": 300, "ftol": 1e-12},
        )
        fractions = result.x
        if (
            not result.success
            or abs(fractions.sum() - 1) > 1e-8
            or (fractions < lo - 1e-8).any()
            or (fractions > hi + 1e-8).any()
            or value_gradient(fractions)[0] > value_gradient(initial)[0] + 1e-6
        ):
            raise MMMError("OPTIMIZATION_FAILED", "Solver failed feasibility or improvement checks")
        success, message = bool(result.success), str(result.message)
    # Remove insignificant numerical bound violations, then conserve the budget.
    fractions = np.maximum(fractions, 0)
    fractions /= fractions.sum()
    scenario = simulate(
        model,
        SimulateRequest(
            model_id=request.model_id,
            horizon=request.horizon,
            total_budget=total,
            allocation=dict(zip(names, fractions.tolist())),
            future_controls=request.future_controls,
        ),
    )
    recent = np.array([model["state"]["reference_spend_per_period"][c] for c in names])
    reference_fractions = (
        recent / recent.sum() if recent.sum() > 0 else np.full(len(names), 1 / len(names))
    )
    comparable = simulate(
        model,
        SimulateRequest(
            model_id=request.model_id,
            horizon=request.horizon,
            total_budget=total,
            allocation=dict(zip(names, reference_fractions.tolist())),
            future_controls=request.future_controls,
        ),
    )
    controls = (
        np.array([scenario["future_controls"][c] for c in trained.control_columns]).T
        if trained.control_columns
        else np.empty((request.horizon, 0))
    )
    difference_design = (
        plan_design(model, scenario["spend_per_period"], controls, request.horizon)
        - plan_design(model, comparable["spend_per_period"], controls, request.horizon)
    ).sum(axis=0)
    interval = None
    if model.get("coefficient_draws"):
        interval = np.quantile(
            np.asarray(model["coefficient_draws"]) @ difference_design, [0.05, 0.95]
        ).tolist()
    marginal = {}
    for c in names:
        p = model["media_parameters"][c]
        retained = p["decay"] ** np.arange(1, request.horizon + 1)
        stock = (
            retained * model["state"]["terminal_adstock"][c]
            + (1 - retained) * scenario["spend_per_period"][c]
        )
        marginal[c] = float(
            np.sum(
                model["coefficients"][c]
                * p["half_saturation"]
                / (p["half_saturation"] + stock) ** 2
                * (1 - retained)
                / request.horizon
            )
        )
    support = decision_support(model, scenario["warnings"])
    return {
        "model_id": request.model_id,
        "optimal_spend": dict(zip(names, (fractions * total).tolist())),
        "recommended_spend": None,
        "decision_support": support,
        "comparison_same_total": {
            "reference_spend": dict(zip(names, (reference_fractions * total).tolist())),
            "reference_definition": "Recent spending shares rescaled to the same requested total; equal shares if recent total is zero",
            "reference_predicted_total": comparable["predicted_total"],
            "candidate_predicted_total": scenario["predicted_total"],
            "predicted_difference": scenario["predicted_total"] - comparable["predicted_total"],
            "conditional_difference_interval_90": interval,
            "changes": {
                c: {
                    "recent_horizon_spend": float(recent[j] * request.horizon),
                    "candidate_spend": float(fractions[j] * total),
                    "absolute_change": float(fractions[j] * total - recent[j] * request.horizon),
                    "percent_change": float(
                        100 * (fractions[j] * total / (recent[j] * request.horizon) - 1)
                    )
                    if recent[j]
                    else None,
                }
                for j, c in enumerate(names)
            },
        },
        "marginal_kpi_per_spend": marginal,
        "marginal_definition": "Derivative of the conditional KPI total with respect to a channel's whole-horizon flat spending; same historical carryover. Not causal mROI or profit.",
        "solver": {
            "success": success,
            "message": message,
            "objective": "conditional KPI total",
            "form": "concave Hill exponent one with nonnegative media coefficients",
        },
        "lower": dict(zip(names, lower.tolist())),
        "upper": dict(zip(names, upper.tolist())),
        "scenario": scenario,
        "warnings": [
            "MODEL_OPTIMUM_ONLY: no causal, profit or operational guarantee",
            *scenario["warnings"],
        ],
    }
