"""Ollama-compatible local model adapter.

This adapter is intentionally lightweight: it can be enabled later once a local
Ollama instance is available.
"""

from __future__ import annotations

import json
from urllib import request

from models.base import NarrationModelAdapter


class OllamaAdapter(NarrationModelAdapter):
    provider_name = "ollama"

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\n{prompt}".strip(),
            "stream": False,
        }
        req = request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body.get("response", "")
