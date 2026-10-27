"""Reproducible small Monte Carlo study; empirical results, never coverage certification."""

import argparse
import json
from pathlib import Path

import numpy as np

from mmm_intelligence.datasets import validate
from mmm_intelligence.diagnostics import interval_coverage
from mmm_intelligence.modeling import train
from mmm_intelligence.schemas import TrainRequest
from mmm_intelligence.scientific import decision_support, design_for_model
from mmm_intelligence.synthetic import controlled_dataset


def run(seeds=10, draws=100):
    results = []
    regimes = (
        "matched",
        "high_noise",
        "collinear",
        "omitted_price",
        "structural_break",
        "skewed_noise",
    )
    for regime in regimes:
        for seed in range(seeds):
            data, truth = controlled_dataset(
                seed=seed,
                noise_sd=500 if regime == "high_noise" else 50,
                collinear=regime == "collinear",
            )
            cutoff = len(data["rows"]) - int(np.ceil(len(data["rows"]) * 0.2))
            expected = np.asarray(truth["conditional_mean"]).copy()
            if regime == "structural_break":
                expected[cutoff:] *= 1.25
                for row in data["rows"][cutoff:]:
                    row["revenue"] *= 1.25
            if regime == "skewed_noise":
                noise = 150 * (
                    np.random.default_rng(seed + 10000).lognormal(0, 1, len(expected)) - np.exp(0.5)
                )
                for row, mean, error in zip(data["rows"], expected, noise):
                    row["revenue"] = float(mean + error)
            req = TrainRequest(
                dataset_id="controlled",
                ridge_alpha=1e-5,
                bootstrap_samples=draws,
                bootstrap_seed=seed + 100,
                bootstrap_block_size=4,
                control_columns=["promotion"]
                if regime == "omitted_price"
                else ["price_index", "promotion"],
            )
            report = validate(data, req, 10000)
            assert report["valid"], report["issues"]
            model = train(data, req, "study", report)
            samples = np.asarray(model["coefficient_draws"])
            lo, hi = np.quantile(samples, [0.05, 0.95], axis=0)
            parameter_results = {}
            for channel, actual in truth["media_coefficients"].items():
                i = model["feature_names"].index(channel)
                parameter_results[channel] = {
                    "true": actual,
                    "estimate": model["coefficients"][channel],
                    "error": model["coefficients"][channel] - actual,
                    "covered": bool(lo[i] <= actual <= hi[i]),
                }
            prediction_draws = samples @ design_for_model(data, model)[cutoff:].T
            low, high = np.quantile(prediction_draws, [0.05, 0.95], axis=0)
            results.append(
                {
                    "regime": regime,
                    "seed": seed,
                    "parameters": parameter_results,
                    "conditional_mean": interval_coverage(
                        expected[cutoff:], low, high, "conditional_mean"
                    ),
                    "metrics": model["metrics"]["test"],
                    "decision": decision_support(model),
                }
            )
    summary = {}
    for regime in regimes:
        subset = [r for r in results if r["regime"] == regime]
        summary[regime] = {
            "replications": seeds,
            "mean_conditional_mean_coverage": float(
                np.mean([r["conditional_mean"]["empirical_coverage"] for r in subset])
            ),
            "mean_holdout_mae": float(np.mean([r["metrics"]["mae"] for r in subset])),
            "channels": {
                c: {
                    "mean_absolute_coefficient_error": float(
                        np.mean([abs(r["parameters"][c]["error"]) for r in subset])
                    ),
                    "parameter_coverage": float(
                        np.mean([r["parameters"][c]["covered"] for r in subset])
                    ),
                }
                for c in truth["media_coefficients"]
            },
            "all_abstained": all(
                not r["decision"]["business_recommendation_eligible"] for r in subset
            ),
        }
    return {
        "synthetic": True,
        "seeds": list(range(seeds)),
        "bootstrap_draws": draws,
        "nominal_conditional_interval": 0.9,
        "coverage_certified": False,
        "scope": "Small matched fixed-shape experiment plus intentional misspecification. Time points are dependent; replications are the independent units. Null coefficients are constrained at a boundary. No prior sensitivity or native MCMC coverage tested.",
        "summary": summary,
        "replications": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
