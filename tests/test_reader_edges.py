"""Actual workbook, Arrow and XML edge cases exercise the complete input boundary."""

import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from test_file_formats import payload

from mmm_intelligence.config import Settings
from mmm_intelligence.errors import MMMError
from mmm_intelligence.supplied_files import parse_file
from mmm_intelligence.universal_schemas import SourceRequest


def parse(tmp_path, fmt, raw, **options):
    return parse_file(
        SourceRequest(**payload(fmt, raw, **options)), Settings(tmp_path, max_rows=52)
    )


def workbook(sheets=1, rows=1, columns=4):
    import xlwt

    book = xlwt.Workbook()
    for sheet_index in range(sheets):
        sheet = book.add_sheet("sheet" + str(sheet_index))
        for col in range(columns):
            sheet.write(0, col, "col" + str(col))
        for row in range(rows):
            sheet.write(
                row + 1,
                0,
                datetime(2026, 1, 1, 12, 30),
                xlwt.easyxf(num_format_str="YYYY-MM-DD HH:MM"),
            )
            if columns > 1:
                sheet.write(row + 1, 1, True)
            if columns > 2:
                sheet.write(row + 1, 2, None)
            if columns > 3:
                sheet.write(row + 1, 3, 10)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def test_xls_time_bool_and_blank_cells(tmp_path):
    _, rows, _, _, _ = parse(tmp_path, "xls", workbook())
    assert rows == [{"col0": "2026-01-01T12:30:00", "col1": True, "col2": None, "col3": 10}]


def test_xls_sheet_selection_corruption_and_dimension_limits(tmp_path):
    for raw, options, code in [
        (workbook(sheets=2), {}, "SHEET_REQUIRED"),
        (workbook(), {"sheet": "absent"}, "SHEET_INVALID"),
        (workbook(rows=53), {}, "ROW_LIMIT"),
        (workbook(columns=81), {}, "ROW_LIMIT"),
        (bytes.fromhex("d0cf11e0a1b11ae1") + b"invalid", {}, "FILE_INVALID"),
    ]:
        with pytest.raises(MMMError) as caught:
            parse(tmp_path, "xls", raw, **options)
        assert caught.value.code == code
    assert parse(tmp_path, "xls", workbook(sheets=2), sheet="sheet1")[3] == ["sheet0", "sheet1"]


def parquet(table):
    import pyarrow.parquet as pq

    output = io.BytesIO()
    pq.write_table(table, output, compression="snappy")
    return output.getvalue()


def test_parquet_dates_decimal_null_and_duplicate_names(tmp_path):
    import pyarrow as pa

    raw = parquet(
        pa.table(
            {
                "day": [date(2026, 1, 1)],
                "time": [datetime(2026, 1, 1, 12)],
                "money": [Decimal("10.25")],
                "missing": [None],
            }
        )
    )
    assert parse(tmp_path, "parquet", raw)[1] == [
        {"day": "2026-01-01", "time": "2026-01-01T12:00:00", "money": "10.25", "missing": None}
    ]
    duplicate = parquet(
        pa.Table.from_arrays([pa.array([1]), pa.array([2])], names=["value", "value"])
    )
    with pytest.raises(MMMError) as caught:
        parse(tmp_path, "parquet", duplicate)
    assert caught.value.code == "SCHEMA_INVALID"


@pytest.mark.parametrize("kind", ["empty", "rows", "columns", "binary"])
def test_parquet_empty_extreme_or_unsupported_schema(tmp_path, kind):
    import pyarrow as pa

    table = (
        pa.table({"x": []})
        if kind == "empty"
        else pa.table({"x": list(range(53))})
        if kind == "rows"
        else pa.table({"x" + str(i): [1] for i in range(81)})
        if kind == "columns"
        else pa.table({"x": [b"binary"]})
    )
    with pytest.raises(MMMError) as caught:
        parse(tmp_path, "parquet", parquet(table))
    assert caught.value.code == ("FILE_INVALID" if kind == "binary" else "ROW_LIMIT")


@pytest.mark.parametrize(
    "raw,options,code",
    [
        (b"<root><record>value</record></root>", {}, "XML_MAPPING"),
        (b"<root/>", {"xml_record": "record/item", "xml_fields": {"x": "."}}, "XML_MAPPING"),
        (b"<root/>", {"xml_record": "record", "xml_fields": {"x": "../secret"}}, "XML_MAPPING"),
        (
            b"<root><record><x>1</x><x>2</x></record></root>",
            {"xml_record": "record", "xml_fields": {"x": "x"}},
            "XML_AMBIGUOUS",
        ),
        (
            b"<root><record><x><y>1</y></x></record></root>",
            {"xml_record": "record", "xml_fields": {"x": "x"}},
            "XML_AMBIGUOUS",
        ),
        (
            b"<root><record><record>nested</record></record></root>",
            {"xml_record": "record", "xml_fields": {"x": "."}},
            "XML_AMBIGUOUS",
        ),
        (
            b"<root><record><x>1</x></record></root>",
            {"xml_record": "record", "xml_fields": {"x": "x"}, "xml_max_depth": 2},
            "FILE_LIMIT",
        ),
    ],
)
def test_xml_ambiguous_or_unbounded_queries_are_refused(tmp_path, raw, options, code):
    with pytest.raises(MMMError) as caught:
        parse(tmp_path, "xml", raw, **options)
    assert caught.value.code == code


def test_xml_row_limit_and_attribute_leaf_values(tmp_path):
    raw = b"<root>" + b"<record><x>1</x></record>" * 53 + b"</root>"
    with pytest.raises(MMMError) as caught:
        parse(tmp_path, "xml", raw, xml_record="record", xml_fields={"x": "x"})
    assert caught.value.code == "ROW_LIMIT"
    assert parse(
        tmp_path,
        "xml",
        b'<root><other/><record id="a"><x value="1"/></record></root>',
        xml_record="record",
        xml_fields={"id": "@id", "x": "x/@value"},
    )[1] == [{"id": "a", "x": "1"}]
