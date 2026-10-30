"""Descriptive trends and aggregate cohorts with explicit censoring and suppression."""

import math
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from scipy.stats import linregress

from .errors import MMMError
from .storage import digest


def level_change(values, dates, regular):
    """One exploratory two-level split, BIC improvement >10; no significance claim."""
    n = len(values)
    if not regular or n < 12 or np.ptp(values) <= 1e-12:
        return None
    # Center first to limit cancellation; prefix sums keep the scan linear in n.
    centered = values - np.mean(values)
    sums = np.r_[0, np.cumsum(centered)]
    squares = np.r_[0, np.cumsum(centered**2)]
    splits = np.arange(4, n - 3)
    sse = np.maximum(0, squares[splits] - sums[splits] ** 2 / splits)
    sse += np.maximum(
        0, squares[-1] - squares[splits] - (sums[-1] - sums[splits]) ** 2 / (n - splits)
    )
    null_sse = max(float(np.sum(centered**2)), np.finfo(float).tiny)
    floors = np.maximum(sse, np.finfo(float).eps * null_sse)
    improvement = n * np.log(null_sse / floors) - 2 * math.log(n)
    best = int(np.argmax(improvement))
    if improvement[best] <= 10:
        return None
    index = int(splits[best])
    return {
        "date": dates[index].isoformat(),
        "before_mean": float(np.mean(values[:index])),
        "after_mean": float(np.mean(values[index:])),
        "bic_improvement": float(improvement[best]),
        "method": "One split with >=4 observations per side; Gaussian constant-variance BIC, k=3 vs k=1; improvement >10",
        "causal_identification": False,
        "limitation": "Exploratory level approximation may also reflect smooth trend, seasonality or outliers; no calibrated change-point interval",
    }


def temporal_analysis(artifact, request):
    for pair in request.lag_pairs:
        if (
            set(pair) != {"spend", "outcome"}
            or any(column not in request.metrics for column in pair.values())
            or pair["spend"] == pair["outcome"]
        ):
            raise MMMError(
                "ANALYSIS_LAG",
                "Declare distinct spend/outcome columns included in selected metrics",
            )
    groups = defaultdict(list)
    for row in artifact["rows"]:
        if any(k not in row for k in ["date", *request.group_by, *request.metrics]):
            raise MMMError("ANALYSIS_FIELDS", "Missing analysis columns")
        groups[tuple(row[k] for k in request.group_by)].append(row)
    output = []
    suppressed = 0
    for key, rows in groups.items():
        if len(rows) < request.minimum_group_size:
            suppressed += 1
            continue
        rows = sorted(rows, key=lambda r: r["date"])
        dates = [date.fromisoformat(r["date"]) for r in rows]
        if len(set(dates)) != len(dates):
            raise MMMError("ANALYSIS_GRAIN", "Aggregate to one observation per date and segment")
        days = np.array([(d - dates[0]).days for d in dates], dtype=float)
        regular = all((b - a).days == artifact["frequency_days"] for a, b in zip(dates, dates[1:]))
        metrics = {}
        for column in request.metrics:
            raw = [r[column] for r in rows]
            if any(v is None for v in raw):
                metrics[column] = {
                    "status": "insufficient",
                    "reason": "Missing observations; no automatic imputation",
                }
                continue
            if any(
                not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                for v in raw
            ):
                raise MMMError("ANALYSIS_TYPE", "Metrics must be finite numeric observations")
            values = np.array(raw, dtype=float)
            half = len(values) // 2
            baseline = float(np.mean(values[:half]))
            recent = float(np.mean(values[-half:]))
            delta = recent - baseline
            rolling = [
                float(np.mean(values[i - request.rolling_window + 1 : i + 1]))
                if i >= request.rolling_window - 1
                else None
                for i in range(len(values))
            ]
            median = float(np.median(values))
            mad = float(np.median(np.abs(values - median)))
            anomaly_dates = [
                d.isoformat()
                for d, v in zip(dates, values)
                if mad > 0 and 0.67448975 * abs(v - median) / mad > 3.5
            ]
            slope = float(linregress(days, values).slope) if regular and len(rows) >= 8 else None
            seasonal = None
            lag = 52 if artifact["frequency_days"] == 7 else 365
            if (
                regular
                and len(values) >= 2 * lag
                and np.std(values[:-lag]) > 0
                and np.std(values[lag:]) > 0
            ):
                seasonal = float(np.corrcoef(values[:-lag], values[lag:])[0, 1])
            metrics[column] = {
                "status": "descriptive",
                "unit": artifact["units"].get(column),
                "dates": [d.isoformat() for d in dates],
                "values": raw,
                "rolling_mean": rolling,
                "baseline_period_mean": baseline,
                "recent_period_mean": recent,
                "period_size": half,
                "absolute_change": delta,
                "percent_change": 100 * delta / baseline if baseline else None,
                "slope_per_day": slope,
                "robust_anomaly_dates": anomaly_dates,
                "seasonal_lag_correlation": seasonal,
                "level_change_candidate": level_change(values, dates, regular),
                "regular": regular,
                "anomaly_method": "global median/MAD modified z >3.5; zero MAD abstains",
                "limitations": [
                    "Period comparison uses equal observation counts; irregular windows need review.",
                    "Slope and lag correlation are descriptive, not causal or a change-point identification.",
                ],
            }
        lags = []
        for pair in request.lag_pairs:
            correlations = []
            complete = all(metrics[name]["status"] == "descriptive" for name in pair.values())
            if complete and regular and len(rows) >= max(12, 2 * (request.max_lag + 3)):
                spend = np.array([row[pair["spend"]] for row in rows], float)
                outcome = np.array([row[pair["outcome"]] for row in rows], float)
                for lag in range(request.max_lag + 1):
                    x = spend[:-lag] if lag else spend
                    y = outcome[lag:]
                    correlations.append(
                        {
                            "lag_periods": lag,
                            "paired_observations": len(x),
                            "correlation": float(np.corrcoef(x, y)[0, 1])
                            if np.std(x) > 0 and np.std(y) > 0
                            else None,
                        }
                    )
            lags.append(
                {
                    **pair,
                    "status": "descriptive" if correlations else "insufficient",
                    "correlations": correlations,
                    "causal_identification": False,
                    "definition": "spend[t] versus outcome[t+lag]; no automatic best-lag selection or significance claim",
                }
            )
        output.append(
            {
                "segment": dict(zip(request.group_by, key)),
                "observations": len(rows),
                "metrics": metrics,
                "lag_associations": lags,
            }
        )
    return {
        "source_id": artifact["artifact_id"],
        "source_sha256": digest(artifact),
        "synthetic": artifact["synthetic"],
        "parameters": request.model_dump(),
        "groups": output,
        "suppressed_groups": suppressed,
        "causal_identification": False,
        "method_version": "descriptive-temporal-1",
        "warnings": ["No channel ranking, significance claim or causal recommendation."],
    }


def cohort_analysis(artifact, request):
    if bool(request.population_column) != bool(request.population_value):
        raise MMMError("COHORT_POPULATION", "Declare population column and eligible value together")
    as_of = date.fromisoformat(request.as_of)
    events = defaultdict(list)
    seen = {}
    duplicates = 0
    future = 0
    for row in artifact["rows"]:
        if any(
            k not in row or row[k] is None
            for k in [
                request.unit_column,
                request.event_column,
                request.date_column,
                *request.group_by,
            ]
        ):
            raise MMMError(
                "COHORT_FIELDS",
                "Cohorts require complete unit, event, date and selected dimensions",
            )
        day = date.fromisoformat(row[request.date_column])
        if day > as_of:
            future += 1
            continue
        key = (row[request.unit_column], row[request.event_column], day)
        dimensions = tuple(row[field] for field in request.group_by)
        if key in seen:
            if seen[key] != dimensions:
                raise MMMError(
                    "COHORT_GRAIN", "Duplicate unit/event/date has conflicting cohort dimensions"
                )
            duplicates += 1
            continue
        seen[key] = dimensions
        events[row[request.unit_column]].append((day, row))
    groups = defaultdict(list)
    excluded_ineligible = 0
    for unit, observations in events.items():
        entries = sorted(
            (day, row)
            for day, row in observations
            if row[request.event_column] == request.entry_event
        )
        if not entries:
            continue
        entry, first = entries[0]
        if request.population_column:
            if request.population_column not in first or first[request.population_column] is None:
                raise MMMError(
                    "COHORT_POPULATION", "First entry must declare population eligibility"
                )
            if first[request.population_column] != request.population_value:
                excluded_ineligible += 1
                continue
        # Cohort dates use calendar weeks/days, while individual follow-up starts at entry.
        cohort = entry - timedelta(days=entry.weekday()) if request.frequency_days == 7 else entry
        key = (cohort.isoformat(), *(first[k] for k in request.group_by))
        returns = {
            day
            for day, row in observations
            if row[request.event_column] == request.return_event and day >= entry
        }
        groups[key].append((entry, returns))
    output = []
    suppressed = 0
    for key, members in groups.items():
        if len(members) < request.minimum_group_size:
            suppressed += 1
            continue
        periods = []
        for period in range(request.horizon):
            eligible = []
            for entry, returns in members:
                start = entry + timedelta(days=period * request.frequency_days)
                end = start + timedelta(days=request.frequency_days)
                if end <= as_of + timedelta(days=1):
                    eligible.append((entry, start, end, returns))
            retained = sum(
                any((entry if request.cumulative else start) <= day < end for day in returns)
                for entry, start, end, returns in eligible
            )
            periods.append(
                {
                    "period": period,
                    "eligible": len(eligible),
                    "censored": len(members) - len(eligible),
                    "retained": retained if len(eligible) >= request.minimum_group_size else None,
                    "rate": retained / len(eligible)
                    if len(eligible) >= request.minimum_group_size
                    else None,
                    "suppressed": 0 < len(eligible) < request.minimum_group_size,
                }
            )
        output.append(
            {
                "cohort": key[0],
                "segment": dict(zip(request.group_by, key[1:])),
                "entry_population": len(members),
                "periods": periods,
            }
        )
    return {
        "source_id": artifact["artifact_id"],
        "source_sha256": digest(artifact),
        "synthetic": artifact["synthetic"],
        "parameters": request.model_dump(),
        "cohorts": output,
        "suppressed_groups": suppressed,
        "duplicate_events": duplicates,
        "future_events_excluded": future,
        "excluded_ineligible_units": excluded_ineligible,
        "method_version": "complete-window-cohort-1",
        "causal_identification": False,
        "warnings": [
            "Only complete individual follow-up windows enter denominators. No personal identifiers are returned."
        ],
    }
