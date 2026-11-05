"""Opt-in real engines with coverage of the isolated first-party Python worker.

Run with MMM_TEST_NATIVE=1 after installing native runtimes and coverage there.
The test wrapper changes instrumentation only, preserving the worker environment.
"""

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from test_materialization import normalized_model_data
from test_universal import call

from mmm_intelligence.config import Settings
from mmm_intelligence.integrations import bridge
from mmm_intelligence.service import MMMService


def instrument_native_workers(monkeypatch, backend):
    project = Path(__file__).resolve().parents[1]
    capture = project / "var/coverage/native" / (backend + "-" + uuid4().hex)
    capture.mkdir(parents=True, exist_ok=True)
    original = bridge.run_worker

    def instrumented(args, **options):
        import json
        from uuid import uuid4

        payload = json.loads(Path(args[3]).read_text(encoding="utf-8"))
        if backend == "meta_robyn":
            inputs = project / "var/coverage/r-inputs"
            inputs.mkdir(parents=True, exist_ok=True)
            (inputs / (payload["operation"] + "-" + uuid4().hex + ".json")).write_text(
                json.dumps(payload), encoding="utf-8"
            )
        return original(
            [
                args[0],
                "-m",
                "coverage",
                "run",
                "--branch",
                "--parallel-mode",
                "--rcfile",
                str(project / "pyproject.toml"),
                "--source",
                str(project / "src/mmm_intelligence"),
                "--data-file",
                str(capture / ".coverage"),
                *args[1:],
            ],
            **options,
        )

    monkeypatch.setattr(bridge, "run_worker", instrumented)
    monkeypatch.setenv("MMM_BACKEND_TIMEOUT_SECONDS", "1800")
    return project, capture


def record_native_capture(project, capture, backend):
    from coverage import CoverageData

    files = list(capture.glob(".coverage.*"))
    assert files, "Native worker coverage was not captured in this new run"
    measured = set()
    for path in files:
        data = CoverageData(basename=str(path))
        data.read()
        measured.update(str(f).replace("\\", "/") for f in data.measured_files() if data.arcs(f))
    assert any(f.endswith("integrations/worker.py") for f in measured)
    manifest = {
        "backend": backend,
        "validation_scope": "synthetic_transport_serialization_and_scenario_only",
        "draws": 20,
        "analytical_validation": False,
        "analytical_minimum_draws": None if backend == "meta_robyn" else 1000,
        "source_sha256": {
            str(p.relative_to(project)).replace("\\", "/"): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in sorted((project / "src/mmm_intelligence").rglob("*"))
            if p.is_file() and p.suffix in {".py", ".R", ".js"}
        },
        "coverage_files": [p.name for p in files],
    }
    (capture / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


@pytest.mark.skipif(
    os.environ.get("MMM_TEST_NATIVE") != "1", reason="Actual native runtime provenance required"
)
@pytest.mark.native_transport
@pytest.mark.parametrize("backend", ["google_meridian", "pymc_marketing", "meta_robyn"])
def test_invalid_native_designs_are_rejected_without_sampling(tmp_path, backend):
    from mmm_intelligence.native_recovery import run_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    with MMMService(Settings(tmp_path / "data")) as service:
        result = run_native_study(
            service, backend, NativeRecoveryProtocol(scenarios=["missing_target", "constant_spend"])
        )
        original_files = sorted(service.store.root.glob("datasets/*.json"))
        repeated = run_native_study(
            service, backend, NativeRecoveryProtocol(scenarios=["missing_target", "constant_spend"])
        )
        assert repeated["operational"]["expected_rejections"] == 4
        assert sorted(service.store.root.glob("datasets/*.json")) == original_files
    assert result["operational"]["protocol_executed"]
    assert result["operational"]["expected_rejections"] == 4
    assert {r["code"] for r in result["replications"]} == {
        "DATASET_INVALID",
        "UNIDENTIFIABLE_MEDIA",
    }
    assert all(r["successful"] == 0 for r in result["summaries"])


@pytest.mark.skipif(
    os.environ.get("MMM_TEST_NATIVE") != "1",
    reason="Native runtimes explicitly enabled with MMM_TEST_NATIVE=1",
)
@pytest.mark.native_transport
@pytest.mark.parametrize("backend", ["google_meridian", "pymc_marketing", "meta_robyn"])
def test_prepared_native_train_reload_scenario_with_worker_coverage(tmp_path, monkeypatch, backend):
    project, capture = instrument_native_workers(monkeypatch, backend)
    settings = Settings(tmp_path / "data", max_file_bytes=52428800)
    service = MMMService(settings)
    try:
        data = normalized_model_data(service)
        prepared = call(
            service,
            "prepare_mmm_dataset",
            artifact_id=data["artifact_id"],
            backend=backend,
            kpi="revenue",
            media=["spend_search", "spend_social", "spend_video"],
            controls=["price_index", "promotion"],
            target_type="revenue",
            currency="BRL",
        )
        fitted = call(
            service, "train_backend", **{**prepared["training_request"], "draws": 20, "tune": 20}
        )
        model_id = fitted["model_id"]
        metadata = call(service, "get_backend_model", model_id=model_id)
        assert metadata["native_estimates"], (
            "Native channel parameter stability requires actual estimates"
        )
        if backend == "meta_robyn":
            assert metadata["diagnostics"]["optimization_trace"]
        assert metadata["dataset_sha256"] == prepared["sha256"]
        expected = np.asarray(metadata["test"]["mean"])
        assert np.isfinite(expected).all() and len(expected) > 0
        rejected_study = call(
            service,
            "audit_model",
            model_id=model_id,
            backend=backend,
            scientific={
                "refit": False,
                "collect_native": False,
                "native_monte_carlo": {"scenarios": ["missing_target", "constant_spend"]},
            },
        )
        assert rejected_study["native_monte_carlo"]["operational"]["protocol_executed"]
        assert rejected_study["classifications"]["statistical"]["status"] != "passed_for_protocol"
    finally:
        service.close()
    reloaded = MMMService(settings)
    try:
        actual = call(reloaded, "predict_backend", model_id=model_id)
        np.testing.assert_allclose(actual["prediction"]["mean"], expected, rtol=1e-5, atol=1e-5)
        if backend != "meta_robyn":
            scientific = call(
                reloaded,
                "audit_model",
                model_id=model_id,
                backend=backend,
                scientific={"refit": False},
            )
            assert scientific["scientific_diagnostics"]["available"]
            assert scientific["scientific_diagnostics"]["parameters"]
            assert scientific["posterior_predictive_check"]["scope"] == "observed_outcome"
            assert scientific["classifications"]["statistical"]["status"] != "passed_for_protocol"
            assert scientific["classifications"]["causal"]["status"] == "simulation_only"
        else:
            scientific = call(
                reloaded,
                "audit_model",
                model_id=model_id,
                backend=backend,
                scientific={"refit": True, "collect_native": False},
            )
            assert scientific["stability"]["status"] == "executed"
            assert len(scientific["stability"]["runs"]) == 3
            assert scientific["stability"]["estimate_consistency_available"]
        scenario = call(
            reloaded, "predict_backend", model_id=model_id, media_multiplier={"spend_search": 1.1}
        )
        if backend == "meta_robyn":
            assert scenario["scope"] == "native_channel_response"
            assert set(scenario["responses"]) == {"spend_search"}
            assert np.isfinite(scenario["responses"]["spend_search"]["response_total"]).all()
            reference = call(
                reloaded,
                "predict_backend",
                model_id=model_id,
                media_multiplier={"spend_search": 1.0},
            )
            assert not np.allclose(
                scenario["responses"]["spend_search"]["scenario_mean_response"],
                reference["responses"]["spend_search"]["scenario_mean_response"],
            )
            assert scenario["responses"]["spend_search"]["scenario_mean_spend"] == pytest.approx(
                1.1 * reference["responses"]["spend_search"]["scenario_mean_spend"]
            )
        else:
            assert np.isfinite(scenario["prediction"]["mean"]).all()
            assert len(scenario["prediction"]["mean"]) == len(expected)
            assert not np.allclose(scenario["prediction"]["mean"], expected, rtol=1e-8, atol=1e-8)
        if backend != "meta_robyn":
            invalid = reloaded.call(
                "predict_backend",
                {"model_id": model_id, "media_multiplier": {"unknown_channel": 1.1}},
            )
            assert not invalid.ok and invalid.error.code == "BACKEND_FAILED"
        # Real transport probes, explicitly outside the public analytical protocol.
        # No reduced sampling budget can enter audit_model through its validated schema.
        from mmm_intelligence.native_recovery import run_native_study
        from mmm_intelligence.schemas import NativeRecoveryProtocol

        with pytest.raises(ValueError):
            NativeRecoveryProtocol(draws=20)
        transport = NativeRecoveryProtocol(periods=104).model_copy(
            update={
                "replications": 1,
                "draws": 20,
                "tune": 20,
                "robyn_trials": 1,
                "robyn_iterations": 200,
            }
        )
        recovery = run_native_study(reloaded, backend, transport)
        assert recovery["operational"]["all_executed"], recovery["replications"]
        assert recovery["attempted"] == 2
        assert recovery["acceptance"]["status"] != "passed_for_studied_DGPs"
        assert all(row["successful"] == 1 for row in recovery["summaries"])
        if backend == "meta_robyn":
            assert all(row["interval_coverage"] is None for row in recovery["summaries"])
        else:
            assert all(row["intervals_available"] == 1 for row in recovery["summaries"])
            from mmm_intelligence.schemas import ScientificProtocol
            from mmm_intelligence.validation import assess_refit

            native_refit = reloaded.store.read(
                "backend_models", recovery["replications"][0]["model_id"]
            )
            checked = assess_refit(reloaded, backend, native_refit, ScientificProtocol())
            assert checked["status"] != "passed_for_protocol", (
                "Reduced draws cannot certify a refit"
            )
        if backend == "pymc_marketing":
            dataset = reloaded.load_dataset(prepared["dataset_id"])
            last = dataset["rows"][-1]
            projected = call(
                reloaded,
                "forecast_model",
                backend=backend,
                model_id=model_id,
                media_plan={
                    channel: [1000.0, 1100.0, 900.0, 1000.0]
                    for channel in prepared["training_request"]["media_columns"]
                },
                future_controls={
                    column: [last[column]] * 4
                    for column in prepared["training_request"]["control_columns"]
                },
            )
            assert len(projected["prediction"]["mean"]) == 4
            assert np.isfinite(projected["prediction"]["mean"]).all()
            assert projected["scope"] == "future_conditional_projection"
            assert projected["prediction"]["dates"][0] > last["date"]
    finally:
        reloaded.close()
    record_native_capture(project, capture, backend)


@pytest.mark.skipif(
    os.environ.get("MMM_TEST_NATIVE") != "1", reason="Actual native runtimes required"
)
@pytest.mark.native_transport
@pytest.mark.parametrize("backend", ["google_meridian", "pymc_marketing"])
def test_real_legacy_baseline_train_restore_and_supported_forecast(tmp_path, monkeypatch, backend):
    project, capture = instrument_native_workers(monkeypatch, backend)
    with MMMService(Settings(tmp_path / "data", max_file_bytes=104857600)) as service:
        call(service, "generate_demo_dataset", dataset_id="legacy-native", periods=104)
        if backend == "pymc_marketing":
            from mmm_intelligence.refits import fit_or_reuse
            from mmm_intelligence.schemas import BackendRequest

            spec = BackendRequest(
                dataset_id="legacy-native",
                backend=backend,
                baseline="legacy",
                draws=20,
                tune=20,
                chains=2,
                control_columns=[],
            )
            fitted, reused = fit_or_reuse(
                service,
                backend,
                service.load_dataset("legacy-native"),
                spec.model_dump(mode="json"),
            )
            assert not reused
        else:
            fitted = call(
                service,
                "train_backend",
                dataset_id="legacy-native",
                backend=backend,
                baseline="legacy",
                draws=20,
                tune=20,
                chains=2,
            )
        model_id = fitted["model_id"]
        stored = service.store.read("backend_models", model_id)
        assert stored["request"]["baseline"] == "legacy"
        assert stored["baseline_policy"] is None
        if backend == "pymc_marketing":
            from mmm_intelligence.schemas import ScientificProtocol
            from mmm_intelligence.validation import stability_study

            with pytest.raises(ValueError):
                ScientificProtocol(seeds=[42])
            # One cached reduced-draw transport probe, never independent refit evidence.
            probe = ScientificProtocol().model_copy(update={"seeds": [42]})
            checked = stability_study(service, stored, stored["dataset"], backend, probe)
            assert checked["status"] == "incomplete" and len(checked["runs"]) == 1
            assert checked["runs"][0]["reused"]
            assert checked["runs"][0]["numerical_assessment"]["status"] != "passed_for_protocol"
        prediction = call(service, "predict_backend", model_id=model_id)
        np.testing.assert_allclose(
            prediction["prediction"]["mean"], stored["test"]["mean"], rtol=1e-5, atol=1e-5
        )
        if backend == "pymc_marketing":
            projected = call(
                service,
                "forecast_model",
                backend=backend,
                model_id=model_id,
                media_plan={c: [1000.0] * 4 for c in stored["request"]["media_columns"]},
                future_controls={
                    c: [stored["dataset"]["rows"][-1][c]] * 4
                    for c in stored["request"]["control_columns"]
                },
            )
            assert np.isfinite(projected["prediction"]["mean"]).all()
            assert len(projected["prediction"]["mean"]) == 4
    record_native_capture(project, capture, backend)
