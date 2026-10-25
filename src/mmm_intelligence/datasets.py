"""Synthetic generation and explicit, non-imputing time-series validation."""

import re
from datetime import date, timedelta

import numpy as np

from .schemas import DatasetSpec, GenerateRequest

MEDIA = ["spend_search", "spend_social", "spend_video"]


def generate(request: GenerateRequest) -> dict:
    from .modeling import adstock, hill

    rng = np.random.default_rng(request.seed)
    n = request.periods
    step = 7 if request.frequency == "weekly" else 1
    t = np.arange(n)
    season = np.sin(2 * np.pi * t * step / 365.25)
    price = 1 + rng.normal(0, 0.04, n)
    promotion = rng.binomial(1, 0.2, n)
    spends = rng.uniform(300, 2800, (n, 3))
    spends[rng.random((n, 3)) < 0.06] = 0
    response = np.column_stack(
        [3000 * hill(adstock(spends[:, j], 0.5), k) for j, k in enumerate([1200, 1600, 1000])]
    )
    revenue = (
        7000
        + 500 * season
        + 4 * t
        + 600 * promotion
        - 2500 * (price - 1)
        + response.sum(axis=1)
        + rng.normal(0, 120, n)
    )
    rows = [
        {
            "date": (request.start_date + timedelta(days=i * step)).isoformat(),
            "revenue": float(revenue[i]),
            "price_index": float(price[i]),
            "promotion": int(promotion[i]),
            **{name: float(spends[i, j]) for j, name in enumerate(MEDIA)},
        }
        for i in range(n)
    ]
    return {
        "schema_version": 1,
        "synthetic": True,
        "source": "built-in-demo-v1",
        "target_type": "revenue",
        "data_context": {
            "source_reference": "built-in-demo-v1",
            "kpi_definition": "synthetic revenue; constructed DGP",
        },
        "frequency": request.frequency,
        "seed": request.seed,
        "units": {"spend": "synthetic_currency_per_period", "target": "synthetic_revenue"},
        "rows": rows,
    }


def validate(dataset: dict, request: DatasetSpec, max_rows: int) -> dict:
    issues, warnings = [], []
    rows = dataset.get("rows")
    if not isinstance(rows, list) or not 52 <= len(rows) <= max_rows:
        return {
            "valid": False,
            "issues": ["ROW_COUNT: need 52..configured maximum rows"],
            "warnings": [],
        }
    names = [
        request.date_column,
        request.target_column,
        *request.media_columns,
        *request.control_columns,
    ]
    if any(not isinstance(row, dict) or not set(names).issubset(row) for row in rows):
        return {
            "valid": False,
            "issues": ["MISSING_COLUMNS: required columns are absent"],
            "warnings": [],
        }
    dates = []
    for row in rows:
        try:
            value = row[request.date_column]
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError("Use ISO dates")
            dates.append(date.fromisoformat(value))
        except (ValueError, TypeError):
            issues.append("INVALID_DATE: use YYYY-MM-DD without time or timezone")
            break
    if len(dates) == len(rows):
        if len(set(dates)) != len(dates):
            issues.append("DUPLICATE_DATES: one row per period is required")
        if any(b <= a for a, b in zip(dates, dates[1:])):
            issues.append("UNSORTED_DATES: dates must increase strictly")
        frequency = dataset.get("frequency")
        step = {"daily": 1, "weekly": 7}.get(frequency) if isinstance(frequency, str) else None
        if step is None or any((b - a).days != step for a, b in zip(dates, dates[1:])):
            issues.append("IRREGULAR_SERIES: expected complete daily or weekly periods")
    numeric = names[1:]
    valid_numbers = True
    for row in rows:
        for name in numeric:
            value = row[name]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or abs(value) > 1e12
                or not np.isfinite(value)
            ):
                valid_numbers = False
                break
    if not valid_numbers:
        issues.append("INVALID_VALUES: missing, nonnumeric, infinite or excessive numeric values")
    else:
        values = np.array([[row[c] for c in numeric] for row in rows], dtype=float)
        if (values[:, : 1 + len(request.media_columns)] < 0).any():
            issues.append("NEGATIVE_VALUES: target and spending must be nonnegative")
        for j, name in enumerate(numeric):
            if np.ptp(values[:, j]) == 0:
                warnings.append(f"CONSTANT_COLUMN: {name}")
    n_test = int(np.ceil(len(rows) * request.test_fraction))
    train_size = len(rows) - n_test - request.warmup_periods
    features = len(request.media_columns) + len(request.control_columns) + 4
    if train_size < max(26, features + 5) or n_test < 5:
        issues.append("INSUFFICIENT_SPLIT: need >=26 training rows after warmup and >=5 test rows")
    if len(rows) < (104 if dataset.get("frequency") == "weekly" else 730):
        warnings.append(
            "SHORT_HISTORY: limited annual coverage; no universal sufficiency guarantee"
        )
    context = dataset.get("data_context", {})
    missing_metadata = [
        c
        for c in (
            "source_reference",
            "extracted_at",
            "timezone",
            "currency",
            "kpi_definition",
            "complete_through",
        )
        if not context.get(c)
    ]
    if dataset.get("synthetic") is not True and missing_metadata:
        warnings.append("METADATA_MISSING: " + ", ".join(missing_metadata))
    if valid_numbers:
        for j, name in enumerate(numeric):
            q1, q3 = np.quantile(values[:, j], [0.25, 0.75])
            iqr = q3 - q1
            count = (
                int(np.sum((values[:, j] < q1 - 3 * iqr) | (values[:, j] > q3 + 3 * iqr)))
                if iqr > 0
                else 0
            )
            if count:
                warnings.append(
                    f"OUTLIER_SCREEN: {name} has {count} values outside 3-IQR fences; not removed"
                )
    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "rows": len(rows),
        "start_date": dates[0].isoformat() if dates else None,
        "end_date": dates[-1].isoformat() if len(dates) == len(rows) else None,
        "train_rows": train_size,
        "test_rows": n_test,
        "warmup_rows": request.warmup_periods,
        "frequency": dataset.get("frequency"),
        "synthetic": dataset.get("synthetic") is True,
        "missing_metadata": missing_metadata,
        "data_context": context,
        "target_type": dataset.get("target_type", "unspecified"),
    }
