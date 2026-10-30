"""Missingness, cohort population rules and temporal support are explicit."""

import numpy as np
import pytest
from test_temporal_methods import frame, request

from mmm_intelligence.errors import MMMError
from mmm_intelligence.growth_analytics import cohort_analysis, temporal_analysis
from mmm_intelligence.universal_schemas import CohortRequest


def test_temporal_missing_small_duplicate_and_invalid_metrics():
    data = frame(range(4))
    assert temporal_analysis(data, request())["suppressed_groups"] == 1
    data = frame(range(10))
    del data["rows"][0]["sales"]
    with pytest.raises(MMMError, match="Missing"):
        temporal_analysis(data, request())
    data = frame(range(10))
    data["rows"][0]["sales"] = None
    result = temporal_analysis(data, request(lag_pairs=[{"spend": "spend", "outcome": "sales"}]))
    assert result["groups"][0]["metrics"]["sales"]["status"] == "insufficient"
    assert result["groups"][0]["lag_associations"][0]["status"] == "insufficient"
    data["rows"][0]["sales"] = True
    with pytest.raises(MMMError, match="finite numeric"):
        temporal_analysis(data, request())
    data = frame(range(10))
    data["rows"][1]["date"] = data["rows"][0]["date"]
    with pytest.raises(MMMError, match="one observation"):
        temporal_analysis(data, request())


@pytest.mark.parametrize(
    "pair",
    [
        {"spend": "spend"},
        {"spend": "spend", "outcome": "spend"},
        {"spend": "spend", "outcome": "absent"},
    ],
)
def test_lag_pairs_require_distinct_present_selected_metrics(pair):
    with pytest.raises(MMMError):
        temporal_analysis(frame(range(20)), request(lag_pairs=[pair]))


def test_zero_baseline_anomaly_seasonality_and_sorting():
    result = temporal_analysis(frame([0] * 4 + [1] * 4), request())
    assert result["groups"][0]["metrics"]["sales"]["percent_change"] is None
    data = frame([*range(19), 1000])
    data["rows"].reverse()
    metric = temporal_analysis(data, request())["groups"][0]["metrics"]["sales"]
    assert metric["robust_anomaly_dates"] == [max(row["date"] for row in data["rows"])]
    for count, step in [(104, 7), (730, 1)]:
        seasonal = temporal_analysis(frame(range(count), step=step), request())["groups"][0][
            "metrics"
        ]["sales"]
        assert seasonal["seasonal_lag_correlation"] == pytest.approx(1)
    noisy = temporal_analysis(frame(np.random.default_rng(71).normal(10, 1, 100)), request())[
        "groups"
    ][0]["metrics"]["sales"]
    assert noisy["level_change_candidate"] is None


def cohort_request(**changes):
    return CohortRequest(
        **{
            "artifact_id": "events",
            "unit_column": "unit",
            "event_column": "event",
            "entry_event": "entry",
            "return_event": "return",
            "as_of": "2026-02-01",
            "horizon": 3,
            **changes,
        }
    )


def cohort_frame():
    return {
        "artifact_id": "events",
        "synthetic": True,
        "rows": [
            row
            for i in range(10)
            for row in [
                {
                    "unit": str(i),
                    "date": "2026-01-05",
                    "event": "entry",
                    "region": "BR",
                    "eligible": "yes",
                },
                {
                    "unit": str(i),
                    "date": "2026-01-06",
                    "event": "return",
                    "region": "BR",
                    "eligible": "yes",
                },
            ]
        ],
    }


def test_cohort_duplicate_future_missing_entry_and_suppression():
    data = cohort_frame()
    data["rows"] += [
        dict(data["rows"][0]),
        {"unit": "future", "date": "2026-03-01", "event": "entry", "region": "BR"},
        {"unit": "no-entry", "date": "2026-01-05", "event": "return", "region": "BR"},
        {"unit": "tiny", "date": "2026-01-06", "event": "entry", "region": "Other"},
    ]
    result = cohort_analysis(data, cohort_request(group_by=["region"], cumulative=True))
    assert result["duplicate_events"] == 1 and result["future_events_excluded"] == 1
    assert result["suppressed_groups"] == 1
    assert result["cohorts"][0]["periods"][1]["rate"] == 1
    assert "unit" not in str(result["cohorts"])
    del data["rows"][0]["unit"]
    with pytest.raises(MMMError):
        cohort_analysis(data, cohort_request())


def test_cohort_conflicting_duplicate_dimensions_are_not_silently_deduplicated():
    data = cohort_frame()
    data["rows"].append({**data["rows"][0], "region": "conflict"})
    with pytest.raises(MMMError) as caught:
        cohort_analysis(data, cohort_request(group_by=["region"]))
    assert caught.value.code == "COHORT_GRAIN"


def test_cohort_population_is_explicit_and_uses_first_entry():
    data = cohort_frame()
    for row in data["rows"]:
        if row["unit"] in {"0", "1"}:
            row["eligible"] = "no"
    result = cohort_analysis(
        data, cohort_request(population_column="eligible", population_value="yes")
    )
    assert result["excluded_ineligible_units"] == 2
    assert result["cohorts"][0]["entry_population"] == 8
