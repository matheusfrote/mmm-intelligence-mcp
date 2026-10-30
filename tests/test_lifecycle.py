import pytest

from mmm_intelligence.errors import MMMError
from mmm_intelligence.storage import digest


def test_inventory_and_retention_plan_never_remove_files(service, trained):
    out = service.call("storage_inventory", {})
    assert out.ok, out.error
    assert len(out.data["artifacts"]) == 2
    assert out.data["total_bytes"] > 0
    plan = service.call("retention_plan", {"older_than_days": 0})
    assert plan.ok
    assert not plan.data["deleted"]
    assert any(p["kind"] == "datasets" and p["blocked_by"] for p in plan.data["candidates"])
    assert service.store.read("models", "fit") == trained


def test_operator_delete_requires_hash_and_refuses_referenced_data(service, trained):
    from mmm_intelligence.lifecycle import delete_artifact

    with pytest.raises(MMMError, match="hash"):
        delete_artifact(service.store, "models", "fit", "0" * 64)
    data = service.store.read("datasets", "demo")
    with pytest.raises(MMMError, match="Referenced"):
        delete_artifact(service.store, "datasets", "demo", digest(data))
    delete_artifact(service.store, "models", "fit", digest(trained))
    assert not service.store.path("models", "fit").exists()
    delete_artifact(service.store, "datasets", "demo", digest(data))
    assert not service.store.path("datasets", "demo").exists()


def test_delete_never_accepts_path_or_link(service, tmp_path):
    from mmm_intelligence.lifecycle import delete_artifact

    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    with pytest.raises(MMMError):
        delete_artifact(service.store, "datasets", "../../outside", "0" * 64)
    assert outside.read_text() == "keep"


def test_report_blocks_model_deletion(service, trained):
    from mmm_intelligence.lifecycle import delete_artifact

    report = service.call("generate_report", {"model_id": "fit"})
    assert report.ok
    with pytest.raises(MMMError, match="Referenced"):
        delete_artifact(service.store, "models", "fit", digest(trained))


def test_new_tools_preserve_reader_isolation_and_no_mcp_deletion(tmp_path):
    from mmm_intelligence.config import Settings
    from mmm_intelligence.http_transport import HTTPUser, TenantRouter, principal

    router = TenantRouter(
        Settings(tmp_path),
        {
            "writer": HTTPUser("analyst", "0" * 64),
            "reader": HTTPUser("reader", "1" * 64),
        },
    )
    token = principal.set("writer")
    try:
        assert router.call("generate_demo_dataset", {"dataset_id": "private"}).ok
        principal.set("reader")
        assert router.call("storage_inventory", {}).data["artifacts"] == []
        assert router.call("data_quality", {"dataset_id": "private"}).error.code == "NOT_FOUND"
        assert router.call("import_csv", {}).error.code == "FORBIDDEN"
        assert router.call("connector_status", {}).data["network_requests"] == 0
        assert "delete_artifact" not in router.REQUESTS
    finally:
        principal.reset(token)
        router.close()
