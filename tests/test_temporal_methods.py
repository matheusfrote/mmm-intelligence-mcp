"""Descriptive temporal methods have explicit independent numerical expectations."""

from datetime import date, timedelta

import numpy as np
import pytest

from mmm_intelligence.growth_analytics import temporal_analysis
from mmm_intelligence.universal_schemas import GrowthAnalysisRequest


def frame(values, outcome=None, step=7):
    return {
        "artifact_id": "frame",
        "synthetic": True,
        "frequency_days": step,
        "rows": [
            {
                "date": (date(2024, 1, 1) + timedelta(days=i * step)).isoformat(),
                "spend": float(value),
                "sales": float(outcome[i] if outcome is not None else value),
            }
            for i, value in enumerate(values)
        ],
        "units": {"spend": "BRL", "sales": "count"},
    }


def request(**kwargs):
    return GrowthAnalysisRequest(artifact_id="frame", metrics=["spend", "sales"], **kwargs)


def test_bic_level_change_identifies_known_synthetic_step():
    data = frame([10] * 20 + [30] * 20)
    series = temporal_analysis(data, request())["groups"][0]["metrics"]["sales"]
    candidate = series["level_change_candidate"]
    assert candidate["date"] == data["rows"][20]["date"]
    assert candidate["before_mean"] == 10 and candidate["after_mean"] == 30
    assert candidate["causal_identification"] is False


def test_constant_short_and_irregular_series_abstain_from_level_change():
    for data in [frame([10] * 40), frame(range(6)), frame(range(20))]:
        if len(data["rows"]) == 20:
            data["rows"][-1]["date"] = "2025-01-01"
        metric = temporal_analysis(data, request())["groups"][0]["metrics"]["sales"]
        assert metric["level_change_candidate"] is None


def test_lag_screen_uses_spend_before_outcome_without_causal_selection():
    spend = np.random.default_rng(42).uniform(1, 50, 60)
    sales = np.r_[0, 0, spend[:-2]]
    data = frame(spend, sales)
    result = temporal_analysis(
        data, request(lag_pairs=[{"spend": "spend", "outcome": "sales"}], max_lag=4)
    )
    lag = result["groups"][0]["lag_associations"][0]
    assert lag["correlations"][2]["correlation"] == pytest.approx(1)
    assert lag["correlations"][2]["paired_observations"] == 58
    assert lag["causal_identification"] is False
