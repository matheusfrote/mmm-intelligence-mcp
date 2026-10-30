"""Remaining numerical and authorization behaviors have observable consequences."""

import runpy
import tempfile
from pathlib import Path

import numpy as np
import pytest

from mmm_intelligence import server
from mmm_intelligence.datasets import generate, validate
from mmm_intelligence.errors import MMMError
from mmm_intelligence.integrations import bridge
from mmm_intelligence.modeling import train
from mmm_intelligence.schemas import ForecastRequest, GenerateRequest, TrainRequest
from mmm_intelligence.web_app import local_dashboard_request


def test_negative_predictions_survive_training_and_projection(service, dataset):
    for i, row in enumerate(dataset["rows"]):
        row["revenue"] = max(0.0, 100 - i * 2.0)
    service.store.write("datasets", "decline", dataset)
    fitted = service.call("train_mmm", {"dataset_id": "decline", "model_id": "decline"})
    assert fitted.ok and any(w.startswith("NEGATIVE_PREDICTIONS") for w in fitted.warnings)
    request = ForecastRequest(
        model_id="decline",
        media_plan={c: [1.0] for c in ["spend_search", "spend_social", "spend_video"]},
        future_controls={"price_index": [1.0], "promotion": [0.0]},
    )
    forecast = service.forecast_model(request)
    assert min(forecast["prediction"]["mean"]) < 0
    assert any(w.startswith("NEGATIVE_PREDICTIONS") for w in forecast["warnings"])


def test_external_correlation_nonfinite_diagnostic_is_unavailable(dataset, monkeypatch):
    request = TrainRequest(dataset_id="demo")
    monkeypatch.setattr(
        np, "corrcoef", lambda *args, **kwargs: np.array([[1.0, np.nan], [np.nan, 1.0]])
    )
    model = train(dataset, request, "fit", validate(dataset, request, 1000))
    assert model["diagnostics"]["train_residual_lag1"] is None


def test_bootstrap_block_cannot_exceed_training_residuals():
    data = generate(GenerateRequest(periods=52))
    request = TrainRequest(
        dataset_id="demo", bootstrap_samples=20, bootstrap_block_size=26, test_fraction=0.4
    )
    with pytest.raises(MMMError) as caught:
        train(data, request, "fit", validate(data, request, 1000))
    assert caught.value.code == "INVALID_BLOCK_SIZE"


def test_crossmedia_equal_known_context_needs_no_incompatibility(service):
    from test_materialization import normalized_model_data
    from test_universal import call

    data = normalized_model_data(service)
    data["dimensions"].update(
        region="BR", universe="synthetic", methodology="fixture", measurement_period="week"
    )
    stored = service._growth_save("normalized", data)
    report = call(service, "validate_crossmedia_dataset", artifact_ids=[stored["artifact_id"]])
    assert report["incompatibilities"] == []


def test_dashboard_requires_actual_loopback_peer():
    assert (
        local_dashboard_request(
            {"method": "POST", "scheme": "http", "client": ("192.0.2.1", 0), "headers": []}
        )
        is False
    )


def test_robyn_refuses_os_temp_root_with_spaces(service, tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "executable", lambda name: Path(__import__("sys").executable))
    original = tempfile.TemporaryDirectory
    directory = tmp_path / "has spaces"
    directory.mkdir()

    def temp(*args, **kwargs):
        if kwargs.get("prefix") == "mmm-r-":
            kwargs["dir"] = directory
        return original(*args, **kwargs)

    monkeypatch.setattr(tempfile, "TemporaryDirectory", temp)
    with pytest.raises(MMMError) as caught:
        bridge.execute(service.store, "meta_robyn", {"synthetic": True})
    assert caught.value.code == "R_TEMP_PATH"
    assert list(directory.iterdir()) == []


def test_top_level_entrypoints_import_and_execute_only_declared_main(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    calls = []
    monkeypatch.setattr(server, "main", lambda: calls.append("stdio"))
    monkeypatch.setattr(__import__("sys"), "path", __import__("sys").path.copy())
    monkeypatch.setenv("MMM_DATA_DIR", str(root / "var/test-entry-unused"))
    monkeypatch.setenv("MMM_TRANSPORT", "unsupported")
    runpy.run_path(str(root / "server.py"), run_name="server")
    assert calls == []
    runpy.run_path(str(root / "server.py"), run_name="__main__")
    assert calls == ["stdio"]
    launch = root / "plugins/mmm-intelligence-local/launch.py"
    runpy.run_path(str(launch), run_name="entry_import")
    runpy.run_path(str(launch), run_name="__main__")
    assert calls == ["stdio", "stdio"]
    original_is_dir = Path.is_dir
    monkeypatch.setattr(
        Path, "is_dir", lambda p: True if p == launch.parent / "server" else original_is_dir(p)
    )
    runpy.run_path(str(launch), run_name="entry_bundled_path_policy")
    assert __import__("sys").path[0] == str(launch.parent / "server")


def test_constant_control_and_definite_future_extrapolation(service, dataset):
    from mmm_intelligence.forecasting import prepare

    for row in dataset["rows"]:
        row["promotion"] = 0
    request = TrainRequest(dataset_id="constant")
    report = validate(dataset, request, 1000)
    model = train(dataset, request, "constant", report)
    assert any(w.startswith("RANK_WARNING") for w in model["warnings"])
    plan = ForecastRequest(
        model_id="constant",
        media_plan={c: [1e8] for c in request.media_columns},
        future_controls={c: [1.0] for c in request.control_columns},
    )
    _, assumptions = prepare(model, plan)
    assert sum(w.startswith("EXTRAPOLATION") for w in assumptions["warnings"]) == 3


def test_unexpected_failure_and_host_generation_cap_are_publicly_contained(
    service, monkeypatch, tmp_path
):
    from mmm_intelligence.config import Settings
    from mmm_intelligence.service import MMMService

    limited = MMMService(Settings(tmp_path / "limited", max_rows=52))
    try:
        answer = limited.call("generate_demo_dataset", {"periods": 156})
        assert not answer.ok and answer.error.code == "ROW_LIMIT"
    finally:
        limited.close()

    def fault(req):
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(service, "generate_demo_dataset", fault)
    answer = service.call("generate_demo_dataset", {})
    assert answer.error.code == "INTERNAL_ERROR" and "private" not in answer.error.message


def test_csv_full_validation_and_unknown_spend_currency(service):
    import csv
    import io

    from test_joins import normalized

    from mmm_intelligence.media_validation import validate_media

    data = generate(GenerateRequest(periods=52))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(data["rows"][0]))
    writer.writeheader()
    # The parser accepts a short series; full model validation requires 52 periods.
    for row in data["rows"][:51]:
        writer.writerow(row)
    answer = service.call(
        "import_csv",
        {
            "csv_text": output.getvalue(),
            "synthetic": True,
            "authorization_reference": "synthetic-test",
        },
    )
    assert not answer.ok and answer.error.code == "DATASET_INVALID"
    media = normalized(service, "date,spend\n2026-01-01,10\n")
    media["units"]["spend"] = "JPY"
    assert "Currency must be explicitly reviewed" in validate_media(media)["warnings"]


@pytest.mark.parametrize("users", [{}, [], {str(i): {} for i in range(101)}])
def test_http_user_count_is_bounded(users):
    from mmm_intelligence.http_transport import validate_users

    with pytest.raises(ValueError, match="1..100"):
        validate_users(users)


def test_dashboard_refuses_dataset_replacement_after_training(service, trained):
    from mmm_intelligence.storage import canonical, digest

    path = service.store.path("datasets", "demo")
    data = service.load_dataset("demo")
    data["rows"][0]["revenue"] += 1
    path.write_bytes(
        canonical(
            {"schema_version": 1, "kind": "datasets", "sha256": digest(data), "payload": data}
        )
    )
    result = service.call("render_dashboard", {"model_id": "fit"})
    assert not result.ok and result.error.code == "LINEAGE_MISMATCH"
    assert list((service.store.root / "dashboards").glob("*.json")) == []
