import copy
import hashlib

import numpy as np
import pytest
from starlette.testclient import TestClient

from mmm_intelligence.config import Settings
from mmm_intelligence.http_transport import create_http_app, validate_users
from mmm_intelligence.optimization import optimize
from mmm_intelligence.schemas import OptimizeRequest, SimulateRequest
from mmm_intelligence.simulation import simulate


def test_import_enforces_origin_schema_and_no_overwrite(service, dataset):
    req = {
        "dataset_id": "imported",
        "rows": dataset["rows"],
        "synthetic": True,
        "authorization_reference": "synthetic-software-test",
    }
    result = service.call("import_dataset", req)
    assert result.ok and result.data["validation"]["valid"]
    assert service.call("import_dataset", req).error.code == "ALREADY_EXISTS"
    req.update(dataset_id="real", synthetic=False)
    assert service.call("import_dataset", req).error.code == "REAL_DATA_DISABLED"
    req.update(dataset_id="invalid", synthetic=True)
    req["rows"][0]["date"] = req["rows"][1]["date"]
    assert service.call("import_dataset", req).error.code == "DATASET_INVALID"


def test_import_invalid_column_spec_is_an_input_error(service, dataset):
    result = service.call(
        "import_dataset",
        {
            "rows": dataset["rows"],
            "synthetic": True,
            "authorization_reference": "synthetic-test",
            "media_columns": [],
        },
    )
    assert not result.ok and result.error.code == "INPUT_INVALID"


def test_tuning_invalid_grid_is_an_input_error(service):
    result = service.call("tune_mmm", {"dataset_id": "unused", "decays": [1.0]})
    assert not result.ok and result.error.code == "INPUT_INVALID"


def test_optimizer_bounds_and_independent_grid(trained):
    total = 60000.0
    req = OptimizeRequest(
        model_id="fit",
        horizon=6,
        total_budget=total,
        lower={"spend_search": 5000.0},
        upper={"spend_search": 35000.0},
    )
    out = optimize(trained, req)
    assert sum(out["optimal_spend"].values()) == pytest.approx(total, abs=1e-6)
    assert 5000 - 1e-6 <= out["optimal_spend"]["spend_search"] <= 35000 + 1e-6
    best = -np.inf
    for search in np.linspace(5000, 35000, 7):
        for social in np.linspace(0, total - search, 7):
            allocation = {
                "spend_search": search / total,
                "spend_social": social / total,
                "spend_video": (total - search - social) / total,
            }
            point = simulate(
                trained,
                SimulateRequest(
                    model_id="fit", horizon=6, total_budget=total, allocation=allocation
                ),
            )
            best = max(best, point["predicted_total"])
    assert out["scenario"]["predicted_total"] >= best - 1e-5


def test_optimizer_infeasible_and_zero(service, trained):
    assert (
        service.call(
            "optimize_budget",
            {"model_id": "fit", "total_budget": 100.0, "lower": {"spend_search": 101.0}},
        ).error.code
        == "INFEASIBLE_BUDGET"
    )
    result = service.call("optimize_budget", {"model_id": "fit", "total_budget": 0.0})
    assert result.ok and sum(result.data["optimal_spend"].values()) == 0


def test_bootstrap_reproducibility_intervals_and_paired_identity(service, trained):
    req = {"dataset_id": "demo", "model_id": "uncertain", "bootstrap_samples": 30}
    assert service.call("train_mmm", req).ok
    a = service.store.read("models", "uncertain")
    req["model_id"] = "repeat"
    assert service.call("train_mmm", req).ok
    b = service.store.read("models", "repeat")
    np.testing.assert_allclose(a["coefficient_draws"], b["coefficient_draws"])
    ref = a["state"]["reference_spend_per_period"]
    total = sum(ref.values())
    result = simulate(
        a,
        SimulateRequest(
            model_id="uncertain",
            horizon=4,
            total_budget=total * 4,
            allocation={c: v / total for c, v in ref.items()},
        ),
    )
    low, high = result["uncertainty"]["total_mean_interval"]
    assert np.isfinite([low, high]).all() and low <= high
    np.testing.assert_allclose(result["uncertainty"]["difference_mean_interval"], [0, 0], atol=1e-8)


def test_tuning_does_not_select_on_outer_future(service, dataset):
    service.store.write("datasets", "original", dataset)
    changed = copy.deepcopy(dataset)
    for row in changed["rows"][-32:]:
        row["revenue"] *= 100
        row["spend_search"] *= 100
    service.store.write("datasets", "future", changed)
    common = {"decays": [0.2, 0.8], "multipliers": [0.5, 2.0]}
    a = service.call("tune_mmm", {"dataset_id": "original", "model_id": "tune-a", **common})
    b = service.call("tune_mmm", {"dataset_id": "future", "model_id": "tune-b", **common})
    assert a.ok and b.ok
    assert a.data["shape_selection"] == b.data["shape_selection"]
    assert a.data["shape_selection"]["outer_test_used"] is False


@pytest.mark.parametrize("corruption", ["negative", "missing", "duplicate", "irregular"])
def test_tuning_rejects_invalid_outer_holdout_without_persisting(service, dataset, corruption):
    if corruption == "negative":
        dataset["rows"][-1]["revenue"] = -1.0
    elif corruption == "missing":
        dataset["rows"][-1]["revenue"] = None
    elif corruption == "duplicate":
        dataset["rows"][-1]["date"] = dataset["rows"][-2]["date"]
    else:
        from datetime import date, timedelta

        last = date.fromisoformat(dataset["rows"][-1]["date"])
        dataset["rows"][-1]["date"] = (last + timedelta(days=1)).isoformat()
    service.store.write("datasets", "bad-holdout", dataset)
    result = service.call(
        "tune_mmm",
        {
            "dataset_id": "bad-holdout",
            "model_id": "rejected",
            "decays": [0.5],
            "multipliers": [1.0],
        },
    )
    assert not result.ok
    assert result.error.code == "DATASET_INVALID"
    assert not service.store.path("models", "rejected").exists()


def test_calibration_uses_declared_synthetic_experiment(service, trained):
    assert service.call(
        "train_mmm", {"dataset_id": "demo", "model_id": "calibration", "bootstrap_samples": 40}
    ).ok
    req = {
        "model_id": "calibration",
        "experiment_id": "synthetic",
        "synthetic": True,
        "channel": "spend_search",
        "treatment_spend": 2000.0,
        "control_spend": 500.0,
        "lift_mean": 2000.0,
        "lift_sd": 500.0,
    }
    result = service.call("calibrate_experiment", req)
    assert result.ok and result.data["model_changed"] is False
    assert sum(result.data["weights"]) == pytest.approx(1)
    req["synthetic"] = False
    assert service.call("calibrate_experiment", req).error.code == "REAL_DATA_DISABLED"


def test_calibration_extreme_precision_fails_without_nonfinite_success(service, trained):
    assert service.call(
        "train_mmm", {"dataset_id": "demo", "model_id": "extreme", "bootstrap_samples": 20}
    ).ok
    result = service.call(
        "calibrate_experiment",
        {
            "model_id": "extreme",
            "experiment_id": "extreme-synthetic",
            "synthetic": True,
            "channel": "spend_search",
            "treatment_spend": 2000.0,
            "control_spend": 500.0,
            "lift_mean": 1e12,
            "lift_sd": 1e-300,
        },
    )
    assert not result.ok and result.error.code == "CALIBRATION_NUMERIC_RANGE"


def test_report_and_dashboard_are_real_immutable_artifacts(service, trained):
    report = service.call("generate_report", {"model_id": "fit", "artifact_id": "report"})
    dashboard = service.call("render_dashboard", {"model_id": "fit", "artifact_id": "dashboard"})
    assert report.ok and dashboard.ok
    assert f"{trained['metrics']['test']['mae']:.6f}" in report.data["content"]
    assert "No external" not in dashboard.data["content"]
    assert "<svg" in dashboard.data["content"] and "addEventListener" in dashboard.data["content"]
    assert '<script src="http' not in dashboard.data["content"]
    assert service.store.read("reports", "report")["content"] == report.data["content"]
    assert (
        service.call("generate_report", {"model_id": "fit", "artifact_id": "report"}).error.code
        == "ALREADY_EXISTS"
    )


def test_http_auth_roles_and_tenant_isolation(tmp_path):
    users = {
        name: {"role": role, "token_sha256": hashlib.sha256(token.encode()).hexdigest()}
        for name, role, token in [
            ("alice", "analyst", "alice-synthetic-token"),
            ("bob", "analyst", "bob-synthetic-token"),
            ("viewer", "reader", "viewer-synthetic-token"),
        ]
    }
    app = create_http_app(Settings(tmp_path / "http"), users)
    with TestClient(app, base_url="http://127.0.0.1:8769") as client:
        assert client.post("/mcp", json={}).status_code == 401

        def call(user, name, req):
            response = client.post(
                "/mcp",
                headers={
                    "Authorization": "Bearer " + user + "-synthetic-token",
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": {"request": req}},
                },
            )
            assert response.status_code == 200, response.text
            return response.json()["result"]["structuredContent"]

        assert call("alice", "generate_demo_dataset", {"dataset_id": "owned"})["ok"]
        assert (
            call("bob", "validate_dataset", {"dataset_id": "owned"})["error"]["code"] == "NOT_FOUND"
        )
        assert call("viewer", "generate_demo_dataset", {})["error"]["code"] == "FORBIDDEN"
        assert call("alice", "validate_dataset", {"dataset_id": "owned"})["data"]["valid"]


def test_user_config_rejects_duplicate_tokens():
    same = {"role": "analyst", "token_sha256": "0" * 64}
    with pytest.raises(ValueError):
        validate_users({"one": same, "two": same})
