"""Extension contracts and reconciliation, not authenticated provider adapters."""

import math
from datetime import date
from typing import Literal, Protocol

from pydantic import Field

from .schemas import Contract
from .storage import digest

SOURCES = (
    "google_ads",
    "meta_ads",
    "ga4",
    "tiktok_ads",
    "microsoft_ads",
    "sales",
    "crm",
    "ecommerce",
    "sql",
    "warehouse",
)


class SourceBatch(Contract):
    source: Literal[
        "google_ads",
        "meta_ads",
        "ga4",
        "tiktok_ads",
        "microsoft_ads",
        "sales",
        "crm",
        "ecommerce",
        "sql",
        "warehouse",
    ]
    source_version: str = Field(min_length=1, max_length=64)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str = Field(min_length=1, max_length=64)
    grain: list[str] = Field(min_length=1, max_length=10)
    watermark: date
    records: list[dict] = Field(min_length=1, max_length=10000)
    reported_totals: dict[str, float] = Field(min_length=1, max_length=20)
    authorization_reference: str = Field(min_length=3, max_length=200)
    synthetic: bool


class MarketingSource(Protocol):
    """Implementations keep OAuth and credentials in the host, outside batch payloads."""

    def fetch_page(
        self, *, start: date, end: date, cursor: str | None
    ) -> tuple[SourceBatch, str | None]: ...


def connector_status():
    return {
        name: {
            "state": "contract_only_not_implemented",
            "live_verified": False,
            "required": "Provider adapter, host credential store, read-only scope, bounded pagination/retry, and authorized real reconciliation",
        }
        for name in SOURCES
    }


def reconcile_batches(batches: list[SourceBatch], tolerance=1e-6):
    if not batches or len(batches) > 100 or not 0 <= tolerance <= 0.01:
        raise ValueError("Supply 1..100 batches and an explicit tolerance up to .01")
    first = batches[0]
    # Reject mixed scopes before processing rows, so no partial sync receipt is issued.
    for b in batches:
        if (b.currency, b.timezone, b.grain, b.synthetic) != (
            first.currency,
            first.timezone,
            first.grain,
            first.synthetic,
        ):
            raise ValueError("Mixed currency, timezone, grain or data origin")
        if set(b.reported_totals) != set(first.reported_totals):
            raise ValueError("Reported metrics differ")
    seen: set[tuple] = set()
    totals: dict[str, list[float]] = {key: [] for key in first.reported_totals}
    for b in batches:
        if len(set(b.grain)) != len(b.grain):
            raise ValueError("Duplicate grain columns")
        batch_totals: dict[str, list[float]] = {key: [] for key in b.reported_totals}
        for row in b.records:
            if len(seen) >= 10000:
                raise ValueError("Reconciliation row limit exceeded")
            if any(
                key not in row or not isinstance(row[key], (str, int)) or isinstance(row[key], bool)
                for key in b.grain
            ):
                raise ValueError("Missing or invalid grain key")
            key = (b.source, *(row[c] for c in b.grain))
            if key in seen:
                raise ValueError(
                    "Duplicate source grain; do not silently discard or sum overlapping pages"
                )
            seen.add(key)
            for metric in b.reported_totals:
                value = row.get(metric)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or abs(value) > 1e12
                ):
                    raise ValueError("Invalid source numeric metric")
                batch_totals[metric].append(value)
        for metric, values in batch_totals.items():
            total = math.fsum(values)
            if not math.isclose(total, b.reported_totals[metric], rel_tol=0, abs_tol=tolerance):
                raise ValueError("Provider totals do not reconcile")
            totals[metric].append(total)
    receipt = {
        "record_count": len(seen),
        "currency": first.currency,
        "timezone": first.timezone,
        "totals": {k: math.fsum(v) for k, v in totals.items()},
        "batches": [digest(b.model_dump(mode="json")) for b in batches],
        "source_authenticated": False,
        "synthetic": first.synthetic,
        "scope": "Offline reconciliation of declared batches; not an API/account verification",
    }
    return {**receipt, "receipt_sha256": digest(receipt)}
