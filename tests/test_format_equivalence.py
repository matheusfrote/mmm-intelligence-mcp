"""Real files must converge to the same canonical rows, not merely parse."""

import base64
import csv
import io
import json

import pytest
from test_universal import call

ROWS = [
    {"date": "2026-01-05", "spend": 10.5, "impressions": 100},
    {"date": "2026-01-12", "spend": 0, "impressions": 200},
]


def encoded(fmt):
    stream = io.BytesIO()
    options = {}
    if fmt in {"csv", "tsv"}:
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=ROWS[0], delimiter="\t" if fmt == "tsv" else ",")
        writer.writeheader()
        writer.writerows(ROWS)
        raw = text.getvalue().encode()
    elif fmt in {"json", "jsonl"}:
        raw = (json.dumps(ROWS) if fmt == "json" else "\n".join(map(json.dumps, ROWS))).encode()
    elif fmt == "xlsx":
        from openpyxl import Workbook

        book = Workbook()
        book.active.append(list(ROWS[0]))
        for row in ROWS:
            book.active.append(list(row.values()))
        book.save(stream)
        raw = stream.getvalue()
    elif fmt == "xls":
        import xlwt

        book = xlwt.Workbook()
        sheet = book.add_sheet("data")
        for i, row in enumerate([list(ROWS[0]), *[list(r.values()) for r in ROWS]]):
            for j, value in enumerate(row):
                sheet.write(i, j, value)
        book.save(stream)
        raw = stream.getvalue()
    elif fmt == "parquet":
        import pyarrow as pa
        import pyarrow.parquet as pq

        pq.write_table(pa.Table.from_pylist(ROWS), stream, compression="zstd")
        raw = stream.getvalue()
    else:
        raw = (
            "<root>"
            + "".join(
                "<record>" + "".join(f"<{k}>{v}</{k}>" for k, v in row.items()) + "</record>"
                for row in ROWS
            )
            + "</root>"
        ).encode()
        options = {"xml_record": "record", "xml_fields": {k: k for k in ROWS[0]}}
    return raw, options


@pytest.mark.parametrize("fmt", ["csv", "tsv", "json", "jsonl", "xlsx", "xls", "parquet", "xml"])
def test_formats_are_equivalent_through_persisted_pipeline(service, fmt):
    raw, options = encoded(fmt)
    arguments = {
        "format": fmt,
        "content_base64": base64.b64encode(raw).decode(),
        "synthetic": True,
        "origin": "equivalence fixture",
        **options,
    }
    preview = call(service, "preview_dataset", **arguments)
    assert preview["row_count"] == 2
    source = call(service, "import_source", **arguments, confirm=True)
    mapped = call(
        service,
        "map_dataset_schema",
        source_id=source["artifact_id"],
        profile="search_ads",
        mapping={k: k for k in ROWS[0]},
        units={"spend": "BRL", "impressions": "count"},
        dimensions={"channel": "search", "strategy": "paid"},
    )
    assert mapped["rows"] == ROWS
    validation = call(service, "validate_media_dataset", artifact_id=mapped["artifact_id"])
    assert validation["status"] == "valid"
    assert validation["dataset_applicability"]["state"] == "applicable"
    recovered = call(service, "get_growth_artifact", artifact_id=source["artifact_id"])
    assert base64.b64decode(recovered["content_base64"]) == raw
