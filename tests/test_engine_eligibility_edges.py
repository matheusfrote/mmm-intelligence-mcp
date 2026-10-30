"""Eligibility must predict adapter input incompatibilities before materialization."""

import pytest
from test_materialization import normalized_model_data
from test_universal import call


@pytest.mark.parametrize("backend", ["ridge", "google_meridian", "pymc_marketing", "meta_robyn"])
@pytest.mark.parametrize(
    "problem", ["exposure_not_spend", "mixed_currency", "frequency", "column_name"]
)
def test_backend_eligibility_reports_structural_and_unit_blocks(service, backend, problem):
    frame = normalized_model_data(service)
    media = ["spend_search", "spend_social", "spend_video"]
    if problem == "exposure_not_spend":
        frame["units"]["spend_search"] = "count"
    elif problem == "mixed_currency":
        frame["units"]["spend_search"] = "USD"
    elif problem == "frequency":
        frame["frequency_days"] = 14
        # Preserve an internally regular fortnightly series to isolate the adapter constraint.
        from datetime import date, timedelta

        for i, row in enumerate(frame["rows"]):
            row["date"] = (date(2023, 1, 2) + timedelta(days=14 * i)).isoformat()
    else:
        column = "media_" + "x" * 65
        for row in frame["rows"]:
            row[column] = row.pop("spend_search")
        frame["units"][column] = frame["units"].pop("spend_search")
        frame["profile"]["required"] = [
            column if key == "spend_search" else key for key in frame["profile"]["required"]
        ]
        media[0] = column
    frame = service._growth_save("normalized", frame)
    result = call(
        service,
        "check_mmm_eligibility",
        artifact_id=frame["artifact_id"],
        backend=backend,
        kpi="revenue",
        media=media,
        controls=["price_index", "promotion"],
        target_type="revenue",
    )
    assert not result["eligible"], problem
    assert result["blocking_reasons"]


def test_geo_dimension_requires_explicit_aggregation_before_training(service):
    frame = normalized_model_data(service)
    duplicated = []
    for row in frame["rows"]:
        duplicated.extend([{**row, "region": "one"}, {**row, "region": "two"}])
    frame["rows"] = duplicated
    frame = service._growth_save("normalized", frame)
    result = call(
        service,
        "check_mmm_eligibility",
        artifact_id=frame["artifact_id"],
        backend="google_meridian",
        kpi="revenue",
        media=["spend_search"],
        controls=["price_index"],
        target_type="revenue",
    )
    assert not result["eligible"] and any(
        "one observation per date" in reason for reason in result["blocking_reasons"]
    )
