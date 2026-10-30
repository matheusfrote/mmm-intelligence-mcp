"""Versioned media semantics and descriptive quality; no crossmedia reach sums."""

import math
from datetime import date

import numpy as np

NONADDITIVE = [
    "reach",
    "users",
    "rating",
    "share",
    "frequency",
    "ctr",
    "cpc",
    "cpa",
    "circulation",
    "readers",
    "audience",
]
OPTIONAL = [
    "spend",
    "impressions",
    "clicks",
    "conversions",
    "revenue",
    "leads",
    "sales",
    "views",
    "reach",
    "users",
    "sessions",
    "pageviews",
    "engagements",
    "watch_time",
    "subscribers",
    "retention",
    "insertions",
    "rating",
    "share",
    "grp",
    "trp",
    "frequency",
    "audience",
    "circulation",
    "print_run",
    "readers",
    "ctr",
    "cpc",
    "cpa",
]
PROFILES: dict[str, dict] = {}
for family, names in {
    "traditional": ["tv", "radio", "print"],
    "web": ["website", "seo", "search_ads"],
    "video": [
        "youtube_organic",
        "youtube_paid",
        "tiktok_organic",
        "tiktok_paid",
        "kwai_organic",
        "kwai_paid",
    ],
    "social": [
        "facebook_organic",
        "facebook_boosted",
        "facebook_ads",
        "instagram_organic",
        "instagram_boosted",
        "instagram_ads",
    ],
}.items():
    for name in names:
        PROFILES[name] = {
            "name": name,
            "version": "1",
            "family": family,
            "required": ["date"],
            "optional": OPTIONAL,
            "nonadditive": NONADDITIVE,
        }


for name, profile in PROFILES.items():
    if name in {"tv", "radio"}:
        fields = {
            "spend",
            "insertions",
            "audience",
            "rating",
            "share",
            "grp",
            "trp",
            "reach",
            "frequency",
        }
    elif name == "print":
        fields = {"spend", "insertions", "circulation", "print_run", "readers", "reach"}
    elif name == "website":
        fields = {
            "spend",
            "users",
            "sessions",
            "pageviews",
            "impressions",
            "clicks",
            "leads",
            "conversions",
            "revenue",
            "sales",
            "ctr",
        }
    elif name == "seo":
        fields = {
            "impressions",
            "clicks",
            "ctr",
            "sessions",
            "conversions",
            "revenue",
            "sales",
            "position",
        }
    elif name == "search_ads":
        fields = {
            "spend",
            "impressions",
            "clicks",
            "ctr",
            "cpc",
            "cpa",
            "conversions",
            "revenue",
            "leads",
            "sales",
        }
    else:
        fields = {
            "spend",
            "views",
            "watch_time",
            "retention",
            "subscribers",
            "reach",
            "impressions",
            "clicks",
            "engagements",
            "conversions",
            "leads",
            "revenue",
            "sales",
            "frequency",
            "ctr",
            "cpc",
            "cpa",
        }
    profile["optional"] = sorted(fields)
    profile["expected_units"] = {k: "ratio" for k in {"ctr", "retention"} & fields}
    profile["nonadditive"] = sorted(set(NONADDITIVE) | {"position", "retention"})


def validate_media(artifact):
    rows = artifact["rows"]
    profile = artifact["profile"]
    units = artifact["units"]
    dims = artifact["dimensions"]
    columns = set(rows[0])
    dimension_fields = {
        "date",
        "campaign",
        "region",
        "channel",
        "platform",
        "strategy",
        "format",
        "segment",
    }
    metric_fields = columns - dimension_fields
    supported = set(profile["required"]) | set(profile["optional"])
    applicability = (
        "undetermined"
        if not metric_fields
        else "applicable"
        if metric_fields & supported
        else "not_applicable"
    )
    field_states = {
        field: {
            "state": "applicable"
            if field in supported or field in dimension_fields
            else "not_applicable"
            if field in OPTIONAL
            else "undetermined",
            "present": field in columns,
            "null_count": sum(row.get(field) is None for row in rows) if field in columns else None,
            "reason": "Explicit selected profile "
            + profile["name"]
            + " version "
            + profile["version"],
        }
        for field in sorted(columns | supported)
    }
    required = profile["required"]
    missing = [c for c in required if c not in columns]
    errors = []
    for metric, unit in profile.get("expected_units", {}).items():
        if metric in columns and units.get(metric) not in {None, unit}:
            errors.append({"rule": "incompatible_unit", "field": metric, "expected": unit})
    warnings = []
    dates = []
    keys = set()
    duplicates = 0
    missing_cells = 0
    for index, row in enumerate(rows):
        try:
            day = date.fromisoformat(row.get("date", ""))
            dates.append(day)
        except (ValueError, TypeError):
            errors.append({"row": index + 1, "rule": "invalid_date"})
        key = tuple(
            row.get(c)
            for c in [
                "date",
                "campaign",
                "region",
                "platform",
                "channel",
                "strategy",
                "segment",
                "format",
            ]
        )
        if key in keys:
            duplicates += 1
        keys.add(key)
        for c, v in row.items():
            if v is None:
                missing_cells += 1
                if c in required:
                    errors.append({"row": index + 1, "field": c, "rule": "required_null"})
            elif c not in {
                "date",
                "campaign",
                "region",
                "channel",
                "platform",
                "strategy",
                "format",
                "segment",
            }:
                if (
                    not isinstance(v, (int, float))
                    or isinstance(v, bool)
                    or not math.isfinite(v)
                    or v < 0
                ):
                    errors.append({"row": index + 1, "field": c, "rule": "invalid_numeric"})
        for rate, num, den in [
            ("ctr", "clicks", "impressions"),
            ("cpc", "spend", "clicks"),
            ("cpa", "spend", "conversions"),
        ]:
            if all(isinstance(row.get(c), (int, float)) for c in [rate, num, den]):
                if row[den] <= 0 or not math.isclose(
                    row[rate], row[num] / row[den], rel_tol=0.02, abs_tol=1e-6
                ):
                    errors.append({"row": index + 1, "field": rate, "rule": "rate_or_denominator"})
        if (
            all(isinstance(row.get(c), (int, float)) for c in ["clicks", "impressions"])
            and row["clicks"] > row["impressions"]
        ):
            warnings.append("clicks_exceed_impressions: confirm metric definitions")
    if duplicates:
        errors.append({"rule": "duplicate_grain", "count": duplicates})
    if missing:
        errors.append({"rule": "missing_required", "fields": missing})
    unknown_units = [
        c
        for c in columns
        if c
        not in {
            "date",
            "campaign",
            "region",
            "channel",
            "platform",
            "strategy",
            "format",
            "segment",
        }
        and not units.get(c)
    ]
    if unknown_units:
        warnings.append("Unidentified units: " + ", ".join(sorted(unknown_units)))
    if "spend" in columns and units.get("spend") not in {"BRL", "USD", "EUR", "GBP"}:
        warnings.append("Currency must be explicitly reviewed")
    if profile["name"] in {"tv", "radio", "print"} and columns & {
        "audience",
        "reach",
        "rating",
        "share",
        "readers",
        "circulation",
        "grp",
        "trp",
    }:
        absent = [
            c
            for c in ["universe", "methodology", "region", "measurement_period"]
            if not dims.get(c)
        ]
        if absent:
            warnings.append("Audience definitions missing: " + ", ".join(absent))
    gaps = []
    unique = sorted(set(dates))
    for a, b in zip(unique, unique[1:]):
        if (b - a).days != artifact["frequency_days"]:
            gaps.append([a.isoformat(), b.isoformat()])
    if gaps:
        warnings.append("Irregular dates or missing periods")
    if not dims.get("channel") or not dims.get("strategy"):
        warnings.append("Confirm channel and traffic strategy explicitly")
    strategy = dims.get("strategy")
    strategy_mismatch = False
    if (profile["name"].endswith("_organic") or profile["name"] == "seo") and strategy in {
        "paid",
        "boosted",
    }:
        strategy_mismatch = True
    if (
        profile["name"].endswith(("_paid", "_ads")) or profile["name"] == "search_ads"
    ) and strategy == "organic":
        strategy_mismatch = True
    if strategy_mismatch:
        applicability = "not_applicable"
        warnings.append(
            "traffic_strategy_mismatch: select a profile compatible with the declared strategy"
        )
    metric_columns = columns - {
        "date",
        "campaign",
        "region",
        "channel",
        "platform",
        "strategy",
        "format",
        "segment",
    }
    insufficient = not metric_columns or not dates
    status = (
        "invalid"
        if errors
        else "insufficient"
        if insufficient
        else "valid_with_warnings"
        if warnings
        else "valid"
    )
    return {
        "dataset_applicability": {
            "state": applicability,
            "profile": profile["name"],
            "version": profile["version"],
            "reason": "Declared traffic strategy is incompatible with this profile"
            if strategy_mismatch
            else "Metric intersection with the explicitly selected profile",
        },
        "analysis_applicability": {
            "growth": {
                "state": applicability if not errors else "undetermined",
                "reason": "Profile compatibility and complete valid observations required",
            },
            "mmm": {
                "state": "undetermined",
                "reason": "Requires explicit KPI, media, controls and backend eligibility assessment",
            },
        },
        "field_applicability": field_states,
        "validation_version": "1",
        "status": status,
        "missing_required": missing,
        "not_applicable": sorted(set(OPTIONAL) - set(profile["optional"]) - set(required)),
        "optional_absent": sorted(set(profile["optional"]) - columns),
        "errors": errors[:100],
        "warnings": list(dict.fromkeys(warnings)),
        "duplicates": duplicates,
        "gaps": gaps[:100],
        "row_count": len(rows),
        "period": [min(dates).isoformat(), max(dates).isoformat()] if dates else None,
        "completeness_percent": 100 * (1 - missing_cells / (len(rows) * len(columns))),
        "unknown_units": unknown_units,
        "growth_compatible": not errors and not insufficient and applicability == "applicable",
        "mmm_eligible": False,
        "mmm_reason": "Use check_mmm_eligibility with an explicit outcome, media inputs and engine; numerical validity alone is insufficient.",
    }


def eligibility(artifact, request):
    from pydantic import ValidationError

    from .schemas import BackendRequest, TrainRequest

    rows = artifact["rows"]
    reasons = []
    contract = TrainRequest if request.backend == "ridge" else BackendRequest
    specification = {
        "dataset_id": "eligibility-check",
        "date_column": "date",
        "target_column": request.kpi,
        "media_columns": request.media,
        "control_columns": request.controls,
    }
    if request.backend != "ridge":
        specification["backend"] = request.backend
    try:
        contract.model_validate(specification)
    except ValidationError:
        reasons.append(
            "Column names, channel/control counts or distinct fields violate the selected adapter input contract"
        )
    if artifact["frequency_days"] not in {1, 7}:
        reasons.append("Current adapter accepts daily or weekly frequency only")
    media_units = {artifact["units"].get(column) for column in request.media}
    if len(media_units) != 1 or not media_units <= {"BRL", "USD", "EUR", "GBP"}:
        reasons.append(
            "Current adapter requires spend in one common currency, not independent exposure or mixed currencies"
        )
    elif request.target_type == "revenue" and artifact["units"].get(request.kpi) not in media_units:
        reasons.append("Revenue KPI must use the same currency as media spend")
    report = validate_media(artifact)
    if report["dataset_applicability"]["state"] != "applicable":
        reasons.append("Select a compatible media profile and declared traffic strategy")
    if report["errors"] or report["gaps"] or report["unknown_units"]:
        reasons.append("Resolve quality, temporal regularity and units")
    unique_dates = {r.get("date") for r in rows}
    if len(unique_dates) != len(rows):
        reasons.append("Aggregate to exactly one observation per date before MMM")
    if len(unique_dates) < 52:
        reasons.append("At least 52 regular observations required for this screen")
    columns = [request.kpi, *request.media, *request.controls]
    if len(set(columns)) != len(columns):
        reasons.append("Outcome, controls and media must be distinct")
    values = []
    for column in columns:
        v = [r.get(column) for r in rows]
        if any(
            not isinstance(x, (float, int)) or isinstance(x, bool) or not math.isfinite(x)
            for x in v
        ):
            reasons.append("Missing or nonnumeric model column: " + column)
        elif np.std(v) < 1e-8:
            reasons.append("Insufficient variation: " + column)
        elif column in request.media:
            values.append(v)
    if len(values) > 1 and np.any(
        np.abs(np.corrcoef(values)[np.triu_indices(len(values), 1)]) > 0.95
    ):
        reasons.append("Highly correlated media inputs")
    if not request.controls:
        reasons.append("No controls declared; confounding requires review")
    if not artifact["dimensions"].get("kpi_definition"):
        reasons.append("Declare outcome measurement definition")
    if request.backend == "google_meridian" and request.target_type != "revenue":
        reasons.append("Current Meridian adapter requires a declared revenue KPI")
    if request.backend == "meta_robyn" and request.target_type == "unspecified":
        reasons.append("Current Robyn adapter requires revenue or non_revenue target type")
    return {
        "eligible": not reasons,
        "applicability": {
            "state": "applicable"
            if not reasons
            else "not_applicable"
            if report["dataset_applicability"]["state"] == "not_applicable"
            else "undetermined",
            "reason": "Engine-specific assessment requires all design and data requirements",
        },
        "backend": request.backend,
        "input_contract": contract.__name__,
        "media_interpretation": "spend proxy in one declared currency; no independent exposure or geographic dimensions invented",
        "blocking_reasons": reasons,
        "assessment": "preliminary_design_screen",
        "causal_identification": False,
        "warnings": [
            "Seasonality, lag choice, measurement changes and omitted confounding require substantive review."
        ],
    }
