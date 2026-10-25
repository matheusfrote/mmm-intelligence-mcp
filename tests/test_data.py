import copy

import pytest

from mmm_intelligence.datasets import generate, validate
from mmm_intelligence.schemas import GenerateRequest, TrainRequest


def test_deterministic_demo_and_daily():
    a = generate(GenerateRequest())
    assert a == generate(GenerateRequest())
    daily = generate(GenerateRequest(frequency="daily", periods=730))
    assert daily["synthetic"] is True
    assert validate(daily, TrainRequest(dataset_id="x"), 10000)["valid"]


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_column", "MISSING_COLUMNS"),
        ("none", "INVALID_VALUES"),
        ("nan", "INVALID_VALUES"),
        ("infinity", "INVALID_VALUES"),
        ("string", "INVALID_VALUES"),
        ("bool", "INVALID_VALUES"),
        ("negative", "NEGATIVE_VALUES"),
        ("duplicate", "DUPLICATE_DATES"),
        ("gap", "IRREGULAR_SERIES"),
        ("unsorted", "UNSORTED_DATES"),
        ("date", "INVALID_DATE"),
        ("huge", "INVALID_VALUES"),
        ("short", "ROW_COUNT"),
    ],
)
def test_validation_defects(dataset, mutation, code):
    data = copy.deepcopy(dataset)
    rows = data["rows"]
    if mutation == "missing_column":
        del rows[5]["revenue"]
    if mutation in {"none", "nan", "infinity", "string", "bool", "negative", "huge"}:
        rows[5]["revenue"] = {
            "none": None,
            "nan": float("nan"),
            "infinity": float("inf"),
            "string": "100",
            "bool": True,
            "negative": -1,
            "huge": 10**400,
        }[mutation]
    if mutation == "duplicate":
        rows[5]["date"] = rows[4]["date"]
    if mutation == "gap":
        rows.pop(5)
    if mutation == "unsorted":
        rows.reverse()
    if mutation == "date":
        rows[5]["date"] = "2024-02-30"
    if mutation == "short":
        data["rows"] = rows[:40]
    report = validate(data, TrainRequest(dataset_id="x"), 10000)
    assert not report["valid"]
    assert any(code in issue for issue in report["issues"])


def test_split_insufficient_and_constant_warning(dataset):
    dataset["rows"] = dataset["rows"][:52]
    for row in dataset["rows"]:
        row["promotion"] = 1
    result = validate(dataset, TrainRequest(dataset_id="x", warmup_periods=52), 10000)
    assert not result["valid"]
    assert "CONSTANT_COLUMN: promotion" in result["warnings"]


def test_iso_week_date_not_silently_accepted(dataset):
    dataset["rows"][0]["date"] = "2023-W01-1"
    report = validate(dataset, TrainRequest(dataset_id="x"), 10000)
    assert not report["valid"]
    assert any("INVALID_DATE" in issue for issue in report["issues"])
