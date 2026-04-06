from __future__ import annotations

import webbrowser
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

    ready, reason = run._wait_for_web_health("http://127.0.0.1:8000", timeout_seconds=0.5)
    assert ready is True
    assert reason == "ready"
    assert attempts["count"] == 3


def test_wait_for_web_health_times_out_on_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr(run, "urlopen", lambda url, timeout: _FakeResponse(200, '{"status": "starting"}'))
    monkeypatch.setattr(run.time, "sleep", lambda _: None)

    ready, reason = run._wait_for_web_health("http://127.0.0.1:8000", timeout_seconds=0.01)
    assert ready is False
    assert reason == "health response did not include status ok"


def test_try_launch_browser_windows_prefers_startfile(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(run.platform, "system", lambda: "Windows")
    monkeypatch.setattr(run.os, "startfile", lambda url: calls.append(url), raising=False)

    result = run._try_launch_browser("http://127.0.0.1:8000")

    assert result.success is True
    assert result.method == "os.startfile"
    assert calls == ["http://127.0.0.1:8000"]


def test_try_launch_browser_windows_falls_back_to_cmd_start(monkeypatch) -> None:
    monkeypatch.setattr(run.platform, "system", lambda: "Windows")

    def broken_startfile(_url: str) -> None:
        raise OSError("shell association missing")

    popen_calls: list[list[str]] = []
    monkeypatch.setattr(run.os, "startfile", broken_startfile, raising=False)
    monkeypatch.setattr(
        run.subprocess,
        "Popen",
        lambda cmd, stdout, stderr: popen_calls.append(cmd),
    )

    result = run._try_launch_browser("http://127.0.0.1:8000")

    assert result.success is True
    assert result.method == "cmd start"
    assert popen_calls == [["cmd", "/c", "start", "", "http://127.0.0.1:8000"]]


def test_try_launch_browser_reports_failure_reason(monkeypatch) -> None:
    monkeypatch.setattr(run.platform, "system", lambda: "Windows")

    def broken_startfile(_url: str) -> None:
        raise OSError("startfile failed")

    def broken_popen(_cmd, stdout, stderr):
        raise OSError("cmd start failed")

    monkeypatch.setattr(run.os, "startfile", broken_startfile, raising=False)
    monkeypatch.setattr(run.subprocess, "Popen", broken_popen)

    result = run._try_launch_browser("http://127.0.0.1:8000")

    assert result.success is False
    assert result.method == "os.startfile -> cmd start"
    assert "startfile failed" in result.reason
    assert "cmd start failed" in result.reason


def test_try_launch_browser_non_windows_uses_webbrowser(monkeypatch) -> None:
    monkeypatch.setattr(run.platform, "system", lambda: "Linux")
    monkeypatch.setattr(run.webbrowser, "open", lambda url: url == "http://127.0.0.1:8000")

    result = run._try_launch_browser("http://127.0.0.1:8000")

    assert result.success is True
    assert result.method == "webbrowser.open"


def test_try_launch_browser_non_windows_reports_webbrowser_error(monkeypatch) -> None:
    monkeypatch.setattr(run.platform, "system", lambda: "Linux")

    def broken_open(_url: str) -> bool:
        raise webbrowser.Error("no browser registered")

    monkeypatch.setattr(run.webbrowser, "open", broken_open)

    result = run._try_launch_browser("http://127.0.0.1:8000")

    assert result.success is False
    assert result.method == "webbrowser.open"
    assert "no browser registered" in result.reason
