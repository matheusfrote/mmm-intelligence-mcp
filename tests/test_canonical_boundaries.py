"""Metadata fixtures test canonical contracts; native execution is tested separately."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from mmm_intelligence.canonical import bundle, compare
from mmm_intelligence.errors import MMMError
from mmm_intelligence.schemas import AnalysisRequest, CompareRequest
from mmm_intelligence.storage import digest


def native(dataset):
    return {
        "backend": "pymc_marketing",
        "backend_version": "metadata-contract-fixture",
        "synthetic": True,
        "dataset": dataset,
        "dataset_id": "demo",
        "dataset_sha256": digest(dataset),
        "model_id": "native",
        "cutoff": 124,
        "request": {
            "target_column": "revenue",
            "date_column": "date",
            "media_columns": ["spend_search", "spend_social", "spend_video"],
            "control_columns": ["price_index", "promotion"],
        },
        "test": {
            "dates": [row["date"] for row in dataset["rows"][124:]],
            "mean": [row["revenue"] for row in dataset["rows"][124:]],
            "interval_type": "unavailable",
        },
        "diagnostics": {},
        "warnings": [],
    }


def test_canonical_bundle_refuses_wrong_lineage_backend_and_duplicate_dates(dataset):
    model = native(dataset)
    request = AnalysisRequest(model_id="native", backend="pymc_marketing")
    with pytest.raises(MMMError) as caught:
        bundle({**model, "dataset_sha256": "wrong"}, dataset, request)
    assert caught.value.code == "LINEAGE_MISMATCH"
    with pytest.raises(MMMError) as caught:
        bundle(model, dataset, AnalysisRequest(model_id="native", backend="meta_robyn"))
    assert caught.value.code == "BACKEND_MISMATCH"
    for dates in [["missing"] * 32, model["test"]["dates"][:-1], [model["test"]["dates"][0]] * 32]:
        with pytest.raises(MMMError) as caught:
            bundle({**model, "test": {**model["test"], "dates": dates}}, dataset, request)
        assert caught.value.code == "CORRUPT_MODEL"


def test_comparison_needs_five_common_periods_and_matching_interval_lengths(service, trained):
    base = service.call("get_analysis", {"model_id": "fit"}).data
    other = deepcopy(base)
    other["model_id"] = "second"
    other["evaluation"] = other["evaluation"][-4:]
    with pytest.raises(MMMError) as caught:
        compare([base, other], "intersection")
    assert caught.value.code == "INCOMPARABLE_WINDOWS"
    other = deepcopy(base)
    other["model_id"] = "second"
    other["intervals"] = {"lower": [0], "upper": [1]}
    with pytest.raises(MMMError) as caught:
        compare([base, other], "exact")
    assert caught.value.code == "CORRUPT_MODEL"


def test_comparison_same_model_cannot_be_reported_as_independent_validation():
    with pytest.raises(ValidationError):
        CompareRequest(models=[AnalysisRequest(model_id="fit"), AnalysisRequest(model_id="fit")])
