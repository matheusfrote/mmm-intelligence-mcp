"""Security regressions use only fabricated credentials, payloads and isolated roots."""

import base64
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from mmm_intelligence.config import Settings
from mmm_intelligence.http_transport import create_http_app, validate_users
from mmm_intelligence.rendering import dashboard

TOKEN = "fabricated-appsec-token"
HEADERS = {"Authorization": "Bearer " + TOKEN, "Accept": "application/json, text/event-stream"}


def users(**extra):
    return {
        "analyst": {
            "role": "analyst",
            "token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
            **extra,
        }
    }


def rpc():
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


@pytest.mark.parametrize("extra", [{"disabled": True}, {"expires_at": "2000-01-01T00:00:00Z"}])
def test_disabled_and_expired_tokens_cannot_discover_tools(tmp_path, extra):
    with TestClient(
        create_http_app(Settings(tmp_path), users(**extra)), base_url="http://127.0.0.1:8769"
    ) as client:
        response = client.post("/mcp", headers=HEADERS, json=rpc())
        assert response.status_code == 401
        assert TOKEN not in response.text


def test_token_expiry_is_checked_on_every_request(tmp_path, monkeypatch):
    from mmm_intelligence import http_transport

    before = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(http_transport, "utc_now", lambda: before)
    app = create_http_app(Settings(tmp_path), users(expires_at="2026-01-02T00:00:00Z"))
    with TestClient(app, base_url="http://127.0.0.1:8769") as client:
        assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 200
        monkeypatch.setattr(http_transport, "utc_now", lambda: before + timedelta(days=2))
        assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 401


def test_duplicate_auth_and_remote_host_origin_are_denied(tmp_path):
    with TestClient(
        create_http_app(Settings(tmp_path), users()), base_url="http://127.0.0.1:8769"
    ) as client:
        duplicate = [("Authorization", "Bearer " + TOKEN), ("Authorization", "Bearer " + TOKEN)]
        assert client.post("/mcp", headers=duplicate, json=rpc()).status_code == 401
        assert client.post(
            "/mcp", headers={**HEADERS, "Host": "attacker.example"}, json=rpc()
        ).status_code in {400, 403, 421}
        assert (
            client.post(
                "/mcp", headers={**HEADERS, "Origin": "https://attacker.example"}, json=rpc()
            ).status_code
            == 403
        )


def test_security_headers_cover_authenticated_and_error_responses(tmp_path):
    with TestClient(
        create_http_app(Settings(tmp_path), users()), base_url="http://127.0.0.1:8769"
    ) as client:
        for headers in ({}, HEADERS):
            response = client.post("/mcp", headers=headers, json=rpc())
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-frame-options"] == "DENY"
            assert "default-src 'none'" in response.headers["content-security-policy"]


def test_bounded_request_rate_and_retry_after(tmp_path, monkeypatch):
    monkeypatch.setenv("MMM_HTTP_REQUESTS_PER_MINUTE", "2")
    with TestClient(
        create_http_app(Settings(tmp_path), users()), base_url="http://127.0.0.1:8769"
    ) as client:
        assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 200
        assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 200
        blocked = client.post("/mcp", headers=HEADERS, json=rpc())
        assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0


@pytest.mark.parametrize(
    "profile",
    [
        users(expires_at="tomorrow"),
        users(expires_at="2030-01-01"),
        users(disabled="false"),
        {"analyst": {"role": [], "token_sha256": "0" * 64}},
        {False: {"role": "reader", "token_sha256": "0" * 64}},
    ],
)
def test_malformed_operator_config_fails_closed(profile):
    with pytest.raises(ValueError):
        validate_users(profile)


def test_dashboard_does_not_allow_arbitrary_inline_scripts(trained):
    model = deepcopy(trained)
    model["warnings"].append(
        '</script><script>window.APPSEC_INJECTED=true</script><img src="https://attacker.example">'
    )
    rendered = dashboard(model)
    scripts = re.findall(r"<script>(.*?)</script>", rendered, re.S)
    assert len(scripts) == 1
    expected = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    assert "'sha256-" + expected + "'" in rendered
    assert "script-src 'unsafe-inline'" not in rendered
    assert "</script><script>window.APPSEC_INJECTED" not in rendered


def test_worker_does_not_inherit_host_credentials_or_reflect_failure(tmp_path, monkeypatch):
    from mmm_intelligence.integrations import bridge
    from mmm_intelligence.storage import ArtifactStore

    monkeypatch.setenv("MMM_USERS_JSON", "PRIVATE-CREDENTIAL")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "PRIVATE-CREDENTIAL")
    monkeypatch.setenv("UNUSUAL_PRIVATE_KEY", "PRIVATE-CREDENTIAL")
    monkeypatch.setenv("MMM_RSCRIPT", "operator-runtime")
    monkeypatch.setattr(bridge, "executable", lambda backend: __import__("pathlib").Path(__file__))
    seen = {}

    def worker(args, **kwargs):
        seen.update(kwargs["env"])
        __import__("pathlib").Path(args[-1]).write_text(
            json.dumps(
                {
                    "ok": False,
                    "code": "BACKEND_FAILED",
                    "message": "PRIVATE-CREDENTIAL /private/dataset.csv",
                }
            )
        )
        return __import__("subprocess").CompletedProcess(args, 0)

    monkeypatch.setattr(bridge, "run_worker", worker)
    from mmm_intelligence.errors import MMMError

    with pytest.raises(MMMError) as error:
        bridge.execute(ArtifactStore(Settings(tmp_path)), "pymc_marketing", {})
    assert "PRIVATE-CREDENTIAL" not in str(error.value)
    assert "dataset.csv" not in str(error.value)
    assert not any(
        k in seen for k in ("MMM_USERS_JSON", "AWS_SECRET_ACCESS_KEY", "UNUSUAL_PRIVATE_KEY")
    )
    assert seen["MMM_RSCRIPT"] == "operator-runtime"


def test_revocation_by_rotating_hash_takes_effect_after_restart(tmp_path):
    with TestClient(
        create_http_app(Settings(tmp_path), users()), base_url="http://127.0.0.1:8769"
    ) as client:
        assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 200
    replacement = "fabricated-replacement-credential"
    profile = users()
    profile["analyst"]["token_sha256"] = hashlib.sha256(replacement.encode()).hexdigest()
    with TestClient(
        create_http_app(Settings(tmp_path), profile), base_url="http://127.0.0.1:8769"
    ) as client:
        assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 401
        assert (
            client.post(
                "/mcp", headers={**HEADERS, "Authorization": "Bearer " + replacement}, json=rpc()
            ).status_code
            == 200
        )


def test_unauthorized_rate_window_resets_and_sdk_rejects_oversize_body(tmp_path, monkeypatch):
    from mmm_intelligence import http_transport

    monkeypatch.setenv("MMM_HTTP_UNAUTH_PER_MINUTE", "1")
    monkeypatch.setattr(http_transport, "monotonic", lambda: 1.0)
    with TestClient(
        create_http_app(Settings(tmp_path), users()), base_url="http://127.0.0.1:8769"
    ) as client:
        assert client.post("/mcp", json=rpc()).status_code == 401
        assert client.post("/mcp", json=rpc()).status_code == 429
        monkeypatch.setattr(http_transport, "monotonic", lambda: 62.0)
        assert client.post("/mcp", json=rpc()).status_code == 401
        oversized = client.post(
            "/mcp",
            headers={**HEADERS, "Content-Type": "application/json"},
            content=b"x" * (4 * 1024 * 1024 + 1),
        )
        assert oversized.status_code == 413
        assert "Traceback" not in oversized.text


def test_request_concurrency_limit_releases_after_completion(tmp_path, monkeypatch):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from starlette.responses import JSONResponse
    from starlette.routing import Route

    monkeypatch.setenv("MMM_HTTP_MAX_CONCURRENT", "1")
    entered, release = threading.Event(), threading.Event()

    async def probe(request):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return JSONResponse({"ok": True})

    app = create_http_app(Settings(tmp_path), users())
    app.routes.append(Route("/probe", probe))
    with (
        TestClient(app, base_url="http://127.0.0.1:8769") as client,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        running = pool.submit(client.get, "/probe", headers=HEADERS)
        try:
            assert entered.wait(5)
            assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 429
        finally:
            release.set()
        assert running.result(timeout=5).status_code == 200
        assert client.post("/mcp", headers=HEADERS, json=rpc()).status_code == 200


def test_failed_publish_leaves_no_partial_artifact(service, monkeypatch):
    def fail(*args):
        raise OSError("fabricated disk failure")

    monkeypatch.setattr("mmm_intelligence.storage.os.link", fail)
    response = service.call("generate_demo_dataset", {"dataset_id": "interrupted"})
    assert not response.ok and response.error.code == "STORAGE_ERROR"
    assert not service.store.path("datasets", "interrupted").exists()
    assert not list((service.store.root / "datasets").glob(".pending-*"))


def test_secret_check_detects_fabricated_history_without_echoing_value(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    scanner = Path(__file__).resolve().parents[1] / "examples/check_secrets.py"
    git = ["git", "-c", "user.name=AppSec Test", "-c", "user.email=synthetic@example.invalid"]
    subprocess.run([*git, "init", "-q"], cwd=tmp_path, check=True)
    fabricated = "ghp_" + "A" * 36
    fixture = tmp_path / "fixture.txt"
    fixture.write_text(fabricated)
    subprocess.run([*git, "add", "fixture.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        [*git, "commit", "-qm", "fabricated scanner regression"], cwd=tmp_path, check=True
    )
    fixture.write_text("no credential in current worktree")
    result = subprocess.run(
        [sys.executable, str(scanner)], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert fabricated not in result.stdout
    report = json.loads(result.stdout)
    assert any(x["location"].startswith("history:") for x in report["findings"])
    assert not any(x["location"].startswith("worktree:") for x in report["findings"])


@pytest.mark.parametrize("field", ["target_column", "date_column"])
@pytest.mark.parametrize("name", ["column/../../file", "I(system('fabricated'))", "x" * 65])
def test_scalar_column_identifiers_fail_before_worker_or_data_access(
    service, monkeypatch, field, name
):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid column identifier reached native worker")

    monkeypatch.setattr("mmm_intelligence.integrations.bridge.execute", forbidden)
    result = service.call(
        "train_backend", {"dataset_id": "not-read", "backend": "meta_robyn", field: name}
    )
    assert not result.ok and result.error.code == "INPUT_INVALID"
