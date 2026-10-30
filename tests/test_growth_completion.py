"""Observable rejection and aggregation behavior at the supplied-data boundary."""

import json

import pytest
from test_joins import normalized
from test_universal import call, source


def rejected(service, tool, code, **request):
    result = service.call(tool, request)
    assert not result.ok and result.error.code == code, result


def test_artifact_type_and_import_confirmation(service):
    record = service._growth_save("unsupported", {"synthetic": True})
    rejected(service, "get_growth_artifact", "ARTIFACT_TYPE", artifact_id=record["artifact_id"])
    import base64

    rejected(
        service,
        "import_source",
        "CONFIRM_REQUIRED",
        content_base64=base64.b64encode(b"a\n1\n").decode(),
        format="csv",
        synthetic=True,
        origin="synthetic",
    )


@pytest.mark.parametrize(
    "required,optional",
    [(["date", "date"], []), (["sales"], []), (["date", ""], []), (["date"], ["x" * 81])],
)
def test_invalid_profile_fields(service, required, optional):
    rejected(
        service,
        "register_media_profile",
        "PROFILE_INVALID",
        name="custom",
        family="test",
        version="1",
        required=required,
        optional=optional,
    )


@pytest.mark.parametrize(
    "row,mapping,code",
    [
        ({"day": "2026-01-01", "v": 1}, {"absent": "date"}, "MAPPING_INVALID"),
        ({"day": "2026-01-01", "v": 1}, {"day": "date", "v": "date"}, "MAPPING_INVALID"),
        ({"day": "2026-01-01", "v": 1}, {"day": "date", "v": "unknown"}, "MAPPING_INVALID"),
        ({"day": "2026-01-01", "v": True}, {"day": "date", "v": "spend"}, "MAPPING_INVALID"),
        ({"day": "2026-01-01", "v": "inf"}, {"day": "date", "v": "spend"}, "MAPPING_INVALID"),
    ],
)
def test_mapping_refuses_ambiguous_semantics(service, row, mapping, code):
    raw = source(service, json.dumps([row]), "json")
    rejected(
        service,
        "map_dataset_schema",
        code,
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping=mapping,
    )


def test_mapping_nulls_and_timezone_preserve_declared_meaning(service):
    raw = source(
        service,
        json.dumps([{"day": "2026-01-01T01:00:00+0000", "v": None, "ch": "search"}]),
        "json",
    )
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={"day": "date", "v": "spend", "ch": "channel"},
        date_format="%Y-%m-%dT%H:%M:%S%z",
        timezone="America/Sao_Paulo",
    )
    assert mapped["rows"] == [{"date": "2025-12-31", "spend": None, "channel": "search"}]
    raw = source(service, "day\n2026-01-01T01:00:00\n")
    rejected(
        service,
        "map_dataset_schema",
        "DATE_AMBIGUOUS",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={"day": "date"},
        date_format="%Y-%m-%dT%H:%M:%S",
    )


def test_growth_quality_abstention_and_crossmedia_context(service):
    a = normalized(service, "date,spend\n2026-01-01,-1\n")
    rejected(
        service,
        "build_growth_dataset",
        "INVALID_MEDIA",
        artifact_ids=[a["artifact_id"]],
        aggregations={"spend": "sum"},
    )
    rejected(
        service,
        "analyze_growth",
        "ANALYSIS_QUALITY",
        artifact_id=a["artifact_id"],
        metrics=["spend"],
    )
    b = {
        **a,
        "rows": [{"date": "2026-02-01", "spend": 2}],
        "frequency_days": 1,
        "timezone": "Europe/London",
        "units": {"spend": "USD"},
    }
    b = service._growth_save("normalized", b)
    cross = call(
        service, "validate_crossmedia_dataset", artifact_ids=[a["artifact_id"], b["artifact_id"]]
    )
    assert cross["shared_dates"] == []
    assert {
        "Different frequency_days",
        "Different timezone",
        "Incompatible unit: spend",
        "No common periods",
    } <= set(cross["incompatibilities"])


def aggregate(service, csv, **changes):
    data = normalized(service, csv)
    if "ctr" in data["units"]:
        data = service._growth_save(
            "normalized", {**data, "units": {**data["units"], "ctr": "ratio"}}
        )
    return service.call("build_growth_dataset", {"artifact_ids": [data["artifact_id"]], **changes})


def test_every_metric_requires_explicit_aggregation(service):
    result = aggregate(service, "date,spend\n2026-01-05,10\n")
    assert result.error.code == "AGGREGATION_REQUIRED"
    result = aggregate(service, "date,reach\n2026-01-05,10\n", aggregations={"reach": "sum"})
    assert result.error.code == "NONADDITIVE"


@pytest.mark.parametrize("weight", [None, "missing", "spend"])
def test_weighted_mean_refuses_absent_and_zero_weights(service, weight):
    result = aggregate(
        service,
        "date,spend,clicks\n2026-01-05,0,10\n2026-01-06,0,20\n",
        aggregations={"spend": "sum", "clicks": "weighted_mean"},
        weights={} if weight is None else {"clicks": weight},
    )
    assert result.error.code == "WEIGHT_INVALID"


def test_weighted_and_daily_aggregation_and_optional_null(service):
    # Empty optional impressions remain unknown; required spend/clicks stay valid.
    raw = source(
        service,
        json.dumps(
            [
                {"date": "2026-01-05", "spend": 2, "clicks": 10, "impressions": None},
                {"date": "2026-01-06", "spend": 6, "clicks": 20, "impressions": None},
            ]
        ),
        "json",
    )
    data = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={k: k for k in ["date", "spend", "clicks", "impressions"]},
        units={"spend": "BRL", "clicks": "count", "impressions": "count"},
    )
    result = call(
        service,
        "build_growth_dataset",
        artifact_ids=[data["artifact_id"]],
        aggregations={"spend": "sum", "clicks": "weighted_mean", "impressions": "sum"},
        weights={"clicks": "spend"},
    )
    assert result["observations"][0]["values"] == {
        "date": "2026-01-05",
        "spend": 8,
        "clicks": 17.5,
        "impressions": None,
    }
    daily = call(
        service,
        "build_growth_dataset",
        artifact_ids=[data["artifact_id"]],
        frequency="daily",
        aggregations={"spend": "sum", "clicks": "sum", "impressions": "sum"},
    )
    assert len(daily["observations"]) == 2


@pytest.mark.parametrize("ratios", [{}, {"ctr": ["clicks", "absent"]}])
def test_ratio_requires_declared_available_components(service, ratios):
    result = aggregate(
        service,
        "date,spend,clicks,impressions,ctr\n2026-01-05,0,0,10,0\n",
        aggregations={"spend": "sum", "clicks": "sum", "impressions": "sum", "ctr": "ratio"},
        ratios=ratios,
    )
    assert result.error.code == "RATIO_INVALID"


def test_decision_requires_matching_plan_and_results(service):
    common = {"actor": "synthetic reviewer", "note": "unit boundary"}
    approved = service._growth_save(
        "decision",
        {
            "synthetic": True,
            "state": "approved",
            "revision": 0,
            "kpi": "sales",
            "method": "randomized",
        },
    )
    assumptions = {
        k: "declared"
        for k in [
            "hypothesis",
            "unit",
            "window",
            "duration",
            "sample_assumptions",
            "control",
            "success",
            "stop",
            "guardrails",
        ]
    }
    experiment = service._growth_save(
        "experiment_plan", {"synthetic": True, "kpi": "other", "method": "randomized"}
    )
    rejected(
        service,
        "transition_growth_decision",
        "PLAN_INCOMPATIBLE",
        artifact_id=approved["artifact_id"],
        state="planned",
        plan={**assumptions, "experiment_plan_id": experiment["artifact_id"]},
        **common,
    )
    planned = call(
        service,
        "transition_growth_decision",
        artifact_id=approved["artifact_id"],
        state="planned",
        plan=assumptions,
        **common,
    )
    rejected(
        service,
        "transition_growth_decision",
        "RESULTS_REQUIRED",
        artifact_id=planned["artifact_id"],
        state="evaluated",
        **common,
    )
    result = service._growth_save(
        "experiment_result",
        {"synthetic": True, "plan_id": experiment["artifact_id"], "kpi": "sales"},
    )
    rejected(
        service,
        "transition_growth_decision",
        "PLAN_INCOMPATIBLE",
        artifact_id=planned["artifact_id"],
        state="evaluated",
        results_id=result["artifact_id"],
        **common,
    )
