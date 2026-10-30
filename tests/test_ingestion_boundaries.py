"""Existing CSV transformations reject ambiguous data and preserve declared totals."""

import pytest

from mmm_intelligence.errors import MMMError
from mmm_intelligence.ingestion import parse_csv, reporting_timezone
from mmm_intelligence.schemas import CSVImportRequest


def request(text, **kwargs):
    return CSVImportRequest(
        csv_text=text,
        synthetic=True,
        authorization_reference="synthetic fixture",
        target_column="sales",
        media_columns=["spend"],
        control_columns=[],
        **kwargs,
    )


@pytest.mark.parametrize(
    "text,options,code",
    [
        ("\n", {}, "CSV_HEADER"),
        ("date,sales,sales\n2026-01-01,1,1", {}, "CSV_HEADER"),
        ("date,,spend\n2026-01-01,1,1", {}, "CSV_HEADER"),
        ("date,sales,spend\n2026-01-01,1,1", {"column_mapping": {"absent": "sales"}}, "CSV_HEADER"),
        ("a,sales,spend\n2026-01-01,1,1", {"column_mapping": {"a": "sales"}}, "CSV_HEADER"),
        ("date,sales,spend\n2026-01-01,1", {}, "CSV_ROW"),
        ("date,sales,spend\n2026-01-01,1,-1", {}, "CSV_VALUE"),
        ("date,sales,spend\n2026-01-01,NaN,1", {}, "CSV_VALUE"),
        ("date,sales,spend\n2026-01-01,1e13,1", {}, "CSV_VALUE"),
        (
            "date;sales;spend\n2026-01-01;1.000,00;1",
            {"delimiter": ";", "decimal_separator": ","},
            "CSV_VALUE",
        ),
        ("date,sales,spend\n2026-1-1,1,1", {}, "CSV_VALUE"),
        (
            "date,sales,spend\n2026-01-01,1,1",
            {"date_format": "iso_datetime", "timezone": "UTC"},
            "CSV_VALUE",
        ),
        (
            "date,sales,spend\n2026-01-01T00:00:00,1,1",
            {"date_format": "iso_datetime", "timezone": "UTC"},
            "CSV_VALUE",
        ),
        ('date,sales,spend\n"unterminated,1,1', {}, "CSV_PARSE"),
    ],
)
def test_csv_boundary_errors_are_actionable(text, options, code):
    with pytest.raises(MMMError) as caught:
        parse_csv(request(text, **options), max_rows=100, max_bytes=10000)
    assert caught.value.code == code


def test_source_limits_apply_before_unbounded_loading():
    text = "date,sales,spend\n2026-01-01,1,1\n2026-01-08,2,2"
    for rows, limit, code in [(1, 10000, "ROW_LIMIT"), (100, 1, "ARTIFACT_TOO_LARGE")]:
        with pytest.raises(MMMError) as caught:
            parse_csv(request(text), max_rows=rows, max_bytes=limit)
        assert caught.value.code == code


def test_timezone_offset_and_normalization_are_exact():
    assert reporting_timezone("+05:30").utcoffset(None).total_seconds() == 19800
    assert reporting_timezone("-03:00").utcoffset(None).total_seconds() == -10800
    assert str(reporting_timezone("America/Sao_Paulo")) == "America/Sao_Paulo"
    with pytest.raises(MMMError) as caught:
        reporting_timezone("not/a_timezone")
    assert caught.value.code == "TIMEZONE_UNAVAILABLE"
    result = parse_csv(
        request(
            "date,sales,spend\n2026-01-01T23:00:00-03:00,1,1",
            date_format="iso_datetime",
            timezone="UTC",
        ),
        max_rows=100,
        max_bytes=10000,
    )
    assert result["rows"][0]["date"] == "2026-01-02"


def test_partial_calendar_week_cannot_be_labeled_complete():
    text = "date,sales,spend\n2026-01-05,1,1\n2026-01-06,2,2"
    with pytest.raises(MMMError) as caught:
        parse_csv(
            request(
                text,
                aggregate_weekly=True,
                source_frequency="daily",
                reducers={"sales": "sum", "spend": "sum"},
            ),
            max_rows=100,
            max_bytes=10000,
        )
    assert caught.value.code == "INCOMPLETE_PERIOD"
