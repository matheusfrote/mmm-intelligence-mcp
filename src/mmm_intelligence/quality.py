"""Descriptive, evidence-bearing data quality screens without automatic cleaning."""

from datetime import date, timedelta

import numpy as np

from .datasets import validate


def assess(dataset, request, max_rows):
    report = validate(dataset, request, max_rows)
    alerts = [
        {"severity": "blocking", "code": s.split(":")[0], "evidence": s} for s in report["issues"]
    ]
    alerts += [
        {"severity": "moderate", "code": s.split(":")[0], "evidence": s} for s in report["warnings"]
    ]
    rows = dataset.get("rows", [])
    missing = []
    try:
        dates = sorted({date.fromisoformat(r[request.date_column]) for r in rows})
        step = 7 if dataset["frequency"] == "weekly" else 1
        if dates and (dates[-1] - dates[0]).days <= 36600:
            present = set(dates)
            missing = [
                (dates[0] + timedelta(days=i)).isoformat()
                for i in range(0, (dates[-1] - dates[0]).days + 1, step)
                if dates[0] + timedelta(days=i) not in present
            ]
    except (KeyError, ValueError, TypeError):
        pass
    numeric = [request.target_column, *request.media_columns, *request.control_columns]
    summary, correlations = {}, []
    arrays = {}
    for c in numeric:
        values = [r.get(c) for r in rows if isinstance(r, dict)]
        finite = [
            v
            for v in values
            if isinstance(v, (int, float))
            and not isinstance(v, bool)
            and np.isfinite(v)
            and abs(v) <= 1e12
        ]
        summary[c] = {"present_finite": len(finite), "missing_or_invalid": len(rows) - len(finite)}
        if finite:
            x = np.array(finite, float)
            summary[c].update(
                min=float(x.min()),
                max=float(x.max()),
                mean=float(x.mean()),
                std=float(x.std()),
                zero_fraction=float((x == 0).mean()),
            )
            q1, q3 = np.quantile(x, [0.25, 0.75])
            iqr = float(q3 - q1)
            count = int(((x < q1 - 3 * iqr) | (x > q3 + 3 * iqr)).sum()) if iqr > 0 else None
            summary[c].update(extreme_iqr_count=count, extreme_iqr_multiplier=3)
            if count:
                alerts.append(
                    {
                        "severity": "moderate",
                        "code": "EXTREME_IQR_SCREEN",
                        "channel": c,
                        "evidence": {
                            "count": count,
                            "lower": float(q1 - 3 * iqr),
                            "upper": float(q3 + 3 * iqr),
                        },
                        "interpretation": "Descriptive 3-IQR screen; skew and campaigns can explain extremes. No outliers removed. Undefined when IQR is zero.",
                    }
                )
            if len(finite) == len(rows):
                arrays[c] = x
                if c in request.media_columns and np.ptp(x) == 0:
                    alerts.append(
                        {
                            "severity": "severe",
                            "code": "CONSTANT_MEDIA",
                            "channel": c,
                            "evidence": "No observed variation; local training cannot identify this channel",
                        }
                    )
                if len(x) >= 52 and x[: len(x) // 2].mean() > 0:
                    ratio = float(x[len(x) // 2 :].mean() / x[: len(x) // 2].mean())
                    if ratio < 0.5 or ratio > 2:
                        alerts.append(
                            {
                                "severity": "moderate",
                                "code": "LEVEL_SHIFT_SCREEN",
                                "channel": c,
                                "evidence": {"second_half_to_first_half_mean": ratio},
                                "interpretation": "Operational screen; may reflect trend/seasonality or tracking, not a change-point test",
                            }
                        )
    names = [c for c in request.media_columns + request.control_columns if c in arrays]
    for j, a in enumerate(names):
        for b in names[j + 1 :]:
            if arrays[a].std() and arrays[b].std():
                corr = float(np.corrcoef(arrays[a], arrays[b])[0, 1])
                correlations.append({"a": a, "b": b, "correlation": corr})
                if abs(corr) > 0.95:
                    alerts.append(
                        {
                            "severity": "severe",
                            "code": "COLLINEARITY_SCREEN",
                            "evidence": correlations[-1],
                            "interpretation": "Descriptive screen, not proof of causal nonidentification",
                        }
                    )
    alerts.append(
        {
            "severity": "informational",
            "code": "CAUSAL_CONTEXT_REQUIRED",
            "evidence": "Omitted confounders and endogeneity cannot be ruled out by tabular checks",
        }
    )
    return {
        **report,
        "missing_periods": missing,
        "columns": summary,
        "correlations": correlations,
        "alerts": alerts,
        "transformations_applied": [],
        "business_recommendation_eligible": False,
        "backend_requirements": {
            "ridge": "Varying training media and adequate split required",
            "google_meridian": "Declared revenue; exposure proxy assumption and native diagnostics",
            "pymc_marketing": "MCMC diagnostics, prior sensitivity and PPC required",
            "meta_robyn": "Declared KPI type; native 60/20/20 split and search review",
        },
    }
