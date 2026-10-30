"""The operational file contract preserves times and bounds absolute XML paths."""

import io
from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from openpyxl import Workbook
from test_file_formats import payload


def test_xlsx_preserves_time_until_explicit_date_mapping(service):
    book = Workbook()
    book.active.append(["day", "at"])
    book.active.append([datetime(2026, 1, 5), datetime(2026, 1, 5, 12, 30)])
    stream = io.BytesIO()
    book.save(stream)
    result = service.call("preview_dataset", payload("xlsx", stream.getvalue()))
    assert result.ok, result.error
    assert result.data["preview"] == [{"day": "2026-01-05", "at": "2026-01-05T12:30:00"}]


def test_absolute_and_relative_xml_paths_refer_only_to_the_selected_record(service):
    raw = b'<root><record id="a"><nested><amount>2</amount></nested></record></root>'
    common = {"xml_record": "record"}
    relative = service.call(
        "preview_dataset",
        payload("xml", raw, xml_fields={"id": "@id", "value": "nested/amount"}, **common),
    )
    absolute = service.call(
        "preview_dataset",
        payload(
            "xml",
            raw,
            xml_fields={"id": "/root/record/@id", "value": "/root/record/nested/amount"},
            **common,
        ),
    )
    assert relative.ok and absolute.ok, (relative.error, absolute.error)
    assert relative.data["preview"] == absolute.data["preview"] == [{"id": "a", "value": "2"}]


@pytest.mark.parametrize(
    "path",
    ["/root/metadata/value", "/wrong/record/value", "/root/record/../secret", "//record/value"],
)
def test_xml_cannot_escape_the_declared_record(service, path):
    answer = service.call(
        "preview_dataset",
        payload(
            "xml",
            b"<root><record><value>2</value></record></root>",
            xml_record="record",
            xml_fields={"x": path},
        ),
    )
    assert not answer.ok and answer.error.code == "XML_MAPPING"


def test_nested_parquet_has_the_requested_file_error_contract(service):
    output = io.BytesIO()
    pq.write_table(pa.table({"nested": [[1, 2]]}), output)
    result = service.call("preview_dataset", payload("parquet", output.getvalue()))
    assert not result.ok and result.error.code == "FILE_INVALID"
