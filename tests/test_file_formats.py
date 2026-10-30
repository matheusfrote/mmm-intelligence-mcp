"""Real binary fixtures and hostile input tests for each supported reader."""

import base64
import io
from datetime import datetime

import pytest


def payload(fmt, raw, **kwargs):
    return dict(
        format=fmt,
        content_base64=base64.b64encode(raw).decode(),
        origin="synthetic fixture",
        synthetic=True,
        **kwargs,
    )


def test_xls_reads_actual_workbook_and_dates(service):
    import xlwt

    book = xlwt.Workbook()
    sheet = book.add_sheet("data")
    for j, v in enumerate(["date", "views"]):
        sheet.write(0, j, v)
    sheet.write(1, 0, datetime(2026, 1, 1), xlwt.easyxf(num_format_str="YYYY-MM-DD"))
    sheet.write(1, 1, 10)
    buffer = io.BytesIO()
    book.save(buffer)
    result = service.call("preview_dataset", payload("xls", buffer.getvalue(), sheet="data"))
    assert result.ok, result.error
    assert result.data["preview"] == [{"date": "2026-01-01", "views": 10}]
    assert not service.call("preview_dataset", payload("xls", b"not an xls")).ok


def test_parquet_preserves_scalars_nulls_and_rejects_nested(service):
    import pyarrow as pa
    import pyarrow.parquet as pq

    buffer = io.BytesIO()
    pq.write_table(
        pa.table({"date": ["2026-01-01"], "views": [10], "flag": [True], "unknown": [None]}),
        buffer,
        compression="gzip",
    )
    result = service.call("preview_dataset", payload("parquet", buffer.getvalue()))
    assert result.ok, result.error
    assert result.data["preview"][0] == {
        "date": "2026-01-01",
        "views": 10,
        "flag": True,
        "unknown": None,
    }
    nested = io.BytesIO()
    pq.write_table(pa.table({"nested": [[1, 2]]}), nested)
    assert not service.call("preview_dataset", payload("parquet", nested.getvalue())).ok


def test_xml_explicit_paths_attributes_missing_and_xxe(service):
    xml = b'<root><record id="a"><date>2026-01-01</date><metrics><views>10</views></metrics></record></root>'
    args = payload(
        "xml",
        xml,
        xml_record="record",
        xml_fields={"id": "@id", "date": "date", "views": "metrics/views", "unknown": "optional"},
    )
    result = service.call("preview_dataset", args)
    assert result.ok, result.error
    assert result.data["preview"] == [
        {"id": "a", "date": "2026-01-01", "views": "10", "unknown": None}
    ]
    attack = b'<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///C:/secret">]><root><record>&xxe;</record></root>'
    assert not service.call(
        "preview_dataset", payload("xml", attack, xml_record="record", xml_fields={"value": "."})
    ).ok


@pytest.mark.parametrize(
    "fmt,raw", [("xls", b"garbage"), ("parquet", b"PAR1badPAR1"), ("xml", b"<broken>")]
)
def test_malformed_files_have_actionable_format_error(service, fmt, raw):
    result = service.call(
        "preview_dataset",
        payload(
            fmt,
            raw,
            **({"xml_record": "record", "xml_fields": {"value": "."}} if fmt == "xml" else {}),
        ),
    )
    assert not result.ok
    assert result.error.code in {"FILE_INVALID", "FORMAT_MISMATCH"}


def test_parquet_dictionary_expansion_obeys_decoded_budget(tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from mmm_intelligence.config import Settings
    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.supplied_files import parse_file
    from mmm_intelligence.universal_schemas import SourceRequest

    buffer = io.BytesIO()
    pq.write_table(
        pa.table({"metric": ["x" * 9000] * 1024}),
        buffer,
        use_dictionary=True,
        write_statistics=False,
        compression="zstd",
    )
    allocated = []
    original = pq.ParquetFile.iter_batches

    def measured(self, **kwargs):
        for batch in original(self, **kwargs):
            allocated.append(batch.nbytes)
            yield batch

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", measured)
    with pytest.raises(MMMError, match="expanded|decoded"):
        parse_file(
            SourceRequest(**payload("parquet", buffer.getvalue())),
            Settings(tmp_path, max_file_bytes=4096),
        )
    assert max(allocated) <= 4 * 4096, (
        "Decoder must bound variable-width allocation before post-decode checks"
    )
