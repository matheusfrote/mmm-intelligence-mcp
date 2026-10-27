"""Finite shell assets and a strictly same-origin, loopback dashboard boundary."""

from importlib.resources import files
from ipaddress import ip_address
from urllib.parse import urlsplit

ASSETS = {
    "/app": ("index.html", "text/html"),
    **{
        f"/app/{name}": (name, kind)
        for name, kind in (
            ("app.js", "text/javascript"),
            ("client.js", "text/javascript"),
            ("views.js", "text/javascript"),
            ("charts.js", "text/javascript"),
            ("ui.js", "text/javascript"),
            ("app.css", "text/css"),
            ("icon.svg", "image/svg+xml"),
        )
    },
}
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def local_dashboard_request(scope):
    """No credential: local machine access, strict origin and a non-simple header.

    This endpoint must never be reverse-proxied. Tokens and remote tenants belong
    to /mcp, which retains its independent authentication policy.
    """
    if scope["method"] != "POST" or scope.get("scheme") != "http":
        return False
    try:
        if not ip_address(scope.get("client", ("", 0))[0]).is_loopback:
            return False
        values = {}
        for key, value in scope["headers"]:
            key = key.lower()
            if key in values or key == b"forwarded" or key.startswith(b"x-forwarded-"):
                return False
            values[key] = value.decode("latin-1")
        host = values.get(b"host", "")
        parsed = urlsplit("http://" + host)
        return (
            parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
            and values.get(b"origin") == "http://" + host
            and values.get(b"x-mmm-dashboard") == "1"
            and values.get(b"sec-fetch-site", "same-origin") == "same-origin"
            and values.get(b"content-type", "").split(";")[0] == "application/json"
        )
    except (ValueError, TypeError, IndexError):
        return False


async def serve_asset(scope, send):
    """Only GET on exact bundled assets; never resolve a request path on disk."""
    headers = {k.lower(): v.decode("latin-1") for k, v in scope["headers"]}
    host = urlsplit("http://" + headers.get(b"host", "")).hostname
    allowed = host in {"127.0.0.1", "localhost", "::1"}
    origin = headers.get(b"origin")
    if origin and origin != "http://" + headers.get(b"host", ""):
        allowed = False
    name, kind = ASSETS[scope["path"]]
    body = (
        files("mmm_intelligence").joinpath("web", name).read_bytes()
        if allowed
        else b"Invalid host or origin"
    )
    await send(
        {
            "type": "http.response.start",
            "status": 200 if allowed else 421,
            "headers": [
                (b"content-type", (kind + "; charset=utf-8").encode()),
                (b"content-security-policy", CSP.encode()),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
                (b"x-frame-options", b"DENY"),
                (b"referrer-policy", b"no-referrer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
