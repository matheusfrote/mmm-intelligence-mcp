"""Limits apply equally to textual and spreadsheet inputs before persistence."""

import io
import json
import zipfile

import pytest
from test_file_formats import payload

from mmm_intelligence.config import Settings
from mmm_intelligence.errors import MMMError
from mmm_intelligence.supplied_files import parse_file
from mmm_intelligence.universal_schemas import SourceRequest


def check(tmp_path, fmt, raw, **options):
    return parse_file(
        SourceRequest(**payload(fmt, raw, **options)), Settings(tmp_path, max_rows=52)
    )


@pytest.mark.parametrize(
    "fmt,raw,options,code",
    [
        ("csv", b"a,b\n1", {}, "ROW_INVALID"),
        ("csv", b"a,a\n1,2", {}, "HEADER_INVALID"),
        ("csv", b"a,b", {"header_row": 2}, "HEADER_INVALID"),
        ("json", b"{}", {}, "ROW_LIMIT"),
        ("json", b"[]", {}, "ROW_LIMIT"),
        ("json", b"[1]", {}, "SCHEMA_INVALID"),
        ("json", b'[{"a":1},{"b":2}]', {}, "SCHEMA_DRIFT"),
        ("json", b'[{"a":[1]}]', {}, "SCHEMA_INVALID"),
        ("json", b'[{"a":Infinity}]', {}, "SCHEMA_INVALID"),
        ("json", b'[{"":1}]', {}, "SCHEMA_INVALID"),
        ("json", json.dumps([{str(i): i for i in range(81)}]).encode(), {}, "SCHEMA_INVALID"),
        ("json", json.dumps([{"x": "a" * 10001}]).encode(), {}, "CELL_LIMIT"),
        ("jsonl", b"\n\n", {}, "ROW_LIMIT"),
    ],
)
def test_common_file_boundary_rejects_invalid_data(tmp_path, fmt, raw, options, code):
    with pytest.raises(MMMError) as caught:
        check(tmp_path, fmt, raw, **options)
    assert caught.value.code == code


def test_empty_or_overlong_encoded_input_cannot_allocate_unbounded_data(tmp_path):
    for raw in [b"", b"x" * 1025]:
        with pytest.raises(MMMError) as caught:
            parse_file(
                SourceRequest(**payload("csv", raw)), Settings(tmp_path, max_file_bytes=1024)
            )
        assert caught.value.code == "FILE_LIMIT"
    assert check(tmp_path, "tsv", b"a\tb\n1\t2\n")[1] == [{"a": "1", "b": "2"}]
    assert check(tmp_path, "jsonl", b'\n{"a":1}\n\n')[1] == [{"a": 1}]


def xlsx():
    from openpyxl import Workbook

    book = Workbook()
    book.active.title = "data"
    book.active.append(["date", "count"])
    book.active.append(["2026-01-01", 10])
    stream = io.BytesIO()
    book.save(stream)
    return stream.getvalue()


def test_xlsx_refuses_missing_xml_protection_or_dependency(tmp_path, monkeypatch):
    import openpyxl

    monkeypatch.setattr(openpyxl, "DEFUSEDXML", False)
    with pytest.raises(MMMError) as caught:
        check(tmp_path, "xlsx", xlsx())
    assert caught.value.code == "FORMAT_UNAVAILABLE"
    monkeypatch.undo()
    import sys

    raw = xlsx()
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    with pytest.raises(MMMError) as caught:
        check(tmp_path, "xlsx", raw)
    assert caught.value.code == "FORMAT_UNAVAILABLE"


def test_xls_optional_dependency_has_explicit_installation_error(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "xlrd", None)
    with pytest.raises(MMMError) as caught:
        check(tmp_path, "xls", bytes.fromhex("d0cf11e0a1b11ae1"))
    assert caught.value.code == "FORMAT_UNAVAILABLE"


def test_zip_expansion_and_entry_count_are_bounded(tmp_path):
    for many in [True, False]:
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for i in range(1001 if many else 1):
                archive.writestr(str(i), b"x" if many else b"x" * 20001)
        with pytest.raises(MMMError) as caught:
            parse_file(
                SourceRequest(**payload("xlsx", raw.getvalue())),
                Settings(tmp_path, max_file_bytes=10485760 if many else 4096),
            )
        assert caught.value.code == "FILE_LIMIT"


def test_xlsx_unknown_sheet_is_not_silently_ignored(tmp_path):
    with pytest.raises(MMMError) as caught:
        check(tmp_path, "xlsx", xlsx(), sheet="absent")
    assert caught.value.code == "SHEET_INVALID"
