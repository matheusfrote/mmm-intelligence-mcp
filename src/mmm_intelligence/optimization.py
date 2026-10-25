"""Constrained budget optimization of the local concave Hill-one model."""

import numpy as np
from scipy.optimize import minimize

from .errors import MMMError
from .schemas import OptimizeRequest, SimulateRequest
from .simulation import check_model, simulate


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
    return {
        "model_id": request.model_id,
        "optimal_spend": dict(zip(names, (fractions * total).tolist())),
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
