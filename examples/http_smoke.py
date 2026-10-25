"""Start and stop an authenticated loopback MCP server and verify tenant isolation."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import secrets
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def exercise(url, tokens):
    async def call(user, name, request):
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + tokens[user]}) as http:
            async with Client(streamable_http_client(url, http_client=http)) as client:
                result = await client.call_tool(name, {"request": request})
                return result.structured_content

    created = await call("alice", "generate_demo_dataset", {"dataset_id": "private"})
    assert created["ok"]
    isolated = await call("bob", "validate_dataset", {"dataset_id": "private"})
    assert isolated["error"]["code"] == "NOT_FOUND"
    forbidden = await call("viewer", "generate_demo_dataset", {})
    assert forbidden["error"]["code"] == "FORBIDDEN"
    return {
        "transport": "streamable-http-loopback",
        "sdk": "2.x",
        "created": True,
        "tenant_isolation": True,
        "reader_write_blocked": True,
        "unauthorized_status": 401,
    }


def security_probe(url, tokens):
    """Negative tests and small latency sample against this script's disposable server."""
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {
        "Authorization": "Bearer " + tokens["alice"],
        "Accept": "application/json, text/event-stream",
    }
    with httpx2.Client(timeout=20) as client:
        denied = {}
        for name in ("expired", "disabled"):
            response = client.post(
                url, headers={**headers, "Authorization": "Bearer " + tokens[name]}, json=rpc
            )
            assert response.status_code == 401
            denied[name] = response.status_code
        for field, value in (("Host", "attacker.example"), ("Origin", "https://attacker.example")):
            response = client.post(url, headers={**headers, field: value}, json=rpc)
            assert response.status_code in {400, 403, 421}
            denied[field] = response.status_code
        too_large = client.post(
            url,
            headers={**headers, "Content-Type": "application/json"},
            content=b"x" * (4 * 1024 * 1024 + 1),
        )
        assert too_large.status_code == 413
        denied["body_over_4_mib"] = too_large.status_code
        for method in ("OPTIONS", "PATCH", "DELETE"):
            response = client.request(method, url, headers=headers)
            assert response.status_code == 405
            denied[method] = response.status_code
        elapsed = []
        for _ in range(20):
            start = time.perf_counter()
            response = client.post(url, headers=headers, json=rpc)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            elapsed.append(1000 * (time.perf_counter() - start))
        for _ in range(41):
            limited = client.post(url, headers=headers, json=rpc)
            if limited.status_code == 429:
                break
        assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
        return {
            "negative_statuses": denied,
            "security_headers_present": True,
            "rate_limit_status": 429,
            "latency": {
                "scope": "20 sequential tools/list requests on disposable loopback; not production capacity",
                "samples": 20,
                "p50_ms": statistics.median(elapsed),
                "p95_ms": sorted(elapsed)[math.ceil(0.95 * len(elapsed)) - 1],
            },
        }


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=root / "evidence/http-functional")
    output = parser.parse_args().output_dir.absolute()
    output.mkdir(parents=True, exist_ok=False)
    tokens = {
        name: secrets.token_urlsafe(32)
        for name in ("alice", "bob", "viewer", "expired", "disabled")
    }
    users = {
        name: {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "role": "reader" if name == "viewer" else "analyst",
        }
        for name, token in tokens.items()
    }
    users["expired"]["expires_at"] = "2000-01-01T00:00:00Z"
    users["disabled"]["disabled"] = True
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        port = candidate.getsockname()[1]
    env = {
        **os.environ,
        "MMM_TRANSPORT": "streamable-http",
        "MMM_PORT": str(port),
        "MMM_USERS_JSON": json.dumps(users),
        "MMM_DATA_DIR": str(output / "data"),
        "MMM_ALLOW_REAL_DATA": "false",
        "MMM_HTTP_REQUESTS_PER_MINUTE": "40",
        "MMM_HTTP_UNAUTH_PER_MINUTE": "30",
        "MMM_HTTP_MAX_CONCURRENT": "4",
    }
    with (output / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "mmm_intelligence.server"],
            cwd=root,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            ready = False
            for _ in range(150):
                if process.poll() is not None:
                    raise RuntimeError("HTTP server exited before readiness")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.1)
            if not ready:
                raise RuntimeError("HTTP server did not start")
            url = f"http://127.0.0.1:{port}/mcp"
            assert httpx2.post(url, json={}).status_code == 401
            result = asyncio.run(exercise(url, tokens))
            result["security"] = security_probe(url, tokens)
            (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
