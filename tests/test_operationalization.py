"""Windows lifecycle, official prompt discovery and explicit capability errors."""

import asyncio
import os

import pytest
from mcp import Client

from mmm_intelligence.config import Settings
from mmm_intelligence.server import create_server
from mmm_intelligence.service import MMMService


@pytest.mark.parametrize("exception", [False, True])
def test_service_context_closes_every_handler_and_releases_windows_log(tmp_path, exception):
    try:
        with MMMService(Settings(tmp_path / "data")) as service:
            handlers = service.log.handlers[:]
            assert service.call("generate_demo_dataset", {"dataset_id": "demo"}).ok
            if exception:
                raise RuntimeError("caller failed")
    except RuntimeError as exc:
        assert exception and str(exc) == "caller failed"
    assert service.log.handlers == []
    assert all(
        getattr(handler, "stream", None) is None
        for handler in handlers
        if hasattr(handler, "baseFilename")
    )
    log = tmp_path / "data/logs/server.log"
    os.replace(log, log.with_suffix(".closed"))
    service.close()  # idempotent explicit cleanup remains supported


def test_official_prompts_have_bounded_arguments_and_never_execute_tools(tmp_path):
    async def cycle():
        mcp, service = create_server(Settings(tmp_path))
        try:
            async with Client(mcp) as client:
                prompts = (await client.list_prompts()).prompts
                assert {p.name for p in prompts} == {
                    "audit_mmm_pipeline",
                    "simulate_budget_scenario",
                    "growth_incrementality_test",
                }
                cases = [
                    (
                        "audit_mmm_pipeline",
                        {"dataset_id": "synthetic"},
                        ["VIF", "rank", "training", "data_quality"],
                    ),
                    (
                        "simulate_budget_scenario",
                        {"model_id": "synthetic"},
                        ["Hill", "carryover", "simulate_budget", "abstain"],
                    ),
                    (
                        "growth_incrementality_test",
                        {"artifact_id": "synthetic"},
                        ["power", "plan_experiment", "cluster", "causal"],
                    ),
                ]
                for name, args, words in cases:
                    result = await client.get_prompt(name, args)
                    assert result.messages and result.messages[0].role == "user"
                    text = "\n".join(message.content.text for message in result.messages)
                    assert all(word in text for word in words), text
                for name, argument in [
                    ("audit_mmm_pipeline", "dataset_id"),
                    ("simulate_budget_scenario", "model_id"),
                    ("growth_incrementality_test", "artifact_id"),
                ]:
                    with pytest.raises(Exception):
                        await client.get_prompt(name, {argument: "../../private"})
            assert service.call("storage_inventory", {}).data["artifacts"] == []
        finally:
            service.close()

    asyncio.run(cycle())


@pytest.mark.parametrize("backend", ["google_meridian", "meta_robyn", "pymc_marketing"])
def test_unsupported_native_optimizer_returns_capability_error(service, backend):
    result = service.call(
        "optimize_budget", {"model_id": "not-loaded", "backend": backend, "total_budget": 100.0}
    )
    assert not result.ok and result.error.code == "OPERATION_UNAVAILABLE"
    assert "Ridge" in result.error.message and "native" in result.error.message
    assert not (service.store.root / "jobs").exists()
