"""Declared joins must preserve totals or abstain before writing artifacts."""

from copy import deepcopy

import pytest

from mmm_intelligence.errors import MMMError
from mmm_intelligence.joins import combine, prepare
from mmm_intelligence.universal_schemas import JoinRequest


def table(rows, **overrides):
    return {
        "artifact_id": "source",
        "rows": rows,
        "frequency_days": 7,
        "timezone": "UTC",
        "dimensions": {"channel": "test"},
        "units": {"value": "count"},
        "synthetic": True,
        "profile": {"nonadditive": ["reach"]},
        **overrides,
    }


def request(**overrides):
    return JoinRequest(
        **{"left_id": "left", "right_id": "right", "keys": {"date": "date"}, **overrides}
    )


@pytest.mark.parametrize(
    "rows,keys,rules,frequency,code",
    [
        ([], ["date"], {}, "original", "JOIN_KEYS"),
        ([{"other": 1}], ["date"], {}, "original", "JOIN_KEYS"),
        ([{"date": None}], ["date"], {}, "original", "JOIN_KEYS"),
        ([{"id": "a"}], ["id"], {}, "weekly", "JOIN_TIME"),
        (
            [{"date": "2026-01-05", "value": 1}],
            ["date"],
            {"wrong": "sum"},
            "original",
            "JOIN_AGGREGATION",
        ),
        (
            [{"date": "2026-01-05", "reach": 10}],
            ["date"],
            {"reach": "sum"},
            "original",
            "NONADDITIVE",
        ),
        (
            [{"date": "2026-01-05", "value": "a"}],
            ["date"],
            {"value": "sum"},
            "original",
            "JOIN_AGGREGATION",
        ),
        (
            [{"date": "2026-01-05", "value": True}],
            ["date"],
            {"value": "sum"},
            "original",
            "JOIN_AGGREGATION",
        ),
    ],
)
def test_invalid_preaggregation_is_explicit(rows, keys, rules, frequency, code):
    with pytest.raises(MMMError) as caught:
        prepare(table(rows), keys, rules, frequency)
    assert caught.value.code == code


def test_weekly_alignment_and_mean_preserve_originals():
    data = table(
        [{"date": "2026-01-05", "value": 10}, {"date": "2026-01-06", "value": 20}], frequency_days=1
    )
    original = deepcopy(data)
    assert prepare(data, ["date"], {"value": "mean"}, "weekly") == [
        {"date": "2026-01-05", "value": 15}
    ]
    assert data == original
    data["rows"][0]["value"] = None
    assert prepare(data, ["date"], {"value": "sum"}, "weekly")[0]["value"] is None


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"unmatched": "error"}, "Unmatched"),
        ({"cardinality": "m:1"}, "cardinality"),
    ],
)
def test_preview_reports_reasons_and_confirmation_refuses(changes, reason):
    a = table([{"date": "2026-01-05", "value": 10}])
    b = table([{"date": "2026-01-12", "sales": 2}])
    preview = combine(a, b, request(**changes), 10)
    assert preview["blocked"] and any(reason in message for message in preview["blocking_reasons"])
    with pytest.raises(MMMError, match="join|Join|records|cardinality"):
        combine(a, b, request(**changes, confirm=True), 10)


def test_alignment_cannot_invent_daily_values_from_weekly_series():
    a = table([{"date": "2026-01-05", "value": 10}])
    b = table([{"date": "2026-01-05", "sales": 2}], frequency_days=1)
    with pytest.raises(MMMError, match="finer|upsampl"):
        combine(a, b, request(frequency="daily", confirm=True), 10)


def test_empty_result_collision_limit_timezone_and_context_guards():
    a = table([{"date": "2026-01-05", "value": 10}])
    b = table([{"date": "2026-01-12", "sales": 2}])
    with pytest.raises(MMMError) as error:
        combine(a, b, request(confirm=True), 10)
    assert error.value.code == "EMPTY_JOIN"
    b["rows"] = [{"date": "2026-01-05", "value": 2, "value_right": 3}]
    with pytest.raises(MMMError) as error:
        combine(a, b, request(), 10)
    assert error.value.code == "JOIN_COLUMNS"
    b = table([{"date": "2026-01-05", "sales": 2}], timezone="America/Sao_Paulo", frequency_days=1)
    b["dimensions"]["currency"] = "USD"
    a["dimensions"]["currency"] = "BRL"
    preview = combine(a, b, request(), 0)
    assert len(preview["blocking_reasons"]) == 4
    b["timezone"] = "UTC"
    joined = combine(
        a,
        b,
        request(
            frequency="weekly",
            context={"currency": "BRL after separately reviewed conversion"},
            confirm=True,
        ),
        10,
    )
    assert joined["join_diagnostics"]["context_conflicts"] == ["currency"]
    assert joined["frequency_days"] == 7


def test_nonunique_right_key_mapping_rejected():
    a = table([{"date": "2026-01-05", "value": 10}])
    with pytest.raises(MMMError) as error:
        combine(a, a, request(keys={"date": "date", "value": "date"}), 10)
    assert error.value.code == "JOIN_KEYS"
