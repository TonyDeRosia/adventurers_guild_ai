"""Ollama-compatible local model adapter.

This adapter is intentionally lightweight: it can be enabled later once a local
Ollama instance is available.
"""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib import request

from models.base import ChatMessage, NarrationModelAdapter


class OllamaAdapter(NarrationModelAdapter):
    provider_name = "ollama"

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434", timeout_seconds: int = 45) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str, system_prompt: str = "", history: list[ChatMessage] | None = None) -> str:
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
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            return f"[Ollama unavailable] Could not reach local Ollama at {self.base_url}: {exc}"
        return body.get("message", {}).get("content", "").strip()

    def list_local_models(self) -> list[str]:
        req = request.Request(f"{self.base_url}/api/tags")
        try:
            with request.urlopen(req, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except URLError:
            return []
        return [entry.get("name", "") for entry in body.get("models", []) if entry.get("name")]
