"""Bounded inline CSV ingestion; no paths, network fetches or silent cleaning."""

import csv
import hashlib
import io
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import MMMError
from .schemas import CSVImportRequest


def reporting_timezone(name):
    if name == "UTC":
        return timezone.utc
    if re.fullmatch(r"[+-](?:0\d|1[0-3]):[0-5]\d", name or ""):
        minutes = int(name[1:3]) * 60 + int(name[4:])
        return timezone(timedelta(minutes=minutes * (1 if name[0] == "+" else -1)))
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise MMMError(
            "TIMEZONE_UNAVAILABLE", "Timezone unavailable; install tzdata or use UTC/fixed offset"
        ) from exc


def parse_csv(request: CSVImportRequest, *, max_rows: int, max_bytes: int) -> dict:
    raw = request.csv_text.encode("utf-8")
    if len(raw) > max_bytes:
        raise MMMError("ARTIFACT_TOO_LARGE", "CSV exceeds the host byte limit")
    columns = [
        request.date_column,
        request.target_column,
        *request.media_columns,
        *request.control_columns,
    ]
    reader = csv.reader(
        io.StringIO(request.csv_text, newline=""), delimiter=request.delimiter, strict=True
    )
    try:
        header = next(reader)
        if (
            len(header) != len(set(header))
            or not header
            or any(not c or len(c) > 128 for c in header)
        ):
            raise MMMError("CSV_HEADER", "Header names must be unique and nonempty")
        if set(request.column_mapping) - set(header):
            raise MMMError("CSV_HEADER", "Mapping references an absent source column")
        mapped = [request.column_mapping.get(c, c) for c in header]
        if len(mapped) != len(set(mapped)) or set(mapped) != set(columns):
            raise MMMError(
                "CSV_HEADER",
                "Map exactly the declared date, KPI, media and controls; no discarded columns",
            )
        rows: list[dict] = []
        tz = reporting_timezone(request.timezone) if request.date_format == "iso_datetime" else None
        for line, cells in enumerate(reader, 2):
            if len(rows) >= max_rows:
                raise MMMError("ROW_LIMIT", "CSV exceeds the configured source row limit")
            if len(cells) != len(header):
                raise MMMError("CSV_ROW", f"Wrong field count at row {line}")
            source = dict(zip(mapped, cells))
            try:
                text = source[request.date_column]
                if request.date_format == "iso_datetime":
                    if "T" not in text:
                        raise ValueError("Timestamp required")
                    instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
                    if instant.tzinfo is None:
                        raise ValueError("Offset required; ambiguous local timestamps refused")
                    day = instant.astimezone(tz).date()
                else:
                    day = datetime.strptime(text, request.date_format).date()
                    if day.strftime(request.date_format) != text:
                        raise ValueError("Exact declared date format required")
                row: dict = {request.date_column: day.isoformat()}
                for c in columns[1:]:
                    text = source[c]
                    if request.decimal_separator == ",":
                        if "." in text:
                            raise ValueError("Thousands separators not supported")
                        text = text.replace(",", ".")
                    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
                        raise ValueError("Invalid numeric field")
                    value = float(text)
                    if not math.isfinite(value) or abs(value) > 1e12:
                        raise ValueError("Invalid range")
                    if c in [request.target_column, *request.media_columns] and value < 0:
                        raise ValueError("Negative spend or outcome")
                    row[c] = value
                rows.append(row)
            except (ValueError, OverflowError) as exc:
                raise MMMError(
                    "CSV_VALUE", f"Invalid date or numeric value at row {line}; no values changed"
                ) from exc
    except (csv.Error, StopIteration) as exc:
        raise MMMError("CSV_PARSE", "Malformed or empty CSV") from exc
    transformations: list[dict] = [
        {
            "operation": "parse",
            "column_mapping": request.column_mapping,
            "date_format": request.date_format,
            "timezone": request.timezone,
            "decimal_separator": request.decimal_separator,
            "source_rows": len(rows),
        }
    ]
    if request.sort_dates:
        rows.sort(key=lambda r: r[request.date_column])
        transformations.append({"operation": "sort_dates"})
    if request.duplicate_policy == "aggregate":
        rows = aggregate(rows, request, weekly=False)
        transformations.append({"operation": "aggregate_duplicates", "reducers": request.reducers})
    days = [datetime.fromisoformat(r[request.date_column]).date() for r in rows]
    if len(set(days)) != len(days):
        raise MMMError("DUPLICATE_DATES", "Duplicate reporting dates require explicit aggregation")
    if any(b <= a for a, b in zip(days, days[1:])):
        raise MMMError(
            "UNSORTED_DATES", "Dates must increase; explicitly enable sorting if intended"
        )
    if request.aggregate_weekly:
        if any((b - a).days != 1 for a, b in zip(days, days[1:])):
            raise MMMError(
                "INCOMPLETE_PERIOD", "Daily source has missing days; no partial aggregation"
            )
        rows = aggregate(rows, request, weekly=True)
        transformations.append(
            {"operation": "aggregate_weekly_monday", "reducers": request.reducers}
        )
    return {
        "rows": rows,
        "provenance": {
            "format": "csv",
            "encoding": "utf-8",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "original_csv": request.csv_text,
            "transformations": transformations,
            "output_rows": len(rows),
        },
    }


def aggregate(rows, request, *, weekly):
    groups = defaultdict(list)
    for row in rows:
        day = datetime.fromisoformat(row[request.date_column]).date()
        key = day - timedelta(days=day.weekday()) if weekly else day
        groups[key.isoformat()].append(row)
    output = []
    for day, group in groups.items():
        if weekly and len(group) != 7:
            raise MMMError(
                "INCOMPLETE_PERIOD", "Weekly aggregation requires seven complete days per week"
            )
        row = {request.date_column: day}
        for c, reducer in request.reducers.items():
            values = [r[c] for r in group]
            row[c] = (
                math.fsum(values)
                if reducer == "sum"
                else math.fsum(values) / len(values)
                if reducer == "mean"
                else values[-1]
            )
        output.append(row)
    return output
