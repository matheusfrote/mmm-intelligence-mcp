"""Failure and compatibility contracts of the original local MMM service."""

import io
import json
import os
import subprocess
import sys

import pytest
from test_canonical_boundaries import native
from test_experiment_protocol import fixture_rows, protocol, result
from test_growth_completion import rejected
from test_materialization import normalized_model_data

from mmm_intelligence.canonical import bundle
from mmm_intelligence.config import Settings
from mmm_intelligence.errors import MMMError
from mmm_intelligence.experiments import plan_experiment
from mmm_intelligence.file_readers import reject_external_xml
from mmm_intelligence.forecasting import prepare
from mmm_intelligence.http_transport import LOCAL_DASHBOARD, TenantRouter, principal
from mmm_intelligence.integrations import bridge
from mmm_intelligence.joins import prepare as prepare_join
from mmm_intelligence.materialization import materialize
from mmm_intelligence.quality import assess
from mmm_intelligence.resources import run_worker
from mmm_intelligence.schemas import AnalysisRequest, ForecastRequest, TrainRequest
from mmm_intelligence.service import COMPUTE_GATE, MMMService
from mmm_intelligence.storage import ArtifactStore
from mmm_intelligence.universal_schemas import PreparationRequest
from mmm_intelligence.web_app import local_dashboard_request


def test_xml_external_resource_policy_is_always_refused():
    for url in ["https://example.invalid/schema", "file:///private/file"]:
        with pytest.raises(ValueError, match="External schema resources"):
            reject_external_xml(url, None, None)


def test_real_data_preview_requires_reference_even_when_host_allows(tmp_path):
    service = MMMService(Settings(tmp_path, allow_real_data=True))
    try:
        rejected(
            service,
            "preview_dataset",
            "AUTHORIZATION_REQUIRED",
            content_base64="eAoxCg==",
            format="csv",
            synthetic=False,
            origin="test, no real data",
        )
    finally:
        service.close()


def test_service_never_initializes_log_through_hard_link(tmp_path):
    store = ArtifactStore(Settings(tmp_path))
    original = tmp_path / "original.log"
    original.write_text("preserved")
    os.link(original, store.root / "logs/server.log")
    with pytest.raises(MMMError, match="hard link"):
        MMMService(Settings(tmp_path))
    assert original.read_text() == "preserved"


def test_busy_gate_releases_and_internal_result_errors_are_structured(service, monkeypatch):
    assert COMPUTE_GATE.acquire(blocking=False)
    try:
        rejected(service, "train_mmm", "BUSY", dataset_id="missing")
    finally:
        COMPUTE_GATE.release()
    # Fault at result boundary: Pydantic must contain an invalid internal result.
    monkeypatch.setattr(service, "generate_demo_dataset", lambda req: {"warnings": [None]})
    rejected(service, "generate_demo_dataset", "INTERNAL_ERROR")

    def disk_failure(req):
        raise OSError("private disk path")

    monkeypatch.setattr(service, "generate_demo_dataset", disk_failure)
    rejected(service, "generate_demo_dataset", "STORAGE_ERROR")


def test_native_unavailable_operation_bad_lineage_and_invalid_training(service, dataset):
    rejected(
        service,
        "forecast_model",
        "OPERATION_UNAVAILABLE",
        model_id="missing",
        backend="google_meridian",
        media_plan={"spend_search": [1.0]},
        future_controls={},
    )
    model = native(dataset)
    service.store.write("backend_models", "native", {**model, "dataset_sha256": "incorrect"})
    rejected(
        service,
        "forecast_model",
        "LINEAGE_MISMATCH",
        model_id="native",
        backend="pymc_marketing",
        media_plan={c: [1.0] for c in model["request"]["media_columns"]},
        future_controls={c: [1.0] for c in model["request"]["control_columns"]},
    )
    dataset["rows"][0]["revenue"] = -1
    service.store.write("datasets", "invalid", dataset)
    rejected(
        service, "train_backend", "DATASET_INVALID", dataset_id="invalid", backend="pymc_marketing"
    )


def test_canonical_robyn_uses_explicit_training_dates(dataset):
    model = native(dataset)
    model.update(
        backend="meta_robyn",
        temporal_split={"train_dates": [r["date"] for r in dataset["rows"][:124]]},
    )
    analysis = bundle(model, dataset, AnalysisRequest(model_id="native", backend="meta_robyn"))
    assert analysis["training_dates"] == model["temporal_split"]["train_dates"]


def test_future_plan_inside_support_has_no_extrapolation_warning(trained):
    request = ForecastRequest(
        model_id="fit",
        media_plan={
            c: [(v["training_spend_min"] + v["training_spend_max"]) / 2]
            for c, v in trained["media_parameters"].items()
        },
        future_controls={c: [v] for c, v in trained["state"]["last_controls"].items()},
    )
    _, assumptions = prepare(trained, request)
    assert not any(w.startswith("EXTRAPOLATION") for w in assumptions["warnings"])


def test_daily_join_alignment_does_not_shift_dates():
    assert prepare_join({"rows": [{"date": "2026-01-07", "spend": 2}]}, ["date"], {}, "daily") == [
        {"date": "2026-01-07", "spend": 2}
    ]


def test_materialization_revenue_currency_has_specific_error(service):
    data = normalized_model_data(service)
    data["units"]["revenue"] = "USD"
    with pytest.raises(MMMError) as caught:
        materialize(
            data,
            PreparationRequest(
                artifact_id=data["artifact_id"],
                kpi="revenue",
                media=["spend_search"],
                controls=["price_index"],
                target_type="revenue",
                currency="BRL",
            ),
            1000,
        )
    assert caught.value.code == "KPI_UNIT"


def test_missing_quality_values_short_history_and_audience_context(dataset, service):
    dataset["rows"][0]["spend_search"] = None
    assert not assess(dataset, TrainRequest(dataset_id="demo"), 1000)["valid"]
    dataset["rows"] = dataset["rows"][:20]
    assert not assess(dataset, TrainRequest(dataset_id="demo"), 1000)["valid"]
    data = normalized_model_data(service)
    data["rows"][0]["audience"] = 100
    data["profile"]["name"] = "tv"
    data["dimensions"].update(
        universe="persons", methodology="synthetic", region="BR", measurement_period="week"
    )
    from mmm_intelligence.media_validation import eligibility, validate_media
    from mmm_intelligence.universal_schemas import EligibilityRequest

    assert not any("Audience definitions missing" in w for w in validate_media(data)["warnings"])
    data["profile"]["name"] = "tiktok_organic"
    assert validate_media(data)["dataset_applicability"]["state"] == "not_applicable"
    data["profile"]["name"] = "model_frame"
    request = EligibilityRequest(
        artifact_id=data["artifact_id"],
        backend="meta_robyn",
        kpi="revenue",
        media=["spend_search"],
        controls=["price_index"],
    )
    assert any("Robyn adapter" in r for r in eligibility(data, request)["blocking_reasons"])


def test_experiment_overflow_and_decreasing_guardrail():
    with pytest.raises(MMMError, match="sample size"):
        plan_experiment(protocol(minimum_effect=1e-155))
    rows = fixture_rows()
    for row in rows:
        row["refunds"] = int(row["arm"] == "C")
    analysis = result(
        rows,
        guardrail_specs={
            "refunds": {
                "outcome_type": "binary",
                "direction": "decrease",
                "max_adverse_change": 0.1,
            }
        },
    )
    assert analysis["guardrails"]["refunds"]["status"] == "harm_detected"
    rows[0]["refunds"] = 2
    with pytest.raises(MMMError):
        result(rows)


def test_resource_policy_rejects_unbounded_worker_before_spawning(tmp_path, monkeypatch):
    monkeypatch.setenv("MMM_WORKER_CPU_PERCENT", "101")
    with pytest.raises(ValueError, match="Invalid worker"):
        run_worker(
            [sys.executable, "-c", "raise SystemExit(99)"],
            timeout=1,
            env=None,
            cwd=tmp_path,
            stdout=io.BytesIO(),
        )


def test_router_local_dataset_resource_and_direct_invalid_method(tmp_path):
    router = TenantRouter(Settings(tmp_path), {})
    token = principal.set(LOCAL_DASHBOARD)
    try:
        assert router.call("generate_demo_dataset", {"dataset_id": "local"}).ok
        assert router.load_dataset("local")["synthetic"] is True
    finally:
        principal.reset(token)
        router.close()
    assert local_dashboard_request({"method": "GET", "scheme": "http"}) is False
    assert (
        local_dashboard_request(
            {"method": "POST", "scheme": "http", "client": ("not-ip", 0), "headers": []}
        )
        is False
    )


@pytest.mark.parametrize("failure", ["missing", "nonzero", "oversized", "timeout"])
def test_bridge_refuses_missing_nonzero_and_timed_out_results(service, monkeypatch, failure):
    monkeypatch.setattr(
        bridge, "executable", lambda backend: __import__("pathlib").Path(sys.executable)
    )

    def failed_worker(args, **options):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 10)
        if failure != "missing":
            __import__("pathlib").Path(args[4]).write_text(
                "x" * (service.settings.max_file_bytes + 1)
                if failure == "oversized"
                else json.dumps({"ok": False, "message": "private"})
            )
        return subprocess.CompletedProcess(args, 1)

    monkeypatch.setattr(bridge, "run_worker", failed_worker)
    with pytest.raises(MMMError) as caught:
        bridge.execute(service.store, "pymc_marketing", {"synthetic": True})
    assert caught.value.code == ("BACKEND_TIMEOUT" if failure == "timeout" else "BACKEND_FAILED")
    assert not list((service.store.root / "jobs").iterdir())
