"""Opt-in local HTTP with bearer authentication, roles and per-user artifact roots."""

import contextvars
import hashlib
import hmac
import json
import re
from contextlib import asynccontextmanager
from dataclasses import replace

from .config import Settings
from .schemas import IDENTIFIER_PATTERN, PublicError, ToolResponse
from .service import MMMService

principal = contextvars.ContextVar("mmm_principal", default=None)
READ_TOOLS = {
    "backend_status",
    "validate_dataset",
    "get_model",
    "simulate_budget",
    "optimize_budget",
    "calibrate_experiment",
    "predict_backend",
    "get_backend_model",
}


class TenantRouter:
    REQUESTS = MMMService.REQUESTS

    def __init__(self, settings, users):
        self.users = users
        self.services = {
            name: MMMService(replace(settings, data_dir=settings.data_dir / "tenants" / name))
            for name in users
        }

    def call(self, name, args):
        user = principal.get()
        if user not in self.users or (
            self.users[user]["role"] == "reader" and name not in READ_TOOLS
        ):
            return ToolResponse(
                ok=False,
                error=PublicError(code="FORBIDDEN", message="Role does not authorize this tool"),
            )
        return self.services[user].call(name, args)

    def close(self):
        for service in self.services.values():
            service.close()


def validate_users(users):
    if not isinstance(users, dict) or not 1 <= len(users) <= 100:
        raise ValueError("Configure 1..100 users")
    for name, data in users.items():
        if (
            not re.fullmatch(IDENTIFIER_PATTERN, name)
            or not isinstance(data, dict)
            or set(data) != {"token_sha256", "role"}
            or data["role"] not in {"reader", "analyst"}
            or not re.fullmatch("[0-9a-f]{64}", data["token_sha256"])
        ):
            raise ValueError("Invalid HTTP user configuration")
    hashes = [u["token_sha256"] for u in users.values()]
    if len(hashes) != len(set(hashes)):
        raise ValueError("Users must have distinct tokens")


def create_http_app(settings: Settings, users: dict):
    from .server import create_server

    validate_users(users)
    router = TenantRouter(settings, users)
    mcp, _ = create_server(settings, service_override=router)
    app = mcp.streamable_http_app(
        stateless_http=True, json_response=True, max_request_body_size=4 * 1024 * 1024
    )
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with original_lifespan(app) as state:
                yield state
        finally:
            router.close()

    app.router.lifespan_context = lifespan

    class BearerMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.app(scope, receive, send)
            headers = dict(scope["headers"])
            authorization = headers.get(b"authorization", b"").decode("latin-1")
            token = authorization[7:] if authorization.startswith("Bearer ") else ""
            hashed = hashlib.sha256(token.encode()).hexdigest()
            user = next(
                (
                    name
                    for name, data in users.items()
                    if token and hmac.compare_digest(data["token_sha256"], hashed)
                ),
                None,
            )
            if not user:
                body = json.dumps({"error": "unauthorized"}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"www-authenticate", b"Bearer"),
                        ],
                    }
                )
                return await send({"type": "http.response.body", "body": body})
            reset = principal.set(user)
            try:
                return await self.app(scope, receive, send)
            finally:
                principal.reset(reset)

    app.add_middleware(BearerMiddleware)
    return app
