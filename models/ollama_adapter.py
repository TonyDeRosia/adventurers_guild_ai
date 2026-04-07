"""Ollama-compatible local model adapter.

This adapter is intentionally lightweight: it can be enabled later once a local
Ollama instance is available.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.error import URLError
from urllib import request

from models.base import ChatMessage, NarrationModelAdapter, ProviderUnavailableError


class OllamaAdapter(NarrationModelAdapter):
    provider_name = "ollama"

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434", timeout_seconds: int = 45) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str, system_prompt: str = "", history: list[ChatMessage] | None = None) -> str:
        target = f"{self.base_url}/api/chat"
        print(
            f"[ollama] provider={self.provider_name} model={self.model} base_url={self.base_url} "
            f"target={target} timeout_seconds={self.timeout_seconds}"
        )
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        for item in history or []:
            if item.content.strip():
                messages.append({"role": item.role, "content": item.content.strip()})
        messages.append({"role": "user", "content": prompt.strip()})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        req = request.Request(
            target,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            reason = f"HTTP {exc.code} {exc.reason}"
            print(
                f"[ollama] request_failed provider={self.provider_name} model={self.model} target={target} "
                f"reason={reason}"
            )
            raise ProviderUnavailableError(f"Ollama request to {target} failed: {reason}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            print(
                f"[ollama] request_failed provider={self.provider_name} model={self.model} target={target} "
                f"reason={reason}"
            )
            raise ProviderUnavailableError(f"Could not reach local Ollama at {target}: {reason}") from exc
        except json.JSONDecodeError as exc:
            print(
                f"[ollama] request_failed provider={self.provider_name} model={self.model} target={target} "
                f"reason=invalid_json_response"
            )
            raise ProviderUnavailableError(f"Ollama at {target} returned invalid JSON: {exc}") from exc
        generated = body.get("message", {}).get("content", "").strip()
        if not generated:
            raise ProviderUnavailableError("Ollama returned an empty response")
        print(f"[ollama] request_succeeded provider={self.provider_name} model={self.model} target={target}")
        return generated

    def list_local_models(self) -> list[str]:
        req = request.Request(f"{self.base_url}/api/tags")
        try:
            with request.urlopen(req, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except URLError:
            return []
        return [entry.get("name", "") for entry in body.get("models", []) if entry.get("name")]
