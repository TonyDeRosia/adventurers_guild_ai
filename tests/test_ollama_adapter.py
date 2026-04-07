from __future__ import annotations

import json
from urllib.error import URLError

import pytest

from models.base import ProviderUnavailableError
from models.ollama_adapter import OllamaAdapter


class _FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._body).encode("utf-8")


def test_ollama_logs_request_and_failure_reason(monkeypatch, capsys) -> None:
    adapter = OllamaAdapter(model="llama3", base_url="http://127.0.0.1:11434")

    def _raise(*args, **kwargs):
        raise URLError("[Errno 111] Connection refused")

    monkeypatch.setattr("models.ollama_adapter.request.urlopen", _raise)

    with pytest.raises(ProviderUnavailableError) as exc:
        adapter.generate("look around", "system")

    out = capsys.readouterr().out
    assert "provider=ollama" in out
    assert "model=llama3" in out
    assert "base_url=http://127.0.0.1:11434" in out
    assert "target=http://127.0.0.1:11434/api/chat" in out
    assert "Connection refused" in out
    assert "Could not reach local Ollama at http://127.0.0.1:11434/api/chat" in str(exc.value)


def test_ollama_logs_success_target(monkeypatch, capsys) -> None:
    adapter = OllamaAdapter(model="llama3", base_url="http://localhost:11434")
    monkeypatch.setattr(
        "models.ollama_adapter.request.urlopen",
        lambda *args, **kwargs: _FakeResponse({"message": {"content": "The fog parts before you."}}),
    )

    result = adapter.generate("advance", "system")

    out = capsys.readouterr().out
    assert result == "The fog parts before you."
    assert "target=http://localhost:11434/api/chat" in out
    assert "request_succeeded" in out
