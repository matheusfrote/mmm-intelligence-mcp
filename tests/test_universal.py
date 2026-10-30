"""Synthetic file ingestion, semantic validation and immutable learning regressions."""

import base64
import json

import pytest


def call(service, tool, **args):
    result = service.call(tool, args)
    assert result.ok, result.error
    return result.data


def source(service, text, fmt="csv", **kwargs):
    return call(
        service,
        "import_source",
        content_base64=base64.b64encode(text.encode()).decode(),
        format=fmt,
        synthetic=True,
        origin="synthetic fixture",
        confirm=True,
        **kwargs,
    )


@pytest.mark.parametrize(
    "fmt,text",
    [
        ("csv", "day,cost,views\n2026-01-01,10,100\n"),
        ("tsv", "day\tcost\tviews\n2026-01-01\t10\t100\n"),
        ("json", json.dumps([{"day": "2026-01-01", "cost": 10, "views": 100}])),
        ("jsonl", json.dumps({"day": "2026-01-01", "cost": 10, "views": 100})),
    ],
)
def test_preview_confirm_mapping_and_original_survive(service, fmt, text):
    args = dict(
        content_base64=base64.b64encode(text.encode()).decode(),
        format=fmt,
        synthetic=True,
        origin="fixture",
    )
    preview = call(service, "preview_dataset", **args)
    assert preview["row_count"] == 1
    assert not list((service.store.root / "reports").glob("*.json"))
    raw = source(service, text, fmt)
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={"day": "date", "cost": "spend", "views": "impressions"},
        units={"spend": "BRL", "impressions": "count"},
        dimensions={"channel": "search", "strategy": "paid", "platform": "search-example"},
    )
    assert mapped["rows"][0]["spend"] == 10
    original = call(service, "get_growth_artifact", artifact_id=raw["artifact_id"])
    assert base64.b64decode(original["content_base64"]).decode() == text


def test_reject_bad_files_and_real_data(service):
    assert (
        service.call(
            "import_source",
            dict(content_base64="!!", format="csv", synthetic=True, origin="x", confirm=True),
        ).ok
        is False
    )
    args = dict(
        content_base64=base64.b64encode(b"a,a\n1,2").decode(),
        format="csv",
        synthetic=True,
        origin="x",
        confirm=True,
    )
    assert service.call("preview_dataset", args | {"confirm": False}).ok is False
    assert (
        service.call(
            "import_source", args | {"synthetic": False, "authorization_reference": "declared"}
        ).error.code
        == "REAL_DATA_DISABLED"
    )


@pytest.mark.parametrize(
    "profile",
    [
        "tv",
        "radio",
        "print",
        "website",
        "seo",
        "search_ads",
        "youtube_organic",
        "youtube_paid",
        "tiktok_organic",
        "tiktok_paid",
        "kwai_organic",
        "kwai_paid",
        "facebook_organic",
        "facebook_boosted",
        "facebook_ads",
        "instagram_organic",
        "instagram_boosted",
        "instagram_ads",
    ],
)
def test_profiles_do_not_require_inapplicable_spend(service, profile):
    raw = source(service, "date,impressions\n2026-01-01,100\n")
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile=profile,
        mapping={"date": "date", "impressions": "impressions"},
        units={"impressions": "count"},
        dimensions={"channel": profile, "strategy": "declared", "platform": "fixture"},
    )
    report = call(service, "validate_media_dataset", artifact_id=mapped["artifact_id"])
    assert "spend" not in report["missing_required"]
    assert report["mmm_eligible"] is False


def test_bad_rates_missing_unknown_and_custom_profile(service):
    profile = call(
        service,
        "register_media_profile",
        name="custom_creator",
        version="1",
        required=["date", "views"],
        optional=["reach"],
        nonadditive=["reach"],
        family="creator",
    )
    raw = source(service, "day,views,reach\n2026-01-01,100,\n2026-01-01,50,10\n")
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile=profile["artifact_id"],
        mapping={"day": "date", "views": "views", "reach": "reach"},
        units={"views": "count", "reach": "count"},
        dimensions={"channel": "creator"},
    )
    report = call(service, "validate_media_dataset", artifact_id=mapped["artifact_id"])
    assert report["duplicates"] == 1 and report["status"] == "invalid"
    assert mapped["rows"][0]["reach"] is None
    assert not service.call(
        "build_growth_dataset",
        dict(
            artifact_ids=[mapped["artifact_id"]], frequency="weekly", aggregations={"reach": "sum"}
        ),
    ).ok


def test_decision_transitions_and_history(service):
    raw = source(
        service, "date,spend,impressions,clicks\n2026-01-01,10,100,2\n2026-01-08,20,100,1\n"
    )
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={x: x for x in ["date", "spend", "impressions", "clicks"]},
        units={"spend": "BRL", "impressions": "count", "clicks": "count"},
        dimensions={"channel": "search", "strategy": "paid", "platform": "fixture"},
    )
    diagnostic = call(service, "create_growth_diagnostic", artifact_id=mapped["artifact_id"])
    decision = call(
        service,
        "create_growth_decision",
        diagnostic_id=diagnostic["artifact_id"],
        problem="Efficiency changed",
        hypothesis="Landing issue",
        action="Investigate landing",
        kpi="clicks",
        guardrails=["spend"],
        baseline="2026-01-01/2026-01-08",
        horizon="2 weeks",
        method="observational",
        risks=["confounding"],
    )
    invalid = service.call(
        "transition_growth_decision",
        dict(artifact_id=decision["artifact_id"], state="learned", actor="human", note="skip"),
    )
    assert not invalid.ok
    approved = call(
        service,
        "transition_growth_decision",
        artifact_id=decision["artifact_id"],
        state="approved",
        actor="human",
        note="Reviewed",
    )
    assert approved["previous_id"] == decision["artifact_id"]
    assert (
        call(service, "get_growth_artifact", artifact_id=decision["artifact_id"])["state"]
        == "proposed"
    )
    assert not service.call(
        "transition_growth_decision",
        dict(artifact_id=decision["artifact_id"], state="rejected", actor="human", note="stale"),
    ).ok


def test_profiles_are_distinct_and_workbook_active_content_rejected(service):
    profiles = call(service, "list_media_profiles")["profiles"]
    by_name = {p["name"]: p for p in profiles}
    assert "circulation" in by_name["print"]["optional"]
    assert "circulation" not in by_name["search_ads"]["optional"]
    import io

    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    book.active.append(["date", "spend"])
    book.active.append(["2026-01-01", "=1+1"])
    stream = io.BytesIO()
    book.save(stream)
    args = dict(
        content_base64=base64.b64encode(stream.getvalue()).decode(),
        format="xlsx",
        synthetic=True,
        origin="synthetic workbook",
    )
    assert service.call("preview_dataset", args).error.code == "ACTIVE_CONTENT"


def test_transition_cannot_inject_unverified_results(service):
    from mmm_intelligence.universal_schemas import TransitionRequest

    # Invalid field combinations must fail before any history is written.
    request = TransitionRequest(
        artifact_id="decision-test",
        state="approved",
        actor="human",
        note="review",
        results_id="foreign",
    )
    service._growth_save(
        "decision", {"synthetic": True, "state": "proposed", "revision": 0}, "decision-test"
    )
    assert service.call("transition_growth_decision", request.model_dump()).ok is False


def test_aggregation_crossmedia_eligibility_and_complete_learning(service):
    raw = source(
        service,
        "date,spend,clicks,impressions,ctr\n2026-01-05,10,2,100,0.02\n2026-01-06,20,6,200,0.03\n",
    )
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={k: k for k in ["date", "spend", "clicks", "impressions", "ctr"]},
        units={"spend": "BRL", "clicks": "count", "impressions": "count", "ctr": "ratio"},
        dimensions={"channel": "search", "strategy": "paid"},
        frequency_days=1,
    )
    report = call(service, "validate_media_dataset", artifact_id=mapped["artifact_id"])
    assert report["status"] == "valid"
    growth = call(
        service,
        "build_growth_dataset",
        artifact_ids=[mapped["artifact_id"]],
        aggregations={"spend": "sum", "clicks": "sum", "impressions": "sum", "ctr": "ratio"},
        ratios={"ctr": ["clicks", "impressions"]},
    )
    assert growth["observations"][0]["values"]["spend"] == 30
    assert growth["observations"][0]["values"]["ctr"] == pytest.approx(8 / 300)
    cross = call(service, "validate_crossmedia_dataset", artifact_ids=[mapped["artifact_id"]])
    assert cross["crossmedia_reach"] is None and cross["coverage_matrix"]
    eligible = call(
        service,
        "check_mmm_eligibility",
        artifact_id=mapped["artifact_id"],
        kpi="clicks",
        media=["spend"],
    )
    assert eligible["eligible"] is False
    diagnostic = call(service, "create_growth_diagnostic", artifact_id=mapped["artifact_id"])
    decision = call(
        service,
        "create_growth_decision",
        diagnostic_id=diagnostic["artifact_id"],
        problem="change",
        hypothesis="tracking changed",
        action="investigate",
        kpi="clicks",
        guardrails=["spend"],
        baseline="first day",
        horizon="2 weeks",
        method="observational",
        risks=["confounding"],
    )
    approved = call(
        service,
        "transition_growth_decision",
        artifact_id=decision["artifact_id"],
        state="approved",
        actor="human",
        note="review",
    )
    assert not service.call(
        "transition_growth_decision",
        dict(
            artifact_id=approved["artifact_id"],
            state="planned",
            actor="human",
            note="plan",
            plan={},
        ),
    ).ok
    plan = {
        k: "explicit synthetic assumption"
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
    planned = call(
        service,
        "transition_growth_decision",
        artifact_id=approved["artifact_id"],
        state="planned",
        actor="human",
        note="declared",
        plan=plan,
    )
    evaluated = call(
        service,
        "transition_growth_decision",
        artifact_id=planned["artifact_id"],
        state="evaluated",
        actor="human",
        note="Synthetic illustration; no effect inference",
        results_id=raw["artifact_id"],
    )
    learned = call(
        service,
        "transition_growth_decision",
        artifact_id=evaluated["artifact_id"],
        state="learned",
        actor="human",
        note="Measurement must be reconciled",
    )
    assert learned["results_id"] == raw["artifact_id"] and learned["plan"] == plan
    assert learned["external_action_executed"] is False


def test_xlsx_sheets_header_selection_and_limits(service):
    import io
    import zipfile

    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    book.active.title = "data"
    book.active.append(["date", "spend"])
    book.active.append(["2026-01-01", 10])
    book.create_sheet("other")
    stream = io.BytesIO()
    book.save(stream)
    args = dict(
        content_base64=base64.b64encode(stream.getvalue()).decode(),
        format="xlsx",
        synthetic=True,
        origin="fixture",
    )
    assert service.call("preview_dataset", args).error.code == "SHEET_REQUIRED"
    assert call(service, "preview_dataset", **args, sheet="data")["row_count"] == 1
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr("../escape", b"x")
    assert not service.call(
        "preview_dataset", args | {"content_base64": base64.b64encode(zipped.getvalue()).decode()}
    ).ok
    assert not service.call(
        "preview_dataset", args | {"content_base64": base64.b64encode(b"not zip").decode()}
    ).ok


def test_rate_errors_and_temporal_grain_block(service):
    from datetime import date, timedelta

    rows = [
        {
            "date": (date(2026, 1, 1) + timedelta(weeks=i // 2)).isoformat(),
            "campaign": str(i % 2),
            "spend": i + 1,
            "sales": i % 9 + 1,
            "control": i % 3,
        }
        for i in range(52)
    ]
    raw = source(service, json.dumps(rows), "json")
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="search_ads",
        mapping={k: k for k in rows[0] if k != "control"},
        units={"spend": "BRL", "sales": "count"},
        dimensions={"channel": "search", "strategy": "paid", "kpi_definition": "sales"},
    )
    report = call(
        service,
        "check_mmm_eligibility",
        artifact_id=mapped["artifact_id"],
        kpi="sales",
        media=["spend"],
    )
    assert report["eligible"] is False and any(
        "one observation per date" in reason for reason in report["blocking_reasons"]
    )


def test_source_cannot_be_deleted_while_mapping_references_it(service):
    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.lifecycle import delete_artifact
    from mmm_intelligence.storage import digest

    raw = source(service, "date,views\n2026-01-01,10\n")
    call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="youtube_organic",
        mapping={"date": "date", "views": "views"},
        units={"views": "count"},
    )
    with pytest.raises(MMMError):
        delete_artifact(service.store, "reports", raw["artifact_id"], digest(raw))


def test_ambiguous_json_keys_and_offset_date_conversion(service):
    args = dict(
        content_base64=base64.b64encode(b'[{"date":"2026-01-01","views":1,"views":2}]').decode(),
        format="json",
        synthetic=True,
        origin="fixture",
    )
    assert not service.call("preview_dataset", args).ok
    raw = source(service, "time,views\n2026-01-01T23:30:00-0300,1\n")
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="youtube_organic",
        mapping={"time": "date", "views": "views"},
        date_format="%Y-%m-%dT%H:%M:%S%z",
        timezone="UTC",
    )
    assert mapped["rows"][0]["date"] == "2026-01-02"
