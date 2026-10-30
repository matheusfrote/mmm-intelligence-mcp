from copy import deepcopy

import pytest


def test_canonical_ridge_recomputes_metrics_and_exposes_capabilities(service, trained):
    out = service.call("get_analysis", {"backend": "ridge", "model_id": "fit"})
    assert out.ok, out.error
    assert out.data["schema_version"] == "1.0"
    assert out.data["metrics"]["mae"] == trained["metrics"]["test"]["mae"]
    assert out.data["capabilities"]["future_projection"]["available"]
    assert not out.data["decision_support"]["business_recommendation_eligible"]
    assert out.data["source"]["dataset_sha256"] == trained["dataset_sha256"]


def test_compare_identical_windows_is_exact_and_has_no_winner(service, trained):
    service.call("train_mmm", {"dataset_id": "demo", "model_id": "second", "ridge_alpha": 1.0})
    out = service.call(
        "compare_models",
        {
            "models": [
                {"backend": "ridge", "model_id": "fit"},
                {"backend": "ridge", "model_id": "second"},
            ]
        },
    )
    assert out.ok, out.error
    assert out.data["comparison_window"]["rows"] == trained["split"]["test_rows"]
    assert out.data["winner"] is None
    assert len(out.data["models"]) == 2
    assert out.data["same_training_window"]
    assert out.data["fair_training_protocol"] is None


def test_intersection_aligns_interval_arrays_to_the_reported_dates(service, trained):
    from mmm_intelligence.canonical import compare

    first = service.call("get_analysis", {"model_id": "fit"}).data
    first["intervals"] = {"type": "fixture", "lower": list(range(32)), "upper": list(range(1, 33))}
    other = deepcopy(first)
    other["model_id"] = "fixture"
    other["evaluation"] = other["evaluation"][2:]
    other["intervals"]["lower"] = other["intervals"]["lower"][2:]
    other["intervals"]["upper"] = other["intervals"]["upper"][2:]
    result = compare([first, other], "intersection")
    aligned = result["models"][0]["evaluation_intervals"]
    assert aligned["dates"] == result["comparison_window"]["dates"]
    assert aligned["lower"] == list(range(2, 32))
    assert "lower" not in result["models"][0]["interval_semantics"]


def test_comparison_rejects_different_data_or_target(service, trained):
    service.call("generate_demo_dataset", {"dataset_id": "different", "seed": 44})
    service.call("train_mmm", {"dataset_id": "different", "model_id": "other"})
    out = service.call(
        "compare_models",
        {
            "models": [
                {"backend": "ridge", "model_id": "fit"},
                {"backend": "ridge", "model_id": "other"},
            ]
        },
    )
    assert out.error.code == "INCOMPARABLE_MODELS"


def test_comparison_requires_explicit_common_window(service, trained):
    service.call("train_mmm", {"dataset_id": "demo", "model_id": "shorter", "test_fraction": 0.1})
    req = {
        "models": [
            {"backend": "ridge", "model_id": "fit"},
            {"backend": "ridge", "model_id": "shorter"},
        ]
    }
    assert service.call("compare_models", req).error.code == "INCOMPARABLE_WINDOWS"
    out = service.call("compare_models", {**req, "window_policy": "intersection"})
    assert out.ok
    assert out.data["comparison_window"]["rows"] == 16
    assert out.data["training_windows_differ"]
    assert not out.data["fair_training_protocol"]


def test_native_canonical_uses_original_observations_and_preserves_diagnostics(service, dataset):
    # Contract fixture, NOT a native runtime execution or statistical validation.
    from mmm_intelligence.storage import digest

    native = {
        "backend": "pymc_marketing",
        "backend_version": "contract-fixture",
        "synthetic": True,
        "dataset": dataset,
        "dataset_id": "demo",
        "dataset_sha256": digest(dataset),
        "model_id": "native",
        "cutoff": 124,
        "native_base64": "private",
        "request": {
            "target_column": "revenue",
            "date_column": "date",
            "media_columns": ["spend_search", "spend_social", "spend_video"],
            "control_columns": ["price_index", "promotion"],
            "seed": 42,
        },
        "test": {
            "dates": [r["date"] for r in dataset["rows"][124:]],
            "mean": [r["revenue"] for r in dataset["rows"][124:]],
            "interval_type": "posterior_predictive_observed",
        },
        "diagnostics": {"r_hat_max": 1.2},
        "warnings": ["fixture"],
    }
    service.store.write("backend_models", "native", native)
    out = service.call("get_analysis", {"backend": "pymc_marketing", "model_id": "native"})
    assert out.ok, out.error
    assert out.data["metrics"]["mae"] == 0
    assert out.data["diagnostic_assessment"]["status"] == "inadequate"
    assert "native_base64" not in str(out.data)
    bad = deepcopy(native)
    bad["backend"] = "meta_robyn"
    service.store.write("backend_models", "wrong", bad)
    assert (
        service.call("get_analysis", {"backend": "pymc_marketing", "model_id": "wrong"}).error.code
        == "BACKEND_MISMATCH"
    )


@pytest.mark.parametrize("backend", ["google_meridian", "meta_robyn"])
def test_unsupported_future_operations_are_explicit(service, backend):
    out = service.call("model_capabilities", {"backend": backend})
    assert out.ok
    assert not out.data["future_projection"]["available"]
    assert not out.data["optimization"]["available"]
    assert out.data["future_projection"]["reason"]
