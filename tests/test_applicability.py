"""Applicability and data quality are different axes."""

import pytest
from test_universal import call, source

from mmm_intelligence.media_validation import PROFILES, validate_media


def test_print_circulation_is_not_applicable_to_search_ads(service):
    raw = source(service, "date,circulation\n2026-01-01,100\n")
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={"date": "date", "circulation": "circulation"},
        units={"circulation": "copies"},
        dimensions={"channel": "search", "strategy": "paid"},
    )
    report = call(service, "validate_media_dataset", artifact_id=mapped["artifact_id"])
    assert report["dataset_applicability"]["state"] == "not_applicable"
    assert report["field_applicability"]["circulation"]["state"] == "not_applicable"
    assert report["status"] != "invalid" and not report["growth_compatible"]


def test_unknown_applicability_is_not_automatically_invalid(service):
    raw = source(service, "date\n2026-01-01\n")
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="website",
        mapping={"date": "date"},
    )
    report = call(service, "validate_media_dataset", artifact_id=mapped["artifact_id"])
    assert report["dataset_applicability"]["state"] == "undetermined"
    assert report["status"] == "insufficient"


def test_custom_profile_versions_are_discoverable_by_immutable_id(service):
    versions = [
        call(
            service,
            "register_media_profile",
            name="custom_demo",
            version=str(i),
            family="custom",
            required=["date"],
            optional=["custom_metric"],
        )
        for i in [1, 2]
    ]
    available = call(service, "list_media_profiles")["profiles"]
    ids = {p.get("artifact_id") for p in available}
    assert {v["artifact_id"] for v in versions} <= ids
    assert len({v["artifact_id"] for v in versions}) == 2


@pytest.mark.parametrize("profile_name", sorted(PROFILES))
def test_each_versioned_profile_has_applicable_quality_separate_from_strategy(profile_name):
    profile = PROFILES[profile_name]
    metric = "insertions" if profile_name in {"tv", "radio", "print"} else "clicks"
    strategy = "organic" if profile_name.endswith("_organic") or profile_name == "seo" else "paid"
    frame = {
        "rows": [{"date": "2026-01-05", metric: 10}],
        "profile": profile,
        "units": {metric: "count"},
        "dimensions": {"channel": profile_name, "strategy": strategy},
        "frequency_days": 7,
    }
    report = validate_media(frame)
    assert report["status"] == "valid"
    assert report["dataset_applicability"]["state"] == "applicable"
    assert report["analysis_applicability"]["growth"]["state"] == "applicable"


def test_organic_data_is_not_invalid_when_selected_paid_profile_does_not_apply():
    frame = {
        "rows": [{"date": "2026-01-05", "clicks": 10}],
        "profile": PROFILES["search_ads"],
        "units": {"clicks": "count"},
        "dimensions": {"channel": "search", "strategy": "organic"},
        "frequency_days": 7,
    }
    report = validate_media(frame)
    assert report["dataset_applicability"]["state"] == "not_applicable"
    assert report["status"] == "valid_with_warnings"
    assert not report["errors"] and not report["growth_compatible"]


def test_analysis_destination_refuses_metric_outside_selected_profile(service):
    raw = source(
        service,
        "date,clicks,circulation\n2026-01-05,10,100\n2026-01-12,11,101\n2026-01-19,12,102\n2026-01-26,13,103\n2026-02-02,14,104\n",
    )
    frame = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={key: key for key in ["date", "clicks", "circulation"]},
        units={"clicks": "count", "circulation": "copies"},
        dimensions={"channel": "search", "strategy": "paid"},
    )
    rejected = service.call(
        "analyze_growth", {"artifact_id": frame["artifact_id"], "metrics": ["circulation"]}
    )
    assert not rejected.ok and rejected.error.code == "ANALYSIS_APPLICABILITY"
    accepted = call(service, "analyze_growth", artifact_id=frame["artifact_id"], metrics=["clicks"])
    assert accepted["input_quality"]["status"] == "valid"
