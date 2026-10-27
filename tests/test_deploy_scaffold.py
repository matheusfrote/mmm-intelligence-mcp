"""Structural guards only; these do not claim Docker, TLS or OAuth validation."""

from pathlib import Path

import yaml


def test_deploy_templates_do_not_expose_the_no_login_dashboard():
    root = Path(__file__).resolve().parents[1] / "deploy"
    compose = yaml.safe_load((root / "compose.yaml").read_text())
    service = compose["services"]["mcp"]
    assert "operator-approved" in service["profiles"]
    assert service["network_mode"] == "host" and "ports" not in service
    assert service["read_only"] is True and service["cap_drop"] == ["ALL"]
    assert service["volumes"] == ["artifacts:/artifacts"]
    edge = (root / "nginx.conf.template").read_text()
    assert "location = /mcp" in edge
    assert "location / { return 404; }" in edge
    assert "proxy_set_header Authorization $http_authorization" in edge
    assert "proxy_pass http://127.0.0.1:8769/mcp" in edge
