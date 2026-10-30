"""Entrypoint configuration and cleanup, replacing only the blocking listener boundary."""

import hashlib
import json

import pytest
from starlette.testclient import TestClient

from mmm_intelligence import cli, server
from mmm_intelligence.config import Settings


@pytest.mark.parametrize("command", [[], ["serve"]])
def test_stdio_entry_closes_real_service_when_listener_fails(tmp_path, monkeypatch, command):
    mcp, service = server.create_server(Settings(tmp_path))
    assert service.log.handlers

    def interrupted(*args, **kwargs):
        assert kwargs == {"transport": "stdio"}
        raise RuntimeError("listener interrupted")

    monkeypatch.setattr(mcp, "run", interrupted)
    monkeypatch.setattr(server, "create_server", lambda: (mcp, service))
    monkeypatch.setenv("MMM_TRANSPORT", "stdio")
    with pytest.raises(RuntimeError, match="listener interrupted"):
        cli.main(command)
    assert service.log.handlers == []
    assert not list((tmp_path / "datasets").glob("*.json"))


def test_http_server_entry_uses_fixed_loopback_and_authenticated_mcp(tmp_path, monkeypatch):
    import uvicorn

    monkeypatch.setenv("MMM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MMM_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MMM_PORT", "7654")
    monkeypatch.setenv(
        "MMM_USERS_JSON",
        json.dumps(
            {
                "analyst": {
                    "role": "analyst",
                    "token_sha256": hashlib.sha256(b"fabricated entrypoint token").hexdigest(),
                }
            }
        ),
    )
    observed = []

    def listener(app, **options):
        assert options == {"host": "127.0.0.1", "port": 7654}
        with TestClient(app, base_url="http://127.0.0.1:7654") as client:
            observed.extend(
                [client.get("/app").status_code, client.post("/mcp", json={}).status_code]
            )

    monkeypatch.setattr(uvicorn, "run", listener)
    server.main()
    assert observed == [200, 401]


def test_dashboard_operator_entry_is_local_and_ignores_proxy_headers(tmp_path, monkeypatch):
    import uvicorn

    monkeypatch.setenv("MMM_DATA_DIR", str(tmp_path))
    observed = []

    def listener(app, **options):
        assert options == {"host": "127.0.0.1", "port": 7653, "proxy_headers": False}
        with TestClient(app, base_url="http://127.0.0.1:7653") as client:
            observed.append(client.get("/app").status_code)

    monkeypatch.setattr(uvicorn, "run", listener)
    assert cli.main(["dashboard", "--port", "7653"]) == 0
    assert observed == [200]


def test_unsupported_transport_is_rejected_without_creating_storage(tmp_path, monkeypatch):
    root = tmp_path / "absent"
    monkeypatch.setenv("MMM_DATA_DIR", str(root))
    monkeypatch.setenv("MMM_TRANSPORT", "arbitrary")
    with pytest.raises(ValueError, match="Unsupported"):
        server.main()
    assert not root.exists()
