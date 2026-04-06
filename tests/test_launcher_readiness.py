from __future__ import annotations

from urllib.error import URLError

import run


class _FakeResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_browser_host_uses_loopback_for_wildcard_bind() -> None:
    assert run._browser_host("0.0.0.0") == "127.0.0.1"
    assert run._browser_host("::") == "127.0.0.1"
    assert run._browser_host("127.0.0.1") == "127.0.0.1"


def test_wait_for_web_health_retries_until_ok(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(url: str, timeout: float):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise URLError("connection refused")
        return _FakeResponse(200, '{"status": "ok"}')

    monkeypatch.setattr(run, "urlopen", fake_urlopen)
    monkeypatch.setattr(run.time, "sleep", lambda _: None)

    assert run._wait_for_web_health("http://127.0.0.1:8000", timeout_seconds=0.5) is True
    assert attempts["count"] == 3


def test_wait_for_web_health_times_out_on_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr(run, "urlopen", lambda url, timeout: _FakeResponse(200, '{"status": "starting"}'))
    monkeypatch.setattr(run.time, "sleep", lambda _: None)

    assert run._wait_for_web_health("http://127.0.0.1:8000", timeout_seconds=0.01) is False
