"""Real MCP cycle over synthetic multichannel files, decisions and restart."""

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def run(output):
    output.mkdir(parents=True, exist_ok=False)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mmm_intelligence.server"],
        env={
            **os.environ,
            "MMM_DATA_DIR": str((output / "data").resolve()),
            "MMM_TRANSPORT": "stdio",
            "MMM_ALLOW_REAL_DATA": "false",
        },
    )
    records = []
    async with Client(params) as client:

        async def call(name, **request):
            result = await client.call_tool(name, {"request": request})
            assert not result.is_error and result.structured_content["ok"], (
                result.structured_content
            )
            records.append(name)
            return result.structured_content["data"]

        tools = await client.list_tools()
        assert len(tools.tools) == 45
        ids = []
        for channel, metric in [
            ("tv", "audience"),
            ("radio", "insertions"),
            ("print", "circulation"),
            ("website", "sessions"),
            ("youtube_organic", "views"),
            ("search_ads", "clicks"),
            ("facebook_ads", "conversions"),
        ]:
            content = f"day,{metric},spend\n2026-01-05,100,10\n2026-01-12,110,20\n"
            file = output / (channel + ".csv")
            file.write_text(content, encoding="utf-8")
            payload = dict(
                content_base64=base64.b64encode(file.read_bytes()).decode(),
                format="csv",
                synthetic=True,
                origin="Fabricated " + channel + " export",
            )
            await call("preview_dataset", **payload)
            source = await call("import_source", **payload, confirm=True)
            mapped = await call(
                "map_dataset_schema",
                source_id=source["artifact_id"],
                profile=channel,
                mapping={"day": "date", metric: metric, "spend": "spend"},
                units={metric: "persons" if metric == "audience" else "count", "spend": "BRL"},
                dimensions={
                    "channel": channel,
                    "strategy": "organic" if channel.endswith("_organic") else "paid",
                    "platform": "synthetic " + channel,
                    "region": "BR",
                    "methodology": "synthetic descriptive",
                    "universe": "synthetic adults",
                    "measurement_period": "weekly",
                    "kpi_definition": "supplied channel metric",
                },
            )
            await call("validate_media_dataset", artifact_id=mapped["artifact_id"])
            ids.append(mapped["artifact_id"])
        coverage = await call("validate_crossmedia_dataset", artifact_ids=ids)
        growth = await call(
            "build_growth_dataset",
            artifact_ids=[ids[-1]],
            aggregations={"conversions": "sum", "spend": "sum"},
        )
        eligibility = await call(
            "check_mmm_eligibility", artifact_id=ids[-1], kpi="conversions", media=["spend"]
        )
        assert not eligibility["eligible"]
        diagnostic = await call("create_growth_diagnostic", artifact_id=ids[-1])
        decision = await call(
            "create_growth_decision",
            diagnostic_id=diagnostic["artifact_id"],
            problem="Synthetic spend and outcome changed",
            hypothesis="Audience mix may have changed",
            action="Inspect measurement with human review",
            kpi="conversions",
            guardrails=["spend"],
            baseline="2026-01-05/2026-01-12",
            horizon="2 weeks",
            method="observational",
            risks=["Confounding", "Short history"],
        )
        current = await call(
            "transition_growth_decision",
            artifact_id=decision["artifact_id"],
            state="approved",
            actor="synthetic human reviewer declaration",
            note="Illustrative approval",
        )
        plan = {
            k: "Explicit synthetic example; no real execution"
            for k in [
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
        }
        current = await call(
            "transition_growth_decision",
            artifact_id=current["artifact_id"],
            state="planned",
            actor="synthetic reviewer",
            note="Observational investigation only",
            plan=plan,
        )
        # Imported observations are synthetic; not simulated evidence of efficacy.
        results = await call(
            "import_source",
            content_base64=base64.b64encode(b"date,conversions\n2026-02-01,12\n").decode(),
            format="csv",
            synthetic=True,
            origin="Fabricated experiment result illustration",
            confirm=True,
        )
        current = await call(
            "transition_growth_decision",
            artifact_id=current["artifact_id"],
            state="evaluated",
            actor="synthetic reviewer",
            note="Insufficient evidence of effect; synthetic outcome only",
            results_id=results["artifact_id"],
        )
        current = await call(
            "transition_growth_decision",
            artifact_id=current["artifact_id"],
            state="learned",
            actor="synthetic reviewer",
            note="Reconcile measurement before any causal claim",
        )
    async with Client(params) as restarted:
        restored = await restarted.call_tool(
            "get_growth_artifact", {"request": {"artifact_id": current["artifact_id"]}}
        )
        assert restored.structured_content["data"] == current
    receipt = {
        "synthetic": True,
        "tools_discovered": len(tools.tools),
        "calls": records,
        "restart_persistence": True,
        "coverage": coverage,
        "growth": growth,
        "eligibility": eligibility,
        "diagnostic": diagnostic,
        "decision": current,
    }
    (output / "result.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "report.md").write_text(
        "# Synthetic Growth demonstration\n\nNo causal or commercial result established.\n\n"
        + json.dumps(
            {
                "sources": len(ids),
                "calls": len(records),
                "eligibility": eligibility,
                "learning": current["review_note"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"sources": len(ids), "calls": len(records), "restart_persistence": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    asyncio.run(run(parser.parse_args().output_dir.resolve()))
