"""Reproduce scientific reports over the official MCP stdio transport.

An exit code of zero means the execution/recording succeeded. Scientific failures
or inconclusive results are preserved in the report and never converted to passes.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = ("ridge", "google_meridian", "pymc_marketing", "meta_robyn")
SCENARIOS = [
    "well_specified",
    "null_effect",
    "collinear",
    "omitted_confounder",
    "tracking_break",
    "heavy_tailed",
    "misspecified_adstock",
    "weak_signal",
    "missing_target",
    "constant_spend",
]


def source_hashes():
    sources = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "src/mmm_intelligence").rglob("*"))
        if p.suffix in {".py", ".R", ".js"}
    }
    sources["examples/scientific_protocol.py"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    return sources


def audit_timeout_seconds(backend, native_replications, skip_refits):
    """Bound each tool request for all sequential native workers it may invoke."""
    refits = 0 if skip_refits else 3  # Two seeds and the declared control omission.
    recovery_fits = native_replications * 2  # Prespecified well-specified/null DGPs.
    calls = {
        "ridge": 1,
        "google_meridian": 1 + 2 * refits + 3 * recovery_fits,
        "pymc_marketing": 1 + 2 * refits + 3 * recovery_fits,
        "meta_robyn": max(1, refits + 2 * recovery_fits),
    }
    return 3800 * (max(calls.values()) if backend == "all" else calls[backend])


def reuse_models(options, output):
    """Operator-only reuse of verified synthetic state; never a tool path input."""
    from mmm_intelligence.config import Settings
    from mmm_intelligence.datasets import generate
    from mmm_intelligence.schemas import GenerateRequest
    from mmm_intelligence.storage import ArtifactStore, digest

    if options.reuse_store is None:
        return []
    source = options.reuse_store.resolve()
    if not all(
        (source / kind).is_dir()
        for kind in ("datasets", "models", "backend_models", "reports", "dashboards", "logs")
    ):
        raise ValueError("Reuse requires a complete existing artifact store")
    store = ArtifactStore(Settings(source, max_file_bytes=104857600))
    destination = ArtifactStore(Settings(output / "data", max_file_bytes=104857600))
    dataset = store.read("datasets", "scientific-data")
    expected = generate(GenerateRequest(periods=156, seed=options.seed))
    if digest(dataset) != digest(expected) or dataset.get("synthetic") is not True:
        raise ValueError("Reuse dataset differs from the declared synthetic generator and seed")
    destination.write("datasets", "scientific-data", dataset)
    reused = []
    for backend in BACKENDS if options.backend == "all" else [options.backend]:
        kind = "models" if backend == "ridge" else "backend_models"
        model_id = "scientific-" + backend
        if not store.path(kind, model_id).is_file():
            continue
        model = store.read(kind, model_id)
        expected_request = (
            {"bootstrap_seed": options.seed, "bootstrap_samples": 40}
            if backend == "ridge"
            else {
                "seed": options.seed,
                "draws": 20 if options.transport_smoke else options.draws,
                "tune": 20 if options.transport_smoke else options.tune,
                "chains": 2 if options.transport_smoke else options.chains,
            }
        )
        if (
            model.get("synthetic") is not True
            or model["dataset_sha256"] != digest(dataset)
            or any(model["request"].get(k) != v for k, v in expected_request.items())
        ):
            raise ValueError("Reuse model has incompatible data, seed or sampling configuration")
        destination.write(kind, model_id, model)
        reused.append(backend)
    return reused


def bounded_integer(value, lower, upper):
    parsed = int(value)
    if not lower <= parsed <= upper:
        raise argparse.ArgumentTypeError(f"Use an integer between {lower} and {upper}")
    return parsed


async def run(options):
    output = options.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = source_hashes()
    reused = reuse_models(options, output)
    env = {
        **os.environ,
        "MMM_DATA_DIR": str(output / "data"),
        "MMM_TRANSPORT": "stdio",
        "MMM_ALLOW_REAL_DATA": "false",
        "MMM_MAX_FILE_BYTES": "104857600",
        "MMM_BACKEND_TIMEOUT_SECONDS": "3600",
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mmm_intelligence.server"], cwd=ROOT, env=env
    )
    receipt = {
        "schema_version": "scientific-run-v1",
        "synthetic": True,
        "transport": "official_sdk_stdio",
        "profiles": {},
        "source_sha256": sources,
        "scientific_approval": False,
        "scope": "Reproducible execution; inspect independent classifications",
        "transport_smoke": options.transport_smoke,
        "reused_models": reused,
    }
    # One audit may run several sequential workers. Each remains independently bounded.
    audit_timeout = audit_timeout_seconds(
        options.backend, options.native_replications, options.skip_refits
    )
    async with Client(params, read_timeout_seconds=audit_timeout) as client:

        async def call(name, **request):
            result = await client.call_tool(name, {"request": request})
            if result.is_error or not result.structured_content.get("ok"):
                raise RuntimeError(f"{name}: {result.structured_content}")
            return result.structured_content["data"]

        if options.reuse_store is None:
            await call(
                "generate_demo_dataset",
                dataset_id="scientific-data",
                periods=156,
                seed=options.seed,
            )
        for backend in BACKENDS if options.backend == "all" else [options.backend]:
            model_id = "scientific-" + backend
            if backend in reused:
                pass  # Actual restoration and scientific diagnostics are still executed below.
            elif backend == "ridge":
                await call(
                    "train_mmm",
                    dataset_id="scientific-data",
                    model_id=model_id,
                    bootstrap_samples=40,
                    bootstrap_seed=options.seed,
                )
            else:
                request = {
                    "dataset_id": "scientific-data",
                    "model_id": model_id,
                    "backend": backend,
                    "draws": 20 if options.transport_smoke else options.draws,
                    "tune": 20 if options.transport_smoke else options.tune,
                    "chains": 2 if options.transport_smoke else options.chains,
                    "seed": options.seed,
                }
                if backend == "meta_robyn":
                    request.update(
                        robyn_trials=1 if options.transport_smoke else 5,
                        robyn_iterations=200 if options.transport_smoke else 2000,
                    )
                await call("train_backend", **request)
            scientific = {
                "refit": not options.skip_refits,
                "seeds": [(options.seed + 17) % (2**31 - 1), (options.seed + 29) % (2**31 - 1)],
            }
            if options.refit_draws is not None and backend in {"google_meridian", "pymc_marketing"}:
                scientific["refit_draws"] = options.refit_draws
            if backend == "ridge":
                scientific["monte_carlo"] = {
                    "replications": options.replications,
                    "seed": options.seed,
                    "bootstrap_samples": 40,
                    "scenarios": SCENARIOS,
                }
            elif options.native_replications:
                scientific["native_monte_carlo"] = {
                    "replications": options.native_replications,
                    "seed": options.seed,
                    "draws": options.draws,
                    "tune": options.tune,
                    "scenarios": ["well_specified", "null_effect"],
                }
            report = await call(
                "audit_model", model_id=model_id, backend=backend, scientific=scientific
            )
            exported = await call(
                "export_analysis",
                model_id=model_id,
                backend=backend,
                format="markdown",
                scientific_report_id=report["artifact_id"],
            )
            (output / (backend + ".md")).write_text(exported["content"], encoding="utf-8")
            receipt["profiles"][backend] = report
            # Preserve completed engine evidence even if a later runtime fails.
            (output / "partial.json").write_text(
                json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8"
            )
            print(
                json.dumps({"backend": backend, "classifications": report["classifications"]}),
                flush=True,
            )
    receipt["source_unchanged"] = sources == source_hashes()
    if not receipt["source_unchanged"]:
        raise RuntimeError("Production source changed during the run; do not accept this capture")
    (output / "result.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=[*BACKENDS, "all"], default="ridge")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reuse-store", type=Path)
    parser.add_argument("--replications", type=lambda v: bounded_integer(v, 2, 250), default=20)
    parser.add_argument(
        "--native-replications",
        type=lambda v: bounded_integer(v, 2, 100),
        default=0,
        help="Actual isolated known-truth fits per core scenario; default disabled, never a reduced-draw substitute",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--draws", type=lambda v: bounded_integer(v, 1000, 8000), default=1000)
    parser.add_argument("--tune", type=lambda v: bounded_integer(v, 1000, 8000), default=1000)
    parser.add_argument("--chains", type=int, choices=[4], default=4)
    parser.add_argument("--transport-smoke", action="store_true")
    parser.add_argument("--skip-refits", action="store_true")
    parser.add_argument("--refit-draws", type=lambda v: bounded_integer(v, 1000, 8000))
    asyncio.run(run(parser.parse_args()))
