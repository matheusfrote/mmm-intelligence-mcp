"""Scientific acceptance must remain separate from execution and causal claims."""

import asyncio
from copy import deepcopy

import pytest

from mmm_intelligence.schemas import AuditRequest


def test_scientific_request_is_additive_and_bounded():
    assert "scientific" in AuditRequest.model_fields
    request = AuditRequest(model_id="fit", scientific={})
    assert request.scientific.policy_version == "scientific-v1"
    with pytest.raises(ValueError):
        AuditRequest(model_id="fit", scientific={"monte_carlo": {"replications": 100001}})
    with pytest.raises(ValueError):
        AuditRequest(model_id="fit", scientific={"experiment_result_ids": ["../secret"]})


def test_ridge_and_robyn_do_not_use_mcmc_acceptance(service, trained):
    from mmm_intelligence.validation import classify_scientific

    dataset = service.load_dataset("demo")
    for backend in ("ridge", "meta_robyn"):
        model = deepcopy(trained)
        model.update(backend=backend, restore_verified=True)
        result = classify_scientific(model, dataset, backend=backend)
        assert result["operational"]["status"] == "passed"
        assert result["statistical"]["mcmc"]["status"] == "not_applicable"
        assert result["statistical"]["status"] == "inconclusive"
        assert result["causal"]["status"] == "simulation_only"
        assert result["causal"]["causal_identification"] is False


def test_many_draws_and_good_fit_cannot_approve_missing_diagnostics(service, trained):
    from mmm_intelligence.validation import classify_scientific

    model = deepcopy(trained)
    model["diagnostics"] = {"chains": 4, "draws": 2000, "tune": 2000}
    model["restore_verified"] = True
    result = classify_scientific(model, service.load_dataset("demo"), backend="google_meridian")
    assert result["statistical"]["status"] == "inconclusive"
    assert result["statistical"]["missing"]
    assert not result["business_recommendation_eligible"]


def test_real_protocol_persists_and_requeries_without_overwriting_model(service, trained):
    before = service.store.read("models", "fit")
    result = service.call("audit_model", {"model_id": "fit", "scientific": {"refit": False}})
    assert result.ok, result.error
    assert "classifications" in result.data
    assert result.data["artifact_type"] == "scientific_validation"
    record = service.call("get_growth_artifact", {"artifact_id": result.data["artifact_id"]})
    assert record.ok
    analysis = service.call(
        "get_analysis",
        {"model_id": "fit", "scientific_report_id": result.data["artifact_id"]},
    )
    assert analysis.ok, analysis.error
    assert analysis.data["scientific_validation"]["artifact_id"] == result.data["artifact_id"]
    assert service.store.read("models", "fit") == before


def test_refits_measure_ridge_regularization_without_selecting_holdout_winner(service, trained):
    result = service.call("audit_model", {"model_id": "fit", "scientific": {"refit": True}})
    assert result.ok, result.error
    sensitivity = result.data["stability"]
    assert sensitivity["status"] == "executed"
    assert len(sensitivity["runs"]) >= 3
    assert sensitivity["winner"] is None
    assert {r["configuration"]["ridge_alpha"] for r in sensitivity["runs"]} == {0.01, 0.1, 1.0}
    assert "R²" not in sensitivity["acceptance_basis"]


def test_mcse_and_ppc_failures_cannot_be_hidden_by_other_screens(service, trained):
    from mmm_intelligence.validation import classify_scientific

    model = deepcopy(trained)
    model["diagnostics"] = {
        "chains": 4,
        "draws": 1000,
        "tune": 1000,
        "r_hat_max": 1.001,
        "ess_bulk_min": 900,
        "ess_tail_min": 800,
        "divergences": 0,
        "r_hat_undefined_count": 0,
        "ess_bulk_undefined_count": 0,
        "ess_tail_undefined_count": 0,
    }
    model["scientific_diagnostics"] = {
        "available": True,
        "mcse_sd_ratio_max": 0.2,
        "undefined_mcse_count": 0,
        "trace_series": [{"chains": [[0], [1]]}],
        "truncated": False,
    }
    model["posterior_predictive_check"] = {
        "available": True,
        "scope": "observed_outcome",
        "degenerate": False,
        "discrepancy_flags": ["mean_discrepancy"],
    }
    result = classify_scientific(
        model,
        service.load_dataset("demo"),
        backend="pymc_marketing",
        stability={"status": "executed", "unstable": False},
    )
    assert result["statistical"]["status"] == "failed"
    assert "predictive_discrepancy" in result["statistical"]["failed"]
    assert "mcse_exceeds_precision_policy" in result["statistical"]["failed"]


def test_scientific_cycle_uses_existing_official_mcp_tools(tmp_path):
    from mcp import Client

    from mmm_intelligence.config import Settings
    from mmm_intelligence.server import create_server

    async def cycle():
        server, service = create_server(Settings(tmp_path / "sdk"))
        try:
            async with Client(server) as client:

                async def call(name, **request):
                    response = await client.call_tool(name, {"request": request})
                    assert not response.is_error
                    assert response.structured_content["ok"], response.structured_content
                    return response.structured_content["data"]

                await call("generate_demo_dataset", dataset_id="science")
                await call("train_mmm", dataset_id="science", model_id="science")
                report = await call(
                    "audit_model",
                    model_id="science",
                    scientific={
                        "refit": False,
                        "monte_carlo": {
                            "replications": 2,
                            "bootstrap_samples": 20,
                            "scenarios": ["well_specified"],
                        },
                    },
                )
                assert report["monte_carlo"]["attempted"] == 2
                exported = await call(
                    "export_analysis",
                    model_id="science",
                    format="json",
                    scientific_report_id=report["artifact_id"],
                )
                assert report["artifact_id"] in exported["content"]
                assert "simulation_only" in exported["content"]
        finally:
            service.close()

    asyncio.run(cycle())


def test_reader_cannot_create_scientific_reports(tmp_path):
    import hashlib

    from mmm_intelligence.config import Settings
    from mmm_intelligence.http_transport import TenantRouter, principal, validate_users

    users = validate_users(
        {"reader": {"role": "reader", "token_sha256": hashlib.sha256(b"synthetic").hexdigest()}}
    )
    router = TenantRouter(Settings(tmp_path), users)
    reset = principal.set("reader")
    try:
        response = router.call(
            "audit_model", {"model_id": "missing", "scientific": {"refit": False}}
        )
        assert response.error.code == "FORBIDDEN"
        # Existing read-only legacy audit authorization is retained.
        assert router.call("audit_model", {"model_id": "missing"}).error.code == "NOT_FOUND"
    finally:
        principal.reset(reset)
        router.close()


def test_robyn_search_requires_optimization_trace_and_parameter_stability(service, trained):
    from mmm_intelligence.validation import classify_scientific

    model = deepcopy(trained)
    model["diagnostics"] = {
        "trials": 3,
        "iterations": 2000,
        "optimization_trace": [
            {"error_type": "NRMSE", "cuts": "2000", "flag_med": False, "flag_sd": False}
        ],
    }
    report = classify_scientific(
        model,
        service.load_dataset("demo"),
        backend="meta_robyn",
        stability={"status": "executed", "unstable": False, "estimate_consistency_available": True},
    )
    assert report["statistical"]["mcmc"]["status"] == "not_applicable"
    assert "native_search_convergence_warning" in report["statistical"]["failed"]


def test_bootstrap_intervals_require_their_own_calibration_evidence(service, trained):
    assert service.call(
        "train_mmm", {"dataset_id": "demo", "model_id": "uncertain", "bootstrap_samples": 20}
    ).ok
    report = service.call("audit_model", {"model_id": "uncertain", "scientific": {"refit": True}})
    assert report.ok
    assert report.data["classifications"]["statistical"]["status"] == "inconclusive"
    assert (
        "conditional_interval_validation_unavailable"
        in report.data["classifications"]["statistical"]["missing"]
    )


def test_measured_monte_carlo_failure_propagates_to_statistical_classification(service, trained):
    report = service.call(
        "audit_model",
        {
            "model_id": "fit",
            "scientific": {
                "refit": False,
                "monte_carlo": {
                    "replications": 30,
                    "minimum_replications_for_assessment": 30,
                    "bootstrap_samples": 20,
                    "scenarios": ["well_specified", "null_effect"],
                    "max_absolute_bias": 0.0,
                    "max_rmse": 0.0,
                },
            },
        },
    )
    assert report.ok, report.error
    assert report.data["monte_carlo"]["acceptance"]["status"] == "failed"
    statistical = report.data["classifications"]["statistical"]
    assert statistical["status"] == "failed"
    assert any(reason.startswith("monte_carlo:") for reason in statistical["failed"])


def test_ridge_monte_carlo_cannot_be_mislabeled_as_a_native_engine_study():
    with pytest.raises(ValueError):
        AuditRequest(
            model_id="native",
            backend="pymc_marketing",
            scientific={"monte_carlo": {"replications": 2}},
        )
