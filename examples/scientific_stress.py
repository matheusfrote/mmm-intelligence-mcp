"""Controlled synthetic failure tests. These are not market or business results."""

import argparse
import copy
import json
from pathlib import Path

import numpy as np

from mmm_intelligence.config import Settings
from mmm_intelligence.datasets import generate
from mmm_intelligence.schemas import GenerateRequest
from mmm_intelligence.service import MMMService


def cases():
    baseline = generate(GenerateRequest(seed=42))
    result = {
        name: copy.deepcopy(baseline)
        for name in [
            "baseline",
            "collinear",
            "tracking_break",
            "null_media_effect",
            "zeros_in_kpi",
            "all_media_zero",
            "missing_target",
            "duplicate_date",
            "irregular_series",
            "short_history",
            "negative_media_effect",
        ]
    }
    for row in result["collinear"]["rows"]:
        row["spend_social"] = 2 * row["spend_search"]
    for row in result["tracking_break"]["rows"][-32:]:
        row["revenue"] *= 10
    rng = np.random.default_rng(718)
    for i, row in enumerate(result["null_media_effect"]["rows"]):
        row["revenue"] = float(
            5000 + 2 * i + 300 * np.sin(2 * np.pi * i * 7 / 365.25) + rng.normal(0, 30)
        )
    for row in result["negative_media_effect"]["rows"]:
        row["revenue"] = 15000.0 - 2 * row["spend_search"]
    for row in result["zeros_in_kpi"]["rows"]:
        row["revenue"] = 0.0
    for row in result["all_media_zero"]["rows"]:
        for c in ("spend_search", "spend_social", "spend_video"):
            row[c] = 0.0
    result["missing_target"]["rows"][-1]["revenue"] = None
    result["duplicate_date"]["rows"][-1]["date"] = result["duplicate_date"]["rows"][-2]["date"]
    result["irregular_series"]["rows"][-1]["date"] = "2025-12-23"
    result["short_history"]["rows"] = result["short_history"]["rows"][:30]
    for name, dataset in result.items():
        dataset["source"] = "scientific-stress-v1"
        dataset["data_context"] = {
            "source_reference": "constructed-seed42-718",
            "tracking_notes": name + "; fabricated stress case, not a business observation",
        }
    return result


def run(data_dir: Path):
    report = {
        "synthetic": True,
        "scope": "Controlled software/math stress tests; no business or causal certification",
        "cases": {},
    }
    svc = MMMService(Settings(data_dir))
    try:
        for name, dataset in cases().items():
            svc.store.write("datasets", name, dataset)
            quality = svc.call("validate_dataset", {"dataset_id": name})
            fitted = svc.call(
                "train_mmm", {"dataset_id": name, "model_id": name, "bootstrap_samples": 20}
            )
            out = {"data_quality": quality.data, "train_ok": fitted.ok}
            if not fitted.ok:
                out["error"] = fitted.error.model_dump()
                assert name in {
                    "missing_target",
                    "duplicate_date",
                    "irregular_series",
                    "short_history",
                    "all_media_zero",
                }
            else:
                assert name not in {
                    "missing_target",
                    "duplicate_date",
                    "irregular_series",
                    "short_history",
                    "all_media_zero",
                }
                out["metrics"] = fitted.data["metrics"]
                model = svc.store.read("models", name)
                out["diagnostics"] = model["diagnostics"]
                total = float(sum(model["state"]["reference_spend_per_period"].values()) * 13)
                out["budgets"] = []
                for multiplier in (0.5, 1.0, 2.0):
                    candidate = svc.call(
                        "optimize_budget", {"model_id": name, "total_budget": total * multiplier}
                    )
                    assert candidate.ok, candidate.error
                    data = candidate.data
                    assert np.isclose(sum(data["optimal_spend"].values()), total * multiplier)
                    assert data["recommended_spend"] is None
                    assert not data["decision_support"]["business_recommendation_eligible"]
                    out["budgets"].append(
                        {
                            "multiplier": multiplier,
                            "solver": data["solver"],
                            "decision_support": data["decision_support"],
                            "optimal_spend": data["optimal_spend"],
                            "comparison_same_total": data["comparison_same_total"],
                            "warnings": data["warnings"],
                        }
                    )
            report["cases"][name] = out
    finally:
        svc.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = run(args.output_dir / "private-data")
    (args.output_dir / "result.json").write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {"synthetic": True, "cases": list(result["cases"]), "business_recommendations": 0}
        )
    )


if __name__ == "__main__":
    main()
