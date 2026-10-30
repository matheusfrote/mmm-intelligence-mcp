import csv
import io
from datetime import date, timedelta

import pytest


def csv_request(dataset):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(dataset["rows"][0]))
    writer.writeheader()
    writer.writerows(dataset["rows"])
    return {
        "csv_text": stream.getvalue(),
        "synthetic": True,
        "authorization_reference": "synthetic-test",
        "target_type": "revenue",
    }


def test_csv_roundtrip_preserves_original_and_mapping(service, dataset):
    req = csv_request(dataset)
    req["csv_text"] = req["csv_text"].replace("date,revenue", "Data,Vendas")
    req["column_mapping"] = {"Data": "date", "Vendas": "revenue"}
    out = service.call("import_csv", req)
    assert out.ok, out.error
    stored = service.store.read("datasets", out.data["dataset_id"])
    assert stored["rows"] == dataset["rows"]
    assert stored["provenance"]["original_csv"] == req["csv_text"]
    assert stored["provenance"]["sha256"]
    assert stored["provenance"]["transformations"]
    assert out.data["validation"]["valid"]
    assert service.call("train_mmm", {"dataset_id": out.data["dataset_id"]}).ok


@pytest.mark.parametrize(
    "change",
    ["duplicate_header", "extra_field", "missing", "formula", "nan", "duplicate_date", "unsorted"],
)
def test_csv_bad_inputs_do_not_create_artifacts(service, dataset, change):
    req = csv_request(dataset)
    lines = req["csv_text"].splitlines()
    if change == "duplicate_header":
        lines[0] += ",date"
    elif change == "extra_field":
        lines[1] += ",secret"
    elif change == "missing":
        cells = lines[1].split(",")
        cells[1] = ""
        lines[1] = ",".join(cells)
    elif change in ("formula", "nan"):
        cells = lines[1].split(",")
        cells[1] = "=1+1" if change == "formula" else "nan"
        lines[1] = ",".join(cells)
    elif change == "duplicate_date":
        lines[2] = lines[1]
    else:
        lines[1], lines[2] = lines[2], lines[1]
    req["csv_text"] = "\n".join(lines)
    result = service.call("import_csv", req)
    assert not result.ok
    assert result.error.code in {
        "CSV_HEADER",
        "CSV_ROW",
        "CSV_VALUE",
        "DUPLICATE_DATES",
        "UNSORTED_DATES",
    }
    assert not list((service.store.root / "datasets").glob("*.json"))


def test_csv_real_data_gate_and_no_path_or_url_input(service, dataset):
    req = csv_request(dataset)
    req["synthetic"] = False
    assert service.call("import_csv", req).error.code == "REAL_DATA_DISABLED"
    req["synthetic"] = True
    req["path"] = "../private.csv"
    assert service.call("import_csv", req).error.code == "INPUT_INVALID"


def test_explicit_daily_to_weekly_aggregation_and_missing_day(service):
    rows = ["when,kpi,ad,price"]
    start = date(2024, 1, 1)
    for i in range(364):
        rows.append(f"{start + timedelta(days=i)},10,2,3")
    req = {
        "csv_text": "\n".join(rows),
        "column_mapping": {"when": "date", "kpi": "revenue", "ad": "spend"},
        "media_columns": ["spend"],
        "control_columns": ["price"],
        "synthetic": True,
        "authorization_reference": "test",
        "source_frequency": "daily",
        "frequency": "weekly",
        "aggregate_weekly": True,
        "reducers": {"revenue": "sum", "spend": "sum", "price": "mean"},
    }
    out = service.call("import_csv", req)
    assert out.ok, out.error
    data = service.store.read("datasets", out.data["dataset_id"])
    assert len(data["rows"]) == 52
    assert data["rows"][0] == {"date": "2024-01-01", "revenue": 70.0, "spend": 14.0, "price": 3.0}
    req["csv_text"] = "\n".join(rows[:2] + rows[3:])
    out = service.call("import_csv", req)
    assert not out.ok and out.error.code == "INCOMPLETE_PERIOD"


def test_timezone_and_duplicates_require_explicit_policies(service, dataset):
    req = csv_request(dataset)
    req["csv_text"] = req["csv_text"].replace("2023-01-02,", "2023-01-02T00:00:00-03:00,")
    assert not service.call("import_csv", req).ok
    req["date_format"] = "iso_datetime"
    req["timezone"] = "UTC"
    # Mixed dates/timestamps are deliberately rejected by one declared parser.
    assert not service.call("import_csv", req).ok


def test_quality_has_severity_and_missing_period_evidence(service, dataset):
    service.store.write(
        "datasets", "gap", {**dataset, "rows": dataset["rows"][:10] + dataset["rows"][11:]}
    )
    out = service.call("data_quality", {"dataset_id": "gap"})
    assert out.ok, out.error
    assert out.data["missing_periods"] == ["2023-03-13"]
    assert any(a["severity"] == "blocking" for a in out.data["alerts"])
    assert not out.data["business_recommendation_eligible"]


def test_quality_outliers_are_reported_without_changing_data(service, dataset):
    import copy

    changed = copy.deepcopy(dataset)
    changed["rows"][20]["spend_search"] *= 100
    service.store.write("datasets", "outlier", changed)
    out = service.call("data_quality", {"dataset_id": "outlier"})
    assert out.ok, out.error
    column = out.data["columns"]["spend_search"]
    assert column["extreme_iqr_count"] >= 1
    assert any(a["code"] == "EXTREME_IQR_SCREEN" for a in out.data["alerts"])
    assert service.store.read("datasets", "outlier") == changed


def test_timestamp_decimal_and_explicit_duplicate_reducers(service, dataset):
    rows = ["date;revenue;ad"]
    for r in dataset["rows"]:
        for _ in range(2):
            rows.append(f"{r['date']}T23:30:00-03:00;10,50;2,25")
    req = {
        "csv_text": "\n".join(reversed(rows[1:])) + "\n",
        "delimiter": ";",
        "decimal_separator": ",",
        "date_format": "iso_datetime",
        "timezone": "UTC",
        "sort_dates": True,
        "duplicate_policy": "aggregate",
        "reducers": {"revenue": "sum", "ad": "sum"},
        "media_columns": ["ad"],
        "control_columns": [],
        "synthetic": True,
        "authorization_reference": "test",
    }
    req["csv_text"] = rows[0] + "\n" + req["csv_text"]
    result = service.call("import_csv", req)
    assert result.ok, result.error
    saved = service.store.read("datasets", result.data["dataset_id"])
    assert saved["rows"][0] == {"date": "2023-01-03", "revenue": 21.0, "ad": 4.5}
    assert len(saved["rows"]) == len(dataset["rows"])
    assert [t["operation"] for t in saved["provenance"]["transformations"]] == [
        "parse",
        "sort_dates",
        "aggregate_duplicates",
    ]


def test_source_limits_apply_before_duplicate_reduction(dataset):
    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.ingestion import parse_csv
    from mmm_intelligence.schemas import CSVImportRequest

    req = CSVImportRequest(**csv_request(dataset))
    with pytest.raises(MMMError, match="source row limit"):
        parse_csv(req, max_rows=10, max_bytes=1000000)
    with pytest.raises(MMMError, match="byte limit"):
        parse_csv(req, max_rows=10000, max_bytes=100)
