"""Network retries never bypass the pinned R archive integrity boundary."""

import hashlib
import importlib.util
import io
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


@pytest.fixture
def downloader():
    spec = importlib.util.spec_from_file_location(
        "install_r_binaries", Path(__file__).resolve().parents[1] / "examples/install_r_binaries.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retry_after_rate_limit_then_verified_download(downloader, monkeypatch, tmp_path):
    payload = b"official archive fixture"
    responses = iter(
        [
            urllib.error.HTTPError(
                "https://example.test", 429, "rate limit", {"Retry-After": "3"}, None
            ),
            urllib.error.HTTPError("https://example.test", 503, "temporary", {}, None),
            io.BytesIO(payload),
        ]
    )
    waits = []

    def request(*args, **kwargs):
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(downloader.urllib.request, "urlopen", request)
    monkeypatch.setattr(downloader.time, "sleep", waits.append)
    target = tmp_path / "package.zip"
    downloader.download_verified(
        "https://example.test", target, hashlib.sha256(payload).hexdigest()
    )
    assert target.read_bytes() == payload
    assert waits == [3, 4]


@pytest.mark.parametrize("status,attempts", [(404, 1), (429, 5), (503, 5)])
def test_errors_are_bounded_and_never_cached(downloader, monkeypatch, tmp_path, status, attempts):
    requests = []

    def request(*args, **kwargs):
        requests.append(args)
        raise urllib.error.HTTPError("https://example.test", status, "failure", {}, None)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", request)
    monkeypatch.setattr(downloader.time, "sleep", lambda delay: None)
    target = tmp_path / "package.zip"
    with pytest.raises(urllib.error.HTTPError):
        downloader.download_verified("https://example.test", target, "0" * 64)
    assert len(requests) == attempts
    assert not target.exists()


def test_bad_checksum_is_never_written_or_retried(downloader, monkeypatch, tmp_path):
    requests = []

    def request(*args, **kwargs):
        requests.append(args)
        return io.BytesIO(b"corrupt")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", request)
    target = tmp_path / "package.zip"
    with pytest.raises(ValueError, match="checksum mismatch"):
        downloader.download_verified("https://example.test", target, "0" * 64)
    assert len(requests) == 1
    assert not target.exists()


def test_actual_http_rate_limit_recovers_and_verifies(downloader, tmp_path):
    """Exercise urllib and real HTTP; the synthetic ZIP bytes are not model output."""
    payload = b"synthetic archive bytes"
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(429 if len(requests) == 1 else 200)
            self.end_headers()
            if len(requests) > 1:
                self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    target = tmp_path / "actual.zip"
    try:
        downloader.download_verified(
            f"http://127.0.0.1:{server.server_port}/package.zip",
            target,
            hashlib.sha256(payload).hexdigest(),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert requests == ["/package.zip", "/package.zip"]
    assert target.read_bytes() == payload
    assert list(tmp_path.glob("*.tmp")) == []
