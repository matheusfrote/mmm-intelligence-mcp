"""Independent expectations for trends, censoring and experimental statistics."""

import json
from datetime import date, timedelta

import pytest
from test_universal import call, source


def test_trend_period_change_and_rolling_mean(service):
    rows = [
        {"date": (date(2026, 1, 1) + timedelta(weeks=i)).isoformat(), "sales": float(i + 1)}
        for i in range(10)
    ]
    raw = source(service, json.dumps(rows), "json")
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="website",
        mapping={"date": "date", "sales": "sales"},
        units={"sales": "count"},
        dimensions={"channel": "web", "strategy": "organic"},
    )
    result = call(
        service,
        "analyze_growth",
        artifact_id=mapped["artifact_id"],
        metrics=["sales"],
        rolling_window=3,
    )
    series = result["groups"][0]["metrics"]["sales"]
    assert series["absolute_change"] == 5
    assert series["rolling_mean"][2] == 2
    assert series["slope_per_day"] == pytest.approx(1 / 7)
    assert result["causal_identification"] is False


def test_cohort_eligibility_does_not_mark_censored_units_lost(service):
    rows = []
    for i in range(10):
        rows += [
            {"unit": str(i), "event": "entry", "date": "2026-01-01"},
            {"unit": str(i), "event": "return", "date": "2026-01-02"},
        ]
    raw = source(service, json.dumps(rows), "json")
    result = call(
        service,
        "analyze_cohorts",
        artifact_id=raw["artifact_id"],
        unit_column="unit",
        event_column="event",
        date_column="date",
        entry_event="entry",
        return_event="return",
        as_of="2026-01-07",
        horizon=2,
        frequency_days=7,
    )
    cells = result["cohorts"][0]["periods"]
    assert cells[0]["rate"] == 1 and cells[0]["eligible"] == 10
    assert cells[1]["rate"] is None and cells[1]["censored"] == 10


def test_binary_experiment_estimate_and_power_are_not_causal_proof(service):
    rows = [
        {
            "unit": str(i),
            "arm": "control" if i < 100 else "treatment",
            "outcome": int(i % 10 < (2 if i < 100 else 4)),
        }
        for i in range(200)
    ]
    raw = source(service, json.dumps(rows), "json")
    plan = call(
        service,
        "plan_experiment",
        method="randomized",
        outcome_type="binary",
        kpi="outcome",
        unit_column="unit",
        group_column="arm",
        treatment="treatment",
        control="control",
        baseline=0.2,
        minimum_effect=0.1,
        power=0.8,
        alpha=0.05,
        population="fabricated units",
        measurement_window="2026-01-01/2026-02-01",
        stop_rule="fixed horizon",
        guardrails=["spend"],
    )
    assert plan["sample_size_per_arm"] > 100
    result = call(
        service, "analyze_experiment", artifact_id=raw["artifact_id"], plan_id=plan["artifact_id"]
    )
    assert result["estimate"]["difference"] == pytest.approx(0.2)
    assert result["estimate"]["interval"][0] < 0.2 < result["estimate"]["interval"][1]
    assert result["causal_identification"] is False and result["synthetic"]


def test_continuous_experiment_empty_group_is_rejected(service):
    raw = source(service, json.dumps([{"unit": "1", "arm": "control", "y": 10}]), "json")
    plan = call(
        service,
        "plan_experiment",
        method="observational",
        outcome_type="continuous",
        kpi="y",
        unit_column="unit",
        group_column="arm",
        treatment="treatment",
        control="control",
        baseline=10,
        standard_deviation=2,
        minimum_effect=1,
        power=0.8,
        alpha=0.05,
        population="fixture",
        measurement_window="fixed observed period",
        stop_rule="fixed horizon",
        guardrails=["quality"],
    )
    result = service.call(
        "analyze_experiment", {"artifact_id": raw["artifact_id"], "plan_id": plan["artifact_id"]}
    )
    assert not result.ok


def test_cohort_followup_cell_suppresses_small_effective_denominator(service):
    rows = []
    for i in range(5):
        rows.extend(
            [
                {"unit": str(i), "event": "entry", "date": f"2026-01-{5 + i:02d}"},
                {"unit": str(i), "event": "return", "date": f"2026-01-{5 + i:02d}"},
            ]
        )
    raw = source(service, json.dumps(rows), "json")
    result = call(
        service,
        "analyze_cohorts",
        artifact_id=raw["artifact_id"],
        unit_column="unit",
        event_column="event",
        entry_event="entry",
        return_event="return",
        as_of="2026-01-11",
        horizon=1,
    )
    cell = result["cohorts"][0]["periods"][0]
    assert cell["eligible"] == 1 and cell["rate"] is None and cell["retained"] is None
