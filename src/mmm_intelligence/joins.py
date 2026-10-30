"""Explicit relational joins with grain/metric safeguards before materialization."""

from collections import defaultdict
from datetime import date, timedelta

from .errors import MMMError
from .storage import digest


def prepare(artifact, keys, rules, frequency):
    rows = [dict(row) for row in artifact["rows"]]
    if not rows or set(keys) - set(rows[0]):
        raise MMMError("JOIN_KEYS", "Join key is missing")
    for row in rows:
        if any(row[k] is None for k in keys):
            raise MMMError("JOIN_KEYS", "Null join keys are refused")
        if frequency != "original":
            if "date" not in keys:
                raise MMMError("JOIN_TIME", "Temporal alignment requires date in declared keys")
            day = date.fromisoformat(row["date"])
            if frequency == "weekly":
                day -= timedelta(days=day.weekday())
            row["date"] = day.isoformat()
    if not rules:
        return rows
    if set(rules) != set(rows[0]) - set(keys):
        raise MMMError(
            "JOIN_AGGREGATION", "Declare aggregation of every nonkey column before joining"
        )
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    result = []
    for key, values in groups.items():
        row = dict(zip(keys, key))
        for column, rule in rules.items():
            if column in artifact["profile"]["nonadditive"]:
                raise MMMError(
                    "NONADDITIVE", "Preaggregation cannot combine nonadditive media metrics"
                )
            numbers = [v[column] for v in values]
            if any(v is None for v in numbers):
                row[column] = None
            elif any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in numbers):
                raise MMMError("JOIN_AGGREGATION", "Numeric preaggregation required")
            else:
                row[column] = sum(numbers) / (len(numbers) if rule == "mean" else 1)
        result.append(row)
    return result


def combine(left, right, request, max_rows):
    target_days = {"daily": 1, "weekly": 7}.get(request.frequency)
    if target_days is not None and any(
        source["frequency_days"] > target_days for source in (left, right)
    ):
        raise MMMError(
            "JOIN_TIME",
            "Cannot upsample to a finer frequency without inventing source observations",
        )
    left_keys = list(request.keys)
    right_keys = list(request.keys.values())
    if len(set(right_keys)) != len(right_keys):
        raise MMMError("JOIN_KEYS", "Right keys must be distinct")
    a = prepare(left, left_keys, request.left_aggregations, request.frequency)
    b = prepare(right, right_keys, request.right_aggregations, request.frequency)
    indexes = []
    for rows, keys in [(a, left_keys), (b, right_keys)]:
        index = defaultdict(list)
        for row in rows:
            index[tuple(row[k] for k in keys)].append(row)
        indexes.append(index)
    ai, bi = indexes
    ad = any(len(v) > 1 for v in ai.values())
    bd = any(len(v) > 1 for v in bi.values())
    cardinality = ("m" if ad else "1") + ":" + ("m" if bd else "1")
    reasons = []
    if cardinality != request.cardinality:
        reasons.append("Observed cardinality differs from declared cardinality")
    if ad and bd:
        reasons.append("Many-to-many joins require preaggregation to a safe grain")
    numeric_a = [
        c for c in a[0] if c not in left_keys and any(isinstance(r[c], (int, float)) for r in a)
    ]
    numeric_b = [
        c for c in b[0] if c not in right_keys and any(isinstance(r[c], (int, float)) for r in b)
    ]
    if bd and numeric_a or ad and numeric_b:
        reasons.append("Join would duplicate numeric metrics; preaggregate first")
    unmatched_a = sum(len(v) for k, v in ai.items() if k not in bi)
    unmatched_b = sum(len(v) for k, v in bi.items() if k not in ai)
    if request.unmatched == "error" and (unmatched_a or unmatched_b):
        reasons.append("Unmatched records violate declared policy")
    if request.frequency == "original" and left["frequency_days"] != right["frequency_days"]:
        reasons.append("Different temporal frequencies require explicit alignment")
    if left["timezone"] != right["timezone"]:
        reasons.append("Normalize to a common reporting timezone first")
    common = set(ai) & set(bi)
    count = sum(len(ai[k]) * len(bi[k]) for k in common)
    count += unmatched_a if request.how in {"left", "full"} else 0
    count += unmatched_b if request.how in {"right", "full"} else 0
    if count > max_rows:
        reasons.append("Output row limit would be exceeded")
    names = {
        c: c if c not in a[0] else c + request.right_suffix for c in b[0] if c not in right_keys
    }
    if len(set(names.values())) != len(names) or set(names.values()) & set(a[0]):
        raise MMMError(
            "JOIN_COLUMNS", "Resulting column names collide; change suffix or source mapping"
        )
    context = {}
    conflicts = []
    for field in set(left["dimensions"]) | set(right["dimensions"]):
        lv = left["dimensions"].get(field)
        rv = right["dimensions"].get(field)
        if lv is not None and rv is not None and lv != rv:
            conflicts.append(field)
            if (
                field in {"kpi_definition", "universe", "methodology", "region", "currency"}
                and field not in request.context
            ):
                reasons.append("Resolve conflicting source context explicitly: " + field)
            context[field] = "mixed"
        else:
            context[field] = lv if lv is not None else rv
    context.update(request.context)
    summary = {
        "context_conflicts": conflicts,
        "left_rows": len(a),
        "right_rows": len(b),
        "left_source_rows": len(left["rows"]),
        "right_source_rows": len(right["rows"]),
        "left_unique_keys": len(ai),
        "right_unique_keys": len(bi),
        "observed_cardinality": cardinality,
        "unmatched_left": unmatched_a,
        "unmatched_right": unmatched_b,
        "matched_left": len(a) - unmatched_a,
        "matched_right": len(b) - unmatched_b,
        "output_rows": count,
        "metrics_at_risk": numeric_a + numeric_b if ad or bd else [],
        "blocked": bool(reasons),
        "blocking_reasons": reasons,
        "right_column_mapping": names,
        "warnings": [
            "Unmatched values remain null; equal keys do not establish comparable measurement."
        ],
    }
    if not request.confirm:
        return summary
    if reasons:
        raise MMMError("UNSAFE_JOIN", "; ".join(reasons))
    if not count:
        raise MMMError("EMPTY_JOIN", "No records survive this join")
    rows = []
    keys = (
        set(ai)
        if request.how == "left"
        else set(bi)
        if request.how == "right"
        else set(ai) | set(bi)
        if request.how == "full"
        else common
    )
    for key in sorted(keys, key=lambda k: tuple(str(v) for v in k)):
        for ar in ai.get(key, [None]):
            for br in bi.get(key, [None]):
                row = dict(ar) if ar else {c: None for c in a[0]}
                if ar is None:
                    for lk, rk in request.keys.items():
                        row[lk] = br[rk]
                row.update({target: br[column] if br else None for column, target in names.items()})
                rows.append(row)
    units = {**left["units"], **{names[k]: v for k, v in right["units"].items() if k in names}}
    return {
        "rows": rows,
        "source_ids": [left["artifact_id"], right["artifact_id"]],
        "source_hashes": [digest(left), digest(right)],
        "synthetic": left["synthetic"] and right["synthetic"],
        "units": units,
        "dimensions": context,
        "source_contexts": [left["dimensions"], right["dimensions"]],
        "timezone": left["timezone"],
        "frequency_days": 7
        if request.frequency == "weekly"
        else 1
        if request.frequency == "daily"
        else left["frequency_days"],
        "profile": {
            "name": "explicit_join",
            "version": "1",
            "required": ["date"],
            "optional": list(units),
            "nonadditive": list(
                set(left["profile"]["nonadditive"])
                | {names.get(k, k) for k in right["profile"]["nonadditive"]}
            ),
        },
        "transformation_version": "1",
        "join_request": request.model_dump(),
        "join_diagnostics": summary,
    }
