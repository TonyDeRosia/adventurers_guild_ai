"""ComfyUI integration hook.

Keeps HTTP wiring isolated for easy replacement or extension.
"""

from __future__ import annotations

import json
from urllib import request

from images.base import ImageGeneratorAdapter


class ComfyUIAdapter(ImageGeneratorAdapter):
    def __init__(self, base_url: str = "http://localhost:8188") -> None:
        self.base_url = base_url.rstrip("/")

    def generate_scene_image(self, prompt: str) -> str:
        payload = {"prompt": prompt}
        req = request.Request(
            f"{self.base_url}/prompt",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body.get("prompt_id", "submitted"))
