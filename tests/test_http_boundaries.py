"""Malformed host headers fail closed; input errors never escape as server crashes."""

import hashlib

import pytest
from starlette.testclient import TestClient

from mmm_intelligence.config import Settings
from mmm_intelligence.http_transport import (
    HTTPPolicy,
    TenantRouter,
    create_http_app,
    principal,
    validate_users,
)


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "[malformed"},
        {"Host": "user:password@127.0.0.1"},
        {"Host": "localhost/path"},
        {"Host": "localhost?query=1"},
        {"Host": "127.0.0.1", "Origin": "https://foreign.invalid"},
        [("Host", "foreign.invalid"), ("Host", "127.0.0.1")],
    ],
)
def test_asset_host_boundary_never_raises_for_malformed_input(tmp_path, headers):
    with TestClient(
        create_http_app(Settings(tmp_path)), base_url="http://127.0.0.1:8769"
    ) as client:
        response = client.get("/app", headers=headers)
    assert response.status_code == 421
    assert "MMM Intelligence" not in response.text


@pytest.mark.parametrize(
    "key,value",
    [
        ("MMM_HTTP_REQUESTS_PER_MINUTE", "0"),
        ("MMM_HTTP_UNAUTH_PER_MINUTE", "1001"),
        ("MMM_HTTP_MAX_CONCURRENT", "33"),
    ],
)
def test_http_resource_policy_rejects_unbounded_configuration(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="resource policy"):
        HTTPPolicy.from_env()


@pytest.mark.parametrize(
    "name,extra",
    [("con", {}), ("analyst", {"expires_at": False}), ("analyst", {"expires_at": "invalid"})],
)
def test_reserved_or_invalid_token_configuration_is_refused(name, extra):
    with pytest.raises(ValueError):
        validate_users(
            {
                name: {
                    "role": "reader",
                    "token_sha256": hashlib.sha256(b"fabricated").hexdigest(),
                    **extra,
                }
            }
        )


def test_router_rechecks_principal_even_when_called_directly(tmp_path):
    user = validate_users(
        {"reader": {"role": "reader", "token_sha256": hashlib.sha256(b"fabricated").hexdigest()}}
    )
    router = TenantRouter(Settings(tmp_path), user)
    reset = principal.set("foreign")
    try:
        assert router.call("storage_inventory", {}).error.code == "FORBIDDEN"
        with pytest.raises(ValueError, match="Unauthorized"):
            router.load_dataset("foreign-dataset")
    finally:
        principal.reset(reset)
        router.close()
