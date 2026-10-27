"""Browser shell and dataset resource keep the existing tenant boundary."""

import hashlib
import json

import pytest
from starlette.testclient import TestClient

from mmm_intelligence.config import Settings
from mmm_intelligence.http_transport import create_http_app


def test_web_shell_is_public_but_data_and_other_paths_are_not(tmp_path):
    users = {
        name: {"role": "analyst", "token_sha256": hashlib.sha256(name.encode()).hexdigest()}
        for name in ("alice", "bob")
    }
    with TestClient(
        create_http_app(Settings(tmp_path), users), base_url="http://127.0.0.1:8769"
    ) as c:
        shell = c.get("/app")
        assert shell.status_code == 200
        assert "MMM Intelligence" in shell.text
        assert 'id="login"' not in shell.text
        assert 'id="token"' not in shell.text
        assert "script-src 'self'" in shell.headers["content-security-policy"]
        assert c.get("/app/app.js").status_code == 200
        assert c.get("/app/missing.js").status_code == 401
        assert c.post("/app").status_code == 401
        assert c.get("/app", headers={"Host": "evil.example"}).status_code == 421
        assert c.post("/mcp", json={}).status_code == 401

        def rpc(user, method, params):
            return c.post(
                "/mcp",
                headers={
                    "Authorization": "Bearer " + user,
                    "Accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            ).json()

        generated = rpc(
            "alice",
            "tools/call",
            {"name": "generate_demo_dataset", "arguments": {"request": {"dataset_id": "demo"}}},
        )
        assert generated["result"]["structuredContent"]["ok"]
        read = rpc("alice", "resources/read", {"uri": "mmm://datasets/demo"})
        dataset = json.loads(read["result"]["contents"][0]["text"])
        assert len(dataset["rows"]) == 156
        assert "error" in rpc("bob", "resources/read", {"uri": "mmm://datasets/demo"})
        assert "error" in rpc("alice", "resources/read", {"uri": "mmm://datasets/../demo"})
        templates = rpc("alice", "resources/templates/list", {})
        assert (
            templates["result"]["resourceTemplates"][0]["uriTemplate"]
            == "mmm://datasets/{dataset_id}"
        )


DASHBOARD_HEADERS = {
    "Origin": "http://127.0.0.1:8769",
    "X-MMM-Dashboard": "1",
    "Sec-Fetch-Site": "same-origin",
    "Accept": "application/json, text/event-stream",
}


def test_dashboard_needs_no_token_and_cannot_read_another_tenant(tmp_path):
    users = {"alice": {"role": "analyst", "token_sha256": hashlib.sha256(b"alice").hexdigest()}}
    with TestClient(
        create_http_app(Settings(tmp_path), users),
        base_url="http://127.0.0.1:8769",
        client=("127.0.0.1", 1234),
    ) as c:

        def rpc(path, headers, method, params):
            return c.post(
                path,
                headers=headers,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )

        generated = rpc(
            "/app/mcp",
            DASHBOARD_HEADERS,
            "tools/call",
            {
                "name": "generate_demo_dataset",
                "arguments": {"request": {"dataset_id": "local-demo"}},
            },
        )
        assert generated.status_code == 200
        assert generated.json()["result"]["structuredContent"]["ok"]
        read = rpc(
            "/app/mcp", DASHBOARD_HEADERS, "resources/read", {"uri": "mmm://datasets/local-demo"}
        )
        assert len(json.loads(read.json()["result"]["contents"][0]["text"])["rows"]) == 156
        alice = {"Authorization": "Bearer alice", "Accept": DASHBOARD_HEADERS["Accept"]}
        assert (
            "error"
            in rpc("/mcp", alice, "resources/read", {"uri": "mmm://datasets/local-demo"}).json()
        )
        rpc(
            "/mcp",
            alice,
            "tools/call",
            {
                "name": "generate_demo_dataset",
                "arguments": {"request": {"dataset_id": "private-demo"}},
            },
        )
        assert (
            "error"
            in rpc(
                "/app/mcp",
                DASHBOARD_HEADERS,
                "resources/read",
                {"uri": "mmm://datasets/private-demo"},
            ).json()
        )
        assert rpc("/mcp", DASHBOARD_HEADERS, "tools/list", {}).status_code == 401
        assert (tmp_path / "dashboard" / "datasets" / "local-demo.json").is_file()


@pytest.mark.parametrize(
    "extra,removed,peer",
    [
        ({"Origin": "https://evil.example"}, None, "127.0.0.1"),
        ({"Host": "evil.example"}, None, "127.0.0.1"),
        ({}, "Origin", "127.0.0.1"),
        ({}, "X-MMM-Dashboard", "127.0.0.1"),
        ({"Sec-Fetch-Site": "cross-site"}, None, "127.0.0.1"),
        ({"X-Forwarded-For": "127.0.0.1"}, None, "127.0.0.1"),
        ({}, None, "192.0.2.1"),
    ],
)
def test_dashboard_rejects_external_and_cross_site_requests(tmp_path, extra, removed, peer):
    users = {"alice": {"role": "analyst", "token_sha256": hashlib.sha256(b"alice").hexdigest()}}
    headers = {**DASHBOARD_HEADERS, **extra}
    if removed:
        headers.pop(removed)
    with TestClient(
        create_http_app(Settings(tmp_path), users),
        base_url="http://127.0.0.1:8769",
        client=(peer, 1234),
    ) as c:
        assert (
            c.post(
                "/app/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            ).status_code
            == 403
        )
