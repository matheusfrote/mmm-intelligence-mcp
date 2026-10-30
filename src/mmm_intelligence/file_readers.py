"""Bounded additional readers. Input bytes only, no filesystem or network access."""

import base64
import io
import re
import struct
from datetime import date, datetime
from decimal import Decimal

from .errors import MMMError


def reject_external_xml(url, public_id, context):
    """Resolver policy stays fail-closed even if upstream schema rules change."""
    raise ValueError("External schema resources are forbidden")


def read_additional(raw, request, settings):
    try:
        if request.format == "xls":
            return read_xls(raw, request, settings)
        if request.format == "parquet":
            return read_parquet(raw, settings), []
        return read_xml(raw, request, settings), []
    except ImportError as exc:
        raise MMMError(
            "FORMAT_UNAVAILABLE", "Install the optional files dependencies for " + request.format
        ) from exc


def read_xls(raw, request, settings):
    if not raw.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise MMMError("FORMAT_MISMATCH", "Expected an OLE BIFF Excel workbook")
    import xlrd

    from .supplied_files import tabular

    try:
        book = xlrd.open_workbook(file_contents=raw, on_demand=True, logfile=io.StringIO())
        try:
            sheets = book.sheet_names()
            if request.sheet is None and len(sheets) != 1:
                raise MMMError("SHEET_REQUIRED", "Select a worksheet: " + ", ".join(sheets))
            if request.sheet is not None and request.sheet not in sheets:
                raise MMMError("SHEET_INVALID", "Unknown worksheet")
            sheet = book.sheet_by_name(request.sheet or sheets[0])
            if sheet.nrows > settings.max_rows + request.header_row or sheet.ncols > 80:
                raise MMMError("ROW_LIMIT", "Workbook dimensions exceed host limits")
            table = []
            for index in range(sheet.nrows):
                row = []
                for cell in sheet.row(index):
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        instant = xlrd.xldate_as_datetime(cell.value, book.datemode)
                        row.append(
                            instant.date().isoformat()
                            if instant.time() == datetime.min.time()
                            else instant.isoformat()
                        )
                    elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                        row.append(bool(cell.value))
                    elif cell.ctype in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK}:
                        row.append(None)
                    elif cell.ctype == xlrd.XL_CELL_ERROR:
                        raise MMMError("CELL_INVALID", "Excel contains an error cell")
                    else:
                        row.append(cell.value)
                table.append(row)
            return tabular(table, request.header_row), sheets
        finally:
            book.release_resources()
    except (
        xlrd.XLRDError,
        xlrd.compdoc.CompDocError,
        struct.error,
        IndexError,
        ValueError,
        TypeError,
    ) as exc:
        raise MMMError("FILE_INVALID", "Malformed, encrypted or unsupported XLS workbook") from exc


def scalar(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def read_parquet(raw, settings):
    if not raw.startswith(b"PAR1") or not raw.endswith(b"PAR1"):
        raise MMMError("FORMAT_MISMATCH", "Expected unencrypted single-file Parquet")
    import pyarrow as pa
    import pyarrow.parquet as pq

    try:
        with pq.ParquetFile(
            io.BytesIO(raw),
            thrift_string_size_limit=settings.max_file_bytes,
            thrift_container_size_limit=100000,
            arrow_extensions_enabled=False,
        ) as file:
            meta = file.metadata
            if len(set(file.schema_arrow.names)) != len(file.schema_arrow.names):
                raise MMMError("SCHEMA_INVALID", "Duplicate Parquet column names are ambiguous")
            if not 0 < meta.num_rows <= settings.max_rows or not 0 < len(file.schema_arrow) <= 80:
                raise MMMError(
                    "ROW_LIMIT", "Parquet dimensions exceed host limits or contain no records"
                )
            total = 0
            for group in range(meta.num_row_groups):
                row_group = meta.row_group(group)
                for col in range(row_group.num_columns):
                    chunk = row_group.column(col)
                    if chunk.file_path:
                        raise MMMError("FILE_INVALID", "External Parquet chunks are forbidden")
                    total += chunk.total_uncompressed_size
            if total > 4 * settings.max_file_bytes:
                raise MMMError("FILE_LIMIT", "Parquet expanded data exceeds host limits")
            allowed = [
                pa.types.is_integer,
                pa.types.is_floating,
                pa.types.is_boolean,
                pa.types.is_string,
                pa.types.is_large_string,
                pa.types.is_date,
                pa.types.is_timestamp,
                pa.types.is_decimal,
                pa.types.is_null,
            ]
            if any(not any(check(field.type) for check in allowed) for field in file.schema_arrow):
                raise MMMError(
                    "FILE_INVALID",
                    "Parquet requires scalar numeric, string, boolean or temporal columns",
                )
            rows = []
            decoded = 0
            variable_width = any(
                pa.types.is_string(field.type) or pa.types.is_large_string(field.type)
                for field in file.schema_arrow
            )
            for batch in file.iter_batches(
                # Dictionary expansion happens inside Arrow, before batch.nbytes can be checked.
                # A single variable-width value bounds allocation independently of row repetition.
                batch_size=1
                if variable_width
                else min(settings.max_rows, 128, max(1, settings.max_file_bytes // 1024)),
                use_threads=False,
            ):
                decoded += batch.nbytes + 32 * batch.num_rows * len(file.schema_arrow)
                if decoded > 4 * settings.max_file_bytes:
                    raise MMMError(
                        "FILE_LIMIT", "Parquet decoded/expanded values exceed host limits"
                    )
                if len(rows) + batch.num_rows > settings.max_rows:
                    raise MMMError("ROW_LIMIT", "Actual Parquet rows exceed limit")
                rows.extend({k: scalar(v) for k, v in row.items()} for row in batch.to_pylist())
            return rows
    except (pa.ArrowException, ValueError, OSError) as exc:
        raise MMMError("FILE_INVALID", "Malformed or unsupported Parquet file") from exc


def xml_path(value):
    if value == ".":
        return
    pieces = value.removeprefix("/").split("/")
    if any(not re.fullmatch(r"@?[A-Za-z_][A-Za-z0-9_.:-]*", part) for part in pieces) or any(
        p.startswith("@") for p in pieces[:-1]
    ):
        raise MMMError(
            "XML_MAPPING",
            "Use simple child paths and terminal attributes; XPath expressions are forbidden",
        )


def read_xml(raw, request, settings):
    from defusedxml.common import DefusedXmlException
    from defusedxml.ElementTree import ParseError, iterparse

    if not request.xml_record or not request.xml_fields:
        raise MMMError("XML_MAPPING", "Declare record element and output-column selectors")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]*", request.xml_record):
        raise MMMError("XML_MAPPING", "Record selector must be one explicit element name")
    for path in request.xml_fields.values():
        xml_path(path)
    rows = []
    depth = 0
    ancestry = []
    active = False
    try:
        for event, element in iterparse(
            io.BytesIO(raw),
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if event == "start":
                depth += 1
                ancestry.append(element.tag)
                if depth > request.xml_max_depth:
                    raise MMMError("FILE_LIMIT", "XML nesting exceeds configured depth")
                if element.tag == request.xml_record:
                    if active:
                        raise MMMError("XML_AMBIGUOUS", "Nested record elements are ambiguous")
                    active = True
            else:
                if element.tag == request.xml_record:
                    if len(rows) >= settings.max_rows:
                        raise MMMError("ROW_LIMIT", "XML records exceed host limit")
                    row = {}
                    for column, path in request.xml_fields.items():
                        if path.startswith("/"):
                            absolute = path[1:].split("/")
                            if absolute[:depth] != ancestry:
                                raise MMMError(
                                    "XML_MAPPING",
                                    "Absolute selectors must stay within the selected record ancestry",
                                )
                            path = "/".join(absolute[depth:]) or "."
                        pieces = path.split("/")
                        attribute = pieces[-1][1:] if pieces[-1].startswith("@") else None
                        selector = "/".join(pieces[:-1]) if attribute else path
                        nodes = [element] if selector in {"", "."} else element.findall(selector)
                        if len(nodes) > 1:
                            raise MMMError("XML_AMBIGUOUS", "Selector resolves to multiple values")
                        if nodes and not attribute and len(nodes[0]):
                            raise MMMError(
                                "XML_AMBIGUOUS", "Select a leaf element, not a hierarchy"
                            )
                        row[column] = (
                            nodes[0].get(attribute)
                            if nodes and attribute
                            else nodes[0].text
                            if nodes
                            else None
                        )
                    rows.append(row)
                    active = False
                    element.clear()
                elif not active:
                    element.clear()
                depth -= 1
                ancestry.pop()
    except (ParseError, DefusedXmlException) as exc:
        raise MMMError(
            "FILE_INVALID", "Unsafe or malformed XML; DTD and entities are forbidden"
        ) from exc
    if request.xml_schema_base64 is not None:
        validate_xml_schema(raw, request.xml_schema_base64)
    return rows


def validate_xml_schema(raw, encoded):
    """Local XSD 1.0 structural/type subset; no imports, regexes or executable paths."""
    from defusedxml.common import DefusedXmlException
    from defusedxml.ElementTree import ParseError, iterparse
    from lxml import etree

    allowed = {
        "schema",
        "element",
        "complexType",
        "simpleType",
        "sequence",
        "all",
        "choice",
        "attribute",
        "restriction",
        "enumeration",
        "minInclusive",
        "maxInclusive",
        "minExclusive",
        "maxExclusive",
        "length",
        "minLength",
        "maxLength",
        "totalDigits",
        "fractionDigits",
        "annotation",
        "documentation",
    }
    try:
        schema_bytes = base64.b64decode(encoded, validate=True)
        if not 0 < len(schema_bytes) <= 65536:
            raise ValueError("schema size")
        depth = count = 0
        for event, node in iterparse(
            io.BytesIO(schema_bytes),
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if event == "start":
                count += 1
                depth += 1
                local = node.tag.removeprefix("{http://www.w3.org/2001/XMLSchema}")
                if (
                    depth > 24
                    or count > 1000
                    or local not in allowed
                    or any(
                        k in node.attrib
                        for k in ("schemaLocation", "xpath", "ref", "substitutionGroup")
                    )
                ):
                    raise ValueError("unsupported or excessive schema")
            else:
                depth -= 1

        class DenyResources(etree.Resolver):
            resolve = staticmethod(reject_external_xml)

        parser = etree.XMLParser(
            resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False, recover=False
        )
        parser.resolvers.add(DenyResources())
        schema = etree.XMLSchema(etree.fromstring(schema_bytes, parser))
        schema.assertValid(etree.fromstring(raw, parser))
    except (ValueError, ParseError, DefusedXmlException, etree.LxmlError) as exc:
        raise MMMError(
            "XML_SCHEMA",
            "XML does not satisfy the supplied bounded local XSD, or schema uses unsupported features",
        ) from exc
