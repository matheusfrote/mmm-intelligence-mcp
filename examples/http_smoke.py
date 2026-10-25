"""Start and stop an authenticated loopback MCP server and verify tenant isolation."""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import socket
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


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=root / "evidence/http-functional")
    output = parser.parse_args().output_dir.absolute()
    output.mkdir(parents=True, exist_ok=False)
    tokens = {name: secrets.token_urlsafe(32) for name in ("alice", "bob", "viewer")}
    users = {
        name: {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "role": "reader" if name == "viewer" else "analyst",
        }
        for name, token in tokens.items()
    }
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
            (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
