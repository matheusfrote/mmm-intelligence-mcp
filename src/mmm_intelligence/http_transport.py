"""Opt-in local HTTP with bearer authentication, roles and per-user artifact roots."""

import contextvars
import hashlib
import hmac
import json
import math
import os
import re
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import monotonic

from .config import Settings
from .schemas import IDENTIFIER_PATTERN, PublicError, ToolResponse
from .service import MMMService

principal = contextvars.ContextVar("mmm_principal", default=None)
LOCAL_DASHBOARD = "_local_dashboard"
READ_TOOLS = {
    "backend_status",
    "validate_dataset",
    "get_model",
    "simulate_budget",
    "optimize_budget",
    "calibrate_experiment",
    "predict_backend",
    "get_backend_model",
    "audit_model",
    "data_quality",
    "get_analysis",
    "compare_models",
    "model_capabilities",
    "forecast_model",
    "export_analysis",
    "storage_inventory",
    "retention_plan",
    "connector_status",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class HTTPUser:
    role: str
    token_sha256: str
    disabled: bool = False
    expires_at: datetime | None = None


@dataclass(frozen=True)
class HTTPPolicy:
    requests_per_minute: int = 120
    unauth_per_minute: int = 30
    max_concurrent: int = 4

    @classmethod
    def from_env(cls):
        policy = cls(
            int(os.getenv("MMM_HTTP_REQUESTS_PER_MINUTE", "120")),
            int(os.getenv("MMM_HTTP_UNAUTH_PER_MINUTE", "30")),
            int(os.getenv("MMM_HTTP_MAX_CONCURRENT", "4")),
        )
        if (
            not 1 <= policy.requests_per_minute <= 10000
            or not 1 <= policy.unauth_per_minute <= 1000
            or not 1 <= policy.max_concurrent <= 32
        ):
            raise ValueError("Invalid HTTP resource policy")
        return policy


class TenantRouter:
    REQUESTS = MMMService.REQUESTS

    def __init__(self, settings, users):
        self.users = users
        self.dashboard_service = MMMService(
            replace(settings, data_dir=settings.data_dir / "dashboard")
        )
        self.services = {
            name: MMMService(replace(settings, data_dir=settings.data_dir / "tenants" / name))
            for name in users
        }

    def call(self, name, args):
        user = principal.get()
        if user == LOCAL_DASHBOARD:
            return self.dashboard_service.call(name, args)
        if user not in self.users or (self.users[user].role == "reader" and name not in READ_TOOLS):
            return ToolResponse(
                ok=False,
                error=PublicError(code="FORBIDDEN", message="Role does not authorize this tool"),
            )
        return self.services[user].call(name, args)

    def close(self):
        self.dashboard_service.close()
        for service in self.services.values():
            service.close()

    def load_dataset(self, dataset_id):
        user = principal.get()
        if user == LOCAL_DASHBOARD:
            return self.dashboard_service.load_dataset(dataset_id)
        if user not in self.users:
            raise ValueError("Unauthorized")
        return self.services[user].load_dataset(dataset_id)


def validate_users(users):
    if not isinstance(users, dict) or not 1 <= len(users) <= 100:
        raise ValueError("Configure 1..100 users")
    normalized = {}
    for name, data in users.items():
        if (
            not isinstance(name, str)
            or not re.fullmatch(IDENTIFIER_PATTERN, name)
            or not isinstance(data, dict)
            or not {"token_sha256", "role"}.issubset(data)
            or not set(data).issubset({"token_sha256", "role", "expires_at", "disabled"})
            or not isinstance(data["role"], str)
            or data["role"] not in {"reader", "analyst"}
            or not isinstance(data["token_sha256"], str)
            or not re.fullmatch("[0-9a-f]{64}", data["token_sha256"])
            or type(data.get("disabled", False)) is not bool
        ):
            raise ValueError("Invalid HTTP user configuration")
        if name.split("_")[0] in {
            "con",
            "prn",
            "aux",
            "nul",
            *[f"com{i}" for i in range(1, 10)],
            *[f"lpt{i}" for i in range(1, 10)],
        }:
            raise ValueError("Reserved HTTP user identifier")
        expiry = None
        if "expires_at" in data:
            if not isinstance(data["expires_at"], str):
                raise ValueError("Token expiry must be an ISO timestamp with timezone")
            try:
                expiry = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Invalid token expiry") from exc
            if expiry.tzinfo is None or expiry.utcoffset() is None:
                raise ValueError("Token expiry requires timezone")
            expiry = expiry.astimezone(timezone.utc)
        normalized[name] = HTTPUser(
            data["role"], data["token_sha256"], data.get("disabled", False), expiry
        )
    hashes = [u["token_sha256"] for u in users.values()]
    if len(hashes) != len(set(hashes)):
        raise ValueError("Users must have distinct tokens")
    return normalized


def create_http_app(settings: Settings, users: dict | None = None):
    from .server import create_server

    # None is the explicit local-only launcher; an empty configured user map is
    # still rejected for the regular authenticated HTTP server.
    users = {} if users is None else validate_users(users)
    policy = HTTPPolicy.from_env()
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
            # Keys are bounded by the configured users plus one unauthenticated bucket.
            self.requests = defaultdict(deque)
            self.active = defaultdict(int)

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.app(scope, receive, send)

            from .web_app import ASSETS, local_dashboard_request, serve_asset

            if scope["method"] == "GET" and scope["path"] in ASSETS:
                return await serve_asset(scope, send)

            async def secure_send(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    controls = {
                        b"cache-control": b"no-store",
                        b"x-content-type-options": b"nosniff",
                        b"x-frame-options": b"DENY",
                        b"referrer-policy": b"no-referrer",
                        b"content-security-policy": b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                    }
                    headers = [(k, v) for k, v in headers if k.lower() not in controls]
                    message = {**message, "headers": headers + list(controls.items())}
                await send(message)

            authorizations = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
            authorization = authorizations[0].decode("latin-1") if len(authorizations) == 1 else ""
            token = authorization[7:] if authorization[:7].lower() == "bearer " else ""
            if not 1 <= len(token) <= 512 or any(ord(c) < 33 or ord(c) > 126 for c in token):
                # Empty rejection sentinel is never a usable credential.
                token = ""  # nosec B105
            hashed = hashlib.sha256(token.encode()).hexdigest()
            user = next(
                (
                    name
                    for name, data in users.items()
                    if token
                    and hmac.compare_digest(data.token_sha256, hashed)
                    and not data.disabled
                    and (data.expires_at is None or utc_now() < data.expires_at)
                ),
                None,
            )
            dashboard = scope["path"] == "/app/mcp"
            if dashboard and local_dashboard_request(scope):
                user = LOCAL_DASHBOARD
            key = user or "_unauthenticated"
            limit = policy.requests_per_minute if user else policy.unauth_per_minute
            now = monotonic()
            queue = self.requests[key]
            while queue and queue[0] <= now - 60:
                queue.popleft()

            async def reject(status, error, headers=()):
                body = json.dumps({"error": error}).encode()
                await secure_send(
                    {
                        "type": "http.response.start",
                        "status": status,
                        "headers": [
                            (b"content-type", b"application/json"),
                            *headers,
                        ],
                    }
                )
                await secure_send({"type": "http.response.body", "body": body})

            if dashboard and user != LOCAL_DASHBOARD:
                return await reject(403, "local_dashboard_origin_required")

            if len(queue) >= limit:
                return await reject(
                    429,
                    "rate_limited",
                    [(b"retry-after", str(max(1, math.ceil(60 - now + queue[0]))).encode())],
                )
            queue.append(now)
            if not user:
                return await reject(401, "unauthorized", [(b"www-authenticate", b"Bearer")])
            if self.active[user] >= policy.max_concurrent:
                return await reject(429, "concurrency_limited", [(b"retry-after", b"1")])
            self.active[user] += 1
            reset = principal.set(user)
            try:
                if dashboard:
                    scope = {**scope, "path": "/mcp", "raw_path": b"/mcp"}
                return await self.app(scope, receive, secure_send)
            finally:
                principal.reset(reset)
                self.active[user] -= 1

    app.add_middleware(BearerMiddleware)
    return app
