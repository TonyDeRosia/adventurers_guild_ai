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
    assert str(exc.value) == "Ollama is not running. Start Ollama to use this model provider."


def test_ollama_logs_success_target(monkeypatch, capsys) -> None:
    adapter = OllamaAdapter(model="llama3", base_url="http://localhost:11434")

    def _fake_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/api/tags"):
            return _FakeResponse({"models": [{"name": "llama3:latest"}]})
        return _FakeResponse({"message": {"content": "The fog parts before you."}})

    monkeypatch.setattr("models.ollama_adapter.request.urlopen", _fake_urlopen)

    result = adapter.generate("advance", "system")

    out = capsys.readouterr().out
    assert result == "The fog parts before you."
    assert "target=http://localhost:11434/api/chat" in out
    assert "request_succeeded" in out


def test_ollama_readiness_unreachable_has_user_action(monkeypatch) -> None:
    adapter = OllamaAdapter(model="llama3", base_url="http://127.0.0.1:11434")

    def _raise(*args, **kwargs):
        raise URLError("[Errno 111] Connection refused")

    monkeypatch.setattr("models.ollama_adapter.request.urlopen", _raise)
    status = adapter.check_readiness()
    assert status["ready"] is False
    assert status["reachable"] is False
    assert status["model_exists"] is False
    assert status["user_message"] == "Ollama is not running. Start Ollama to use this model provider."


def test_ollama_generate_missing_model_has_pull_instruction(monkeypatch) -> None:
    adapter = OllamaAdapter(model="llama3", base_url="http://localhost:11434")
    monkeypatch.setattr(
        "models.ollama_adapter.request.urlopen",
        lambda *args, **kwargs: _FakeResponse({"models": [{"name": "mistral:latest"}]}),
    )

    with pytest.raises(ProviderUnavailableError) as exc:
        adapter.generate("look around", "system")

    assert str(exc.value) == "Model llama3 is not installed in Ollama. Run: ollama pull llama3"
