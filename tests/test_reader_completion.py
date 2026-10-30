"""Real file errors and declared library/metadata failure boundaries."""

import base64
import io

import pytest
from test_file_formats import payload
from test_reader_edges import parquet, parse

from mmm_intelligence.config import Settings
from mmm_intelligence.errors import MMMError
from mmm_intelligence.file_readers import read_parquet
from mmm_intelligence.supplied_files import parse_file
from mmm_intelligence.universal_schemas import SourceRequest


def test_xls_real_error_cell_is_rejected(tmp_path):
    import xlwt

    book = xlwt.Workbook()
    sheet = book.add_sheet("data")
    sheet.write(0, 0, "value")
    sheet.row(1).set_cell_error(0, "#DIV/0!")
    output = io.BytesIO()
    book.save(output)
    with pytest.raises(MMMError) as caught:
        parse(tmp_path, "xls", output.getvalue())
    assert caught.value.code == "CELL_INVALID"


def test_parquet_signature_and_external_chunk_metadata(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    with pytest.raises(MMMError) as caught:
        read_parquet(b"wrong signature", Settings(tmp_path))
    assert caught.value.code == "FORMAT_MISMATCH"
    schema = pa.schema([("x", pa.int64())])
    metadata = []
    output = io.BytesIO()
    pq.write_table(pa.table({"x": [1]}), output, metadata_collector=metadata)
    metadata[0].set_file_path("external.parquet")
    manifest = io.BytesIO()
    pq.write_metadata(schema, manifest, metadata_collector=metadata)
    with pytest.raises(MMMError) as caught:
        read_parquet(manifest.getvalue(), Settings(tmp_path))
    assert caught.value.code == "FILE_INVALID" and "External" in str(caught.value)


def test_parquet_expanded_metadata_budget(tmp_path):
    import pyarrow as pa

    raw = parquet(pa.table({"text": ["x" * 10000]}))
    with pytest.raises(MMMError) as caught:
        read_parquet(raw, Settings(tmp_path, max_file_bytes=1024))
    assert caught.value.code == "FILE_LIMIT"


def test_parquet_refuses_library_rows_beyond_declared_metadata(tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq

    # Fault injection at the decoder boundary: footer validation cannot authorize
    # a decoder returning more rows than the configured cap.
    original = pq.ParquetFile
    raw = parquet(pa.table({"x": [1]}))

    class InconsistentDecoder:
        def __init__(self, *args, **kwargs):
            self.real = original(*args, **kwargs)
            self.metadata = self.real.metadata
            self.schema_arrow = self.real.schema_arrow

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.real.close()

        def iter_batches(self, **kwargs):
            yield pa.record_batch({"x": list(range(53))})

    monkeypatch.setattr(pq, "ParquetFile", InconsistentDecoder)
    with pytest.raises(MMMError) as caught:
        read_parquet(raw, Settings(tmp_path, max_rows=52))
    assert caught.value.code == "ROW_LIMIT"


@pytest.mark.parametrize(
    "kind", ["encoded", "csv_rows", "xlsx_dimensions", "xlsx_actual", "schema_empty"]
)
def test_format_resource_limits(tmp_path, kind):
    if kind == "encoded":
        request = SourceRequest(**payload("csv", b"x" * 2000))
        settings = Settings(tmp_path, max_file_bytes=1024)
    elif kind == "csv_rows":
        request = SourceRequest(**payload("csv", b"x\n" + b"1\n" * 55))
        settings = Settings(tmp_path, max_rows=52)
    elif kind == "schema_empty":
        request = SourceRequest(
            **payload(
                "xml",
                b"<root/>",
                xml_record="record",
                xml_fields={"x": "x"},
                xml_schema_base64=base64.b64encode(b"").decode(),
            )
        )
        settings = Settings(tmp_path)
    else:
        import zipfile

        import openpyxl

        book = openpyxl.Workbook()
        book.active.append(["x"])
        for _ in range(53):
            book.active.append([1])
        output = io.BytesIO()
        book.save(output)
        raw = output.getvalue()
        if kind == "xlsx_actual":
            # A genuine ZIP workbook with lying worksheet dimensions.
            import re

            patched = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(patched, "w") as new:
                for entry in old.infolist():
                    content = old.read(entry.filename)
                    if entry.filename == "xl/worksheets/sheet1.xml":
                        content = re.sub(
                            rb'<dimension ref="[^"]+"', b'<dimension ref="A1:A1"', content
                        )
                    new.writestr(entry, content)
            raw = patched.getvalue()
        request = SourceRequest(**payload("xlsx", raw))
        settings = Settings(tmp_path, max_rows=52)
    with pytest.raises(MMMError) as caught:
        parse_file(request, settings)
    assert caught.value.code in {"FILE_LIMIT", "ROW_LIMIT", "XML_SCHEMA"}
