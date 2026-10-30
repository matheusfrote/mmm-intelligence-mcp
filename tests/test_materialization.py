"""A materialized dataset must actually train through the existing service."""

import json

import pytest
from test_universal import call, source

from mmm_intelligence.datasets import generate
from mmm_intelligence.schemas import GenerateRequest


def normalized_model_data(service):
    rows = generate(GenerateRequest())["rows"]
    profile = call(
        service,
        "register_media_profile",
        name="model_frame",
        version="1",
        family="marketing",
        required=list(rows[0]),
        optional=[],
    )
    raw = source(service, json.dumps(rows), "json")
    return call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile=profile["artifact_id"],
        mapping={c: c for c in rows[0]},
        units={
            c: ("BRL" if c.startswith("spend_") or c == "revenue" else "index")
            for c in rows[0]
            if c != "date"
        },
        dimensions={
            "channel": "explicit_multi",
            "strategy": "paid",
            "kpi_definition": "synthetic revenue",
        },
    )


@pytest.mark.parametrize("backend", ["ridge", "google_meridian", "pymc_marketing", "meta_robyn"])
def test_preparation_returns_consumable_request_and_lineage(service, backend):
    mapped = normalized_model_data(service)
    result = call(
        service,
        "prepare_mmm_dataset",
        artifact_id=mapped["artifact_id"],
        backend=backend,
        kpi="revenue",
        media=["spend_search", "spend_social", "spend_video"],
        controls=["price_index", "promotion"],
        target_type="revenue",
        currency="BRL",
    )
    dataset = service.load_dataset(result["dataset_id"])
    assert dataset["source_ids"] == [mapped["artifact_id"]] and dataset["target_type"] == "revenue"
    assert result["training_request"]["dataset_id"] == result["dataset_id"]
    if backend == "ridge":
        fit = call(service, "train_mmm", **result["training_request"])
        assert fit["metrics"]["test"]["mae"] >= 0
    else:
        assert result["training_request"]["backend"] == backend


def test_meridian_refuses_nonmonetary_kpi_before_worker(service):
    mapped = normalized_model_data(service)
    result = service.call(
        "prepare_mmm_dataset",
        dict(
            artifact_id=mapped["artifact_id"],
            backend="google_meridian",
            kpi="revenue",
            media=["spend_search"],
            controls=["price_index"],
            target_type="non_revenue",
            currency="BRL",
        ),
    )
    assert not result.ok
