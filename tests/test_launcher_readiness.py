from __future__ import annotations

import subprocess
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


def test_build_backend_command_source_mode(monkeypatch) -> None:
    monkeypatch.setattr(run.sys, "frozen", False, raising=False)
    monkeypatch.setattr(run.sys, "executable", "/usr/bin/python3", raising=False)

    command = run._build_backend_command("127.0.0.1", 8100)

    assert command[0] == "/usr/bin/python3"
    assert command[1].endswith("run.py")
    assert command[2:] == ["--backend-only", "--host", "127.0.0.1", "--port", "8100"]


def test_build_backend_command_frozen_mode(monkeypatch) -> None:
    monkeypatch.setattr(run.sys, "frozen", True, raising=False)
    monkeypatch.setattr(run.sys, "executable", "C:/App/AdventurerGuildAI.exe", raising=False)

    command = run._build_backend_command("127.0.0.1", 8000)

    assert command == [
        "C:/App/AdventurerGuildAI.exe",
        "--backend-only",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]


def test_stop_backend_process_terminates_running_process() -> None:
    class _FakeProcess:
        def __init__(self) -> None:
            self.terminated = False
            self._returncode = None

        def poll(self):
            return self._returncode

        def terminate(self):
            self.terminated = True
            self._returncode = 0

        def wait(self, timeout: float):
            return 0

    fake = _FakeProcess()
    run._stop_backend_process(fake)  # type: ignore[arg-type]
    assert fake.terminated is True


def test_stop_backend_process_kills_when_terminate_times_out() -> None:
    class _FakeProcess:
        def __init__(self) -> None:
            self.killed = False
            self._returncode = None

        def poll(self):
            return self._returncode

        def terminate(self):
            return None

        def wait(self, timeout: float):
            if not self.killed:
                raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
            self._returncode = 1
            return 1

        def kill(self):
            self.killed = True

    fake = _FakeProcess()
    run._stop_backend_process(fake)  # type: ignore[arg-type]
    assert fake.killed is True
