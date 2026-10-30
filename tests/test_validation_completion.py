"""Data-quality screens must report edge cases without silently repairing inputs."""

from copy import deepcopy

import pytest
from test_growth_edges import cohort_frame, cohort_request
from test_materialization import normalized_model_data

from mmm_intelligence.errors import MMMError
from mmm_intelligence.growth_analytics import cohort_analysis
from mmm_intelligence.materialization import materialize
from mmm_intelligence.media_validation import eligibility, validate_media
from mmm_intelligence.quality import assess
from mmm_intelligence.schemas import TrainRequest
from mmm_intelligence.universal_schemas import EligibilityRequest, PreparationRequest


@pytest.mark.parametrize(
    "changes", [{"population_column": "eligible"}, {"population_value": "yes"}]
)
def test_cohort_population_pair_is_required(changes):
    with pytest.raises(MMMError, match="together"):
        cohort_analysis(cohort_frame(), cohort_request(**changes))


def test_cohort_missing_first_entry_eligibility_is_refused():
    data = cohort_frame()
    data["rows"][0].pop("eligible")
    with pytest.raises(MMMError, match="First entry"):
        cohort_analysis(data, cohort_request(population_column="eligible", population_value="yes"))


def test_quality_missing_malformed_long_date_ranges_and_empty_values(dataset):
    request = TrainRequest(dataset_id="demo")
    damaged = deepcopy(dataset)
    damaged["rows"][1]["date"] = "invalid"
    assert not assess(damaged, request, 1000)["valid"]
    damaged["rows"] = []
    report = assess(damaged, request, 1000)
    assert not report["valid"] and report["columns"]["revenue"]["present_finite"] == 0
    damaged["rows"] = [{"date": "1900-01-01"}, {"date": "2026-01-01"}]
    assert not assess(damaged, request, 1000)["valid"]


def test_quality_constant_collinear_and_level_shift_screens(dataset):
    for i, row in enumerate(dataset["rows"]):
        row["spend_search"] = 1
        row["spend_social"] = i + 1
        row["spend_video"] = 2 * (i + 1)
        row["revenue"] = 10 if i < len(dataset["rows"]) // 2 else 100
    report = assess(dataset, TrainRequest(dataset_id="demo"), 1000)
    codes = {a["code"] for a in report["alerts"]}
    assert {"CONSTANT_MEDIA", "COLLINEARITY_SCREEN", "LEVEL_SHIFT_SCREEN"} <= codes


@pytest.mark.parametrize(
    "case",
    [
        "invalid_date",
        "null",
        "numeric",
        "unit",
        "rates",
        "audience",
        "gaps",
        "strategy",
        "missing",
        "unknown",
    ],
)
def test_media_quality_explicit_failures(service, case):
    data = normalized_model_data(service)
    row = data["rows"][0]
    if case == "invalid_date":
        row["date"] = "invalid"
    if case == "null":
        row["revenue"] = None
    if case == "numeric":
        row["revenue"] = True
    if case == "unit":
        data["profile"]["expected_units"] = {"revenue": "USD"}
    if case == "rates":
        row.update(clicks=20, impressions=10, ctr=2, cpc=0, spend=1)
        data["units"].update(
            clicks="count", impressions="count", ctr="ratio", cpc="BRL", spend="USD"
        )
    if case == "audience":
        data["profile"]["name"] = "tv"
        row["audience"] = 100
    if case == "gaps":
        data["rows"].pop(1)
    if case == "strategy":
        data["profile"]["name"] = "search_ads"
        data["dimensions"]["strategy"] = "organic"
    if case == "missing":
        row.pop("revenue")
    if case == "unknown":
        data["units"].pop("revenue")
    report = validate_media(data)
    assert (
        report["errors"]
        or report["warnings"]
        or report["dataset_applicability"]["state"] != "applicable"
    )
    if case == "rates":
        assert any("clicks_exceed" in x for x in report["warnings"])


@pytest.mark.parametrize(
    "case,reason",
    [
        ("frequency", "frequency"),
        ("revenue_currency", "Revenue KPI"),
        ("strategy", "compatible media profile"),
        ("duplicate", "one observation"),
        ("overlap", "distinct"),
        ("missing", "Missing or nonnumeric"),
        ("constant", "Insufficient variation"),
        ("correlation", "Highly correlated"),
        ("controls", "No controls"),
        ("definition", "outcome measurement"),
    ],
)
def test_engine_screen_reports_specific_design_failure(service, case, reason):
    data = normalized_model_data(service)
    args = dict(
        artifact_id=data["artifact_id"],
        kpi="revenue",
        media=["spend_search", "spend_social"],
        controls=["price_index"],
        target_type="revenue",
    )
    if case == "frequency":
        data["frequency_days"] = 2
    if case == "revenue_currency":
        data["units"]["revenue"] = "USD"
    if case == "strategy":
        data["profile"]["name"] = "search_ads"
        data["dimensions"]["strategy"] = "organic"
    if case == "duplicate":
        data["rows"].append(dict(data["rows"][0]))
    if case == "overlap":
        args["controls"] = ["spend_search"]
    if case == "missing":
        data["rows"][0]["revenue"] = None
    if case == "constant":
        for row in data["rows"]:
            row["revenue"] = 0
    if case == "correlation":
        for row in data["rows"]:
            row["spend_social"] = 2 * row["spend_search"]
    if case == "controls":
        args["controls"] = []
    if case == "definition":
        data["dimensions"].pop("kpi_definition")
    report = eligibility(data, EligibilityRequest(**args))
    assert not report["eligible"]
    assert any(reason in r for r in report["blocking_reasons"]), report


@pytest.mark.parametrize(
    "frequency,currency,code", [(2, "BRL", "ENGINE_FREQUENCY"), (7, "USD", "MEDIA_UNIT")]
)
def test_materialization_host_currency_and_frequency(service, frequency, currency, code):
    data = normalized_model_data(service)
    data["frequency_days"] = frequency
    request = PreparationRequest(
        artifact_id=data["artifact_id"],
        kpi="revenue",
        media=["spend_search"],
        controls=["price_index"],
        target_type="revenue",
        currency=currency,
    )
    with pytest.raises(MMMError) as caught:
        materialize(data, request, 1000)
    assert caught.value.code == code


def test_materialization_checks_full_model_validation_after_design_screen(service):
    data = normalized_model_data(service)
    request = PreparationRequest(
        artifact_id=data["artifact_id"],
        kpi="revenue",
        media=["spend_search"],
        controls=["price_index"],
        target_type="revenue",
        currency="BRL",
    )
    # Screen is about design. The host row cap is separately enforced at materialization.
    with pytest.raises(MMMError) as caught:
        materialize(data, request, 52)
    assert caught.value.code == "DATASET_INVALID"
