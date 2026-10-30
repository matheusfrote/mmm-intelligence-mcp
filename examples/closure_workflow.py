"""Reproducible synthetic MCP demonstration: every format, profile and new analysis.

Use --native for the three actual isolated engines; omitted native cycles are
explicitly marked unverified. A new output directory is required.
"""

import argparse
import asyncio
import base64
import csv
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
from mcp import Client, StdioServerParameters

from mmm_intelligence.datasets import generate
from mmm_intelligence.schemas import GenerateRequest


def format_bytes(rows, fmt):
    stream = io.BytesIO()
    options = {}
    if fmt in {"csv", "tsv"}:
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=rows[0], delimiter="\t" if fmt == "tsv" else ",")
        writer.writeheader()
        writer.writerows(rows)
        raw = text.getvalue().encode()
    elif fmt in {"json", "jsonl"}:
        raw = (json.dumps(rows) if fmt == "json" else "\n".join(map(json.dumps, rows))).encode()
    elif fmt == "xlsx":
        from openpyxl import Workbook

        book = Workbook()
        book.active.append(list(rows[0]))
        for row in rows:
            book.active.append(list(row.values()))
        book.save(stream)
        raw = stream.getvalue()
    elif fmt == "xls":
        import xlwt

        book = xlwt.Workbook()
        sheet = book.add_sheet("data")
        for i, row in enumerate([list(rows[0]), *[list(r.values()) for r in rows]]):
            for j, value in enumerate(row):
                sheet.write(i, j, value)
        book.save(stream)
        raw = stream.getvalue()
    elif fmt == "parquet":
        import pyarrow as pa
        import pyarrow.parquet as pq

        pq.write_table(pa.Table.from_pylist(rows), stream, compression="zstd")
        raw = stream.getvalue()
    else:
        # This fixture has fixed identifier/numeric/date values, not arbitrary user XML.
        raw = (
            "<root>"
            + "".join(
                "<record>"
                + "".join(f"<{key}>{value}</{key}>" for key, value in row.items())
                + "</record>"
                for row in rows
            )
            + "</root>"
        ).encode()
        options = {"xml_record": "record", "xml_fields": {key: key for key in rows[0]}}
    return raw, options


async def run(output, native):
    project = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    env = {
        **os.environ,
        "MMM_DATA_DIR": str(output / "data"),
        "MMM_TRANSPORT": "stdio",
        "MMM_ALLOW_REAL_DATA": "false",
        "MMM_MAX_FILE_BYTES": "52428800",
        "MMM_BACKEND_TIMEOUT_SECONDS": "1800",
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mmm_intelligence.server"], cwd=project, env=env
    )
    calls, artifacts, model_receipts = [], [], {}
    async with Client(params, read_timeout_seconds=2000) as client:

        async def call(tool, **request):
            result = await client.call_tool(tool, {"request": request})
            assert not result.is_error and result.structured_content["ok"], (
                result.structured_content
            )
            calls.append(tool)
            return result.structured_content["data"]

        async def imported(rows, fmt, name):
            raw, options = format_bytes(rows, fmt)
            (output / (name + "." + fmt)).write_bytes(raw)
            arguments = {
                "format": fmt,
                "content_base64": base64.b64encode(raw).decode(),
                "synthetic": True,
                "origin": "fabricated " + name,
                **options,
            }
            preview = await call("preview_dataset", **arguments)
            assert preview["row_count"] == len(rows)
            return await call("import_source", **arguments, confirm=True)

        async def mapped(rows, fmt, name, profile, units, dimensions):
            source = await imported(rows, fmt, name)
            result = await call(
                "map_dataset_schema",
                source_id=source["artifact_id"],
                profile=profile,
                mapping={key: key for key in rows[0]},
                units=units,
                dimensions=dimensions,
            )
            return result

        discovered = await client.list_tools()
        assert len(discovered.tools) == 45
        profile_list = (await call("list_media_profiles"))["profiles"]
        profile_ids = []
        for profile in profile_list:
            name = profile["name"]
            metric = (
                "insertions"
                if name in {"tv", "radio"}
                else "circulation"
                if name == "print"
                else "sessions"
                if name == "website"
                else "clicks"
                if name in {"seo", "search_ads"}
                else "views"
                if profile["family"] == "video"
                else "engagements"
            )
            rows = [{"date": "2026-01-05", metric: 100}, {"date": "2026-01-12", metric: 110}]
            frame = await mapped(
                rows,
                "csv",
                name,
                name,
                {metric: "count"},
                {
                    "channel": name,
                    "strategy": "organic" if name.endswith("_organic") or name == "seo" else "paid",
                    "region": "BR",
                    "methodology": "synthetic count",
                    "universe": "fabricated aggregate",
                    "measurement_period": "weekly",
                },
            )
            quality = await call("validate_media_dataset", artifact_id=frame["artifact_id"])
            assert quality["dataset_applicability"]["state"] == "applicable"
            profile_ids.append(frame["artifact_id"])
        crossmedia = await call("validate_crossmedia_dataset", artifact_ids=profile_ids)
        rows = [
            {"date": "2026-01-05", "spend": 10.5, "sales": 5},
            {"date": "2026-01-12", "spend": 20.0, "sales": 6},
        ]
        equivalents = []
        for fmt in ["csv", "tsv", "json", "jsonl", "xlsx", "xls", "parquet", "xml"]:
            frame = await mapped(
                rows,
                fmt,
                "equivalent-" + fmt,
                "search_ads",
                {"spend": "BRL", "sales": "count"},
                {"channel": "search", "strategy": "paid", "kpi_definition": "fabricated sales"},
            )
            assert frame["rows"] == rows
            equivalents.append(frame)
        joined = await call(
            "join_datasets",
            left_id=equivalents[0]["artifact_id"],
            right_id=equivalents[1]["artifact_id"],
            keys={"date": "date"},
        )
        assert not joined["blocked"] and joined["output_rows"] == 2
        joined = await call(
            "join_datasets",
            left_id=equivalents[0]["artifact_id"],
            right_id=equivalents[1]["artifact_id"],
            keys={"date": "date"},
            confirm=True,
        )
        canonical_join = await call(
            "build_growth_dataset",
            artifact_ids=[joined["artifact_id"]],
            aggregations={
                "spend": "sum",
                "sales": "sum",
                "spend_right": "sum",
                "sales_right": "sum",
            },
        )
        assert len(canonical_join["observations"]) == 2
        assert len(canonical_join["observations"][0]["source_ids"]) == 2
        artifacts.append(canonical_join)
        artifacts.append(joined)
        model_rows = generate(GenerateRequest(periods=104))["rows"]
        custom = await call(
            "register_media_profile",
            name="closure_frame",
            version="1",
            family="synthetic",
            required=list(model_rows[0]),
        )
        frame = await mapped(
            model_rows,
            "json",
            "model-frame",
            custom["artifact_id"],
            {
                key: "BRL" if key.startswith("spend_") or key == "revenue" else "index"
                for key in model_rows[0]
                if key != "date"
            },
            {
                "channel": "fabricated multi",
                "strategy": "paid",
                "kpi_definition": "synthetic revenue",
            },
        )
        trend = await call(
            "analyze_growth",
            artifact_id=frame["artifact_id"],
            metrics=["revenue", "spend_search"],
            lag_pairs=[{"spend": "spend_search", "outcome": "revenue"}],
        )
        artifacts.append(trend)
        for backend in ["ridge", "google_meridian", "pymc_marketing", "meta_robyn"]:
            prepared = await call(
                "prepare_mmm_dataset",
                artifact_id=frame["artifact_id"],
                backend=backend,
                kpi="revenue",
                media=["spend_search", "spend_social", "spend_video"],
                controls=["price_index", "promotion"],
                target_type="revenue",
                currency="BRL",
            )
            model_receipts[backend] = {"preparation": prepared, "native_cycle_verified": False}
            if backend == "ridge" or native:
                request = prepared["training_request"]
                if backend != "ridge":
                    request = {**request, "draws": 20, "tune": 20}
                fitted = await call(prepared["training_tool"], **request)
                metadata = await call(
                    "get_model" if backend == "ridge" else "get_backend_model",
                    model_id=fitted["model_id"],
                )
                assert metadata["dataset_sha256"] == prepared["sha256"]
                model_receipts[backend].update(
                    model_id=fitted["model_id"],
                    native_cycle_verified=True,
                    expected=None if backend == "ridge" else metadata["test"]["mean"],
                    convergence_certified=False,
                )
        units = [
            {
                "unit": str(i),
                "arm": "C" if i < 100 else "T",
                "conversion": int(i % 10 < (2 if i < 100 else 4)),
                "refunds": 0,
                "cost": 2,
                "date": "2026-01-15",
                "eligible": "yes",
                "event": "entry",
            }
            for i in range(200)
        ]
        observations = await imported(units, "json", "experiment-units")
        cohort = await call(
            "analyze_cohorts",
            artifact_id=observations["artifact_id"],
            unit_column="unit",
            event_column="event",
            entry_event="entry",
            return_event="return",
            as_of="2026-01-31",
            horizon=3,
        )
        assert cohort["cohorts"][0]["periods"][2]["eligible"] == 0
        plan = await call(
            "plan_experiment",
            method="randomized",
            outcome_type="binary",
            kpi="conversion",
            unit_column="unit",
            group_column="arm",
            treatment="T",
            control="C",
            baseline=0.2,
            minimum_effect=0.1,
            population="fabricated eligible accounts",
            measurement_window="2026-01-01/2026-01-31",
            stop_rule="fixed horizon",
            guardrails=["refunds"],
            comparison_family_size=2,
            guardrail_specs={
                "refunds": {
                    "outcome_type": "binary",
                    "direction": "increase",
                    "max_adverse_change": 0.1,
                }
            },
            cost_column="cost",
            hypothesis="T changes conversion by .1",
            analysis_plan="ITT complete cases with attrition report",
            randomization_unit="unit",
            duration_days=31,
            conversion_window_days=7,
            observation_start="2026-01-01",
            observation_end="2026-01-31",
            date_column="date",
            population_column="eligible",
            population_value="yes",
            exclusion_criteria="No exclusions",
            operational_constraints="No live actions",
        )
        result = await call(
            "analyze_experiment",
            artifact_id=observations["artifact_id"],
            plan_id=plan["artifact_id"],
        )
        assert (
            abs(result["estimate"]["difference"] - 0.2) < 1e-12
            and result["cost_per_conversion"]["treatment"] == 5
        )
        artifacts.extend([cohort, plan, result])
        diagnostic = await call("create_growth_diagnostic", artifact_id=frame["artifact_id"])
        decision = await call(
            "create_growth_decision",
            diagnostic_id=diagnostic["artifact_id"],
            problem="Synthetic hypothesis",
            hypothesis="T changes conversion",
            action="External manual experiment",
            kpi="conversion",
            guardrails=["refunds"],
            baseline=".2",
            horizon="31 days",
            method="randomized",
            risks=["assignment not authenticated"],
        )
        assumption_keys = [
            "hypothesis",
            "unit",
            "window",
            "duration",
            "sample_assumptions",
            "control",
            "success",
            "stop",
            "guardrails",
        ]
        for state in ["approved", "planned", "evaluated", "learned"]:
            extra = (
                {
                    "plan": {
                        **{key: "declared in linked statistical plan" for key in assumption_keys},
                        "experiment_plan_id": plan["artifact_id"],
                    }
                }
                if state == "planned"
                else {"results_id": result["artifact_id"]}
                if state == "evaluated"
                else {}
            )
            decision = await call(
                "transition_growth_decision",
                artifact_id=decision["artifact_id"],
                state=state,
                actor="synthetic reviewer declaration",
                note="Synthetic evidence only; no causal or commercial claim",
                **extra,
            )
        artifacts.append(decision)
    async with Client(params, read_timeout_seconds=2000) as restarted:
        for artifact in artifacts:
            restored = await restarted.call_tool(
                "get_growth_artifact", {"request": {"artifact_id": artifact["artifact_id"]}}
            )
            assert restored.structured_content["data"] == artifact
        for backend, record in model_receipts.items():
            if not record["native_cycle_verified"]:
                continue
            if backend == "ridge":
                response = await restarted.call_tool(
                    "simulate_budget",
                    {
                        "request": {
                            "model_id": record["model_id"],
                            "horizon": 4,
                            "total_budget": 12000.0,
                            "allocation": {
                                "spend_search": 0.5,
                                "spend_social": 0.3,
                                "spend_video": 0.2,
                            },
                        }
                    },
                )
            else:
                response = await restarted.call_tool(
                    "predict_backend", {"request": {"model_id": record["model_id"]}}
                )
                calls.append("predict_backend")
                assert response.structured_content["ok"], response.structured_content
                np.testing.assert_allclose(
                    response.structured_content["data"]["prediction"]["mean"],
                    record["expected"],
                    rtol=1e-5,
                    atol=1e-5,
                )
                response = await restarted.call_tool(
                    "predict_backend",
                    {
                        "request": {
                            "model_id": record["model_id"],
                            "media_multiplier": {"spend_search": 1.1},
                        }
                    },
                )
                calls.append("predict_backend")
                assert response.structured_content["ok"], response.structured_content
                scenario = response.structured_content["data"]
                if backend == "meta_robyn":
                    reference = await restarted.call_tool(
                        "predict_backend",
                        {
                            "request": {
                                "model_id": record["model_id"],
                                "media_multiplier": {"spend_search": 1.0},
                            }
                        },
                    )
                    calls.append("predict_backend")
                    assert reference.structured_content["ok"]
                    actual = scenario["responses"]["spend_search"]
                    baseline = reference.structured_content["data"]["responses"]["spend_search"]
                    assert np.isclose(
                        actual["scenario_mean_spend"], 1.1 * baseline["scenario_mean_spend"]
                    )
                    assert not np.isclose(
                        actual["scenario_mean_response"], baseline["scenario_mean_response"]
                    )
                else:
                    assert not np.allclose(
                        scenario["prediction"]["mean"], record["expected"], rtol=1e-8, atol=1e-8
                    )
                record["scenario_effect_verified"] = True
            assert response.structured_content["ok"], response.structured_content
            record["restart_scenario_verified"] = True
    receipt = {
        "synthetic": True,
        "tools": 45,
        "profiles": len(profile_ids),
        "formats": ["csv", "tsv", "json", "jsonl", "xlsx", "xls", "parquet", "xml"],
        "format_equivalence_verified": True,
        "calls": calls,
        "crossmedia": crossmedia,
        "models": model_receipts,
        "artifact_reload_verified": True,
        "artifacts": [item["artifact_id"] for item in artifacts],
        "native_cycles_requested": native,
        "causal_identification": False,
        "production_modified": False,
    }
    (output / "result.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    (output / "report.md").write_text(
        "# Synthetic integral MCP demonstration\n\nNo causal or commercial effectiveness established. Native short runs do not certify convergence.\n\n"
        + json.dumps(receipt, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "profiles": len(profile_ids),
                "formats": 8,
                "calls": len(calls),
                "restart_verified": True,
                "native": native,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    options = parser.parse_args()
    asyncio.run(run(options.output_dir.resolve(), options.native))
