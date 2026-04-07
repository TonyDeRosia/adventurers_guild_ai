"""ComfyUI integration hook.

Keeps HTTP wiring isolated for easy replacement or extension.
"""

from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter
from images.workflow_manager import WorkflowManager


class ComfyUIAdapter(ImageGeneratorAdapter):
    def __init__(self, base_url: str = "http://localhost:8188") -> None:
        self.base_url = base_url.rstrip("/")



    def check_readiness(self) -> dict[str, object]:
        req = request.Request(f"{self.base_url}/system_stats")
        try:
            with request.urlopen(req, timeout=10):
                pass
        except (URLError, HTTPError, json.JSONDecodeError) as exc:
            reason = str(getattr(exc, "reason", exc))
            return {
                "provider": "comfyui",
                "base_url": self.base_url,
                "reachable": False,
                "ready": False,
                "status_level": "error",
                "user_message": "ComfyUI is not reachable at the configured address.",
                "next_action": "Start ComfyUI, then click Recheck.",
                "error": reason,
            }

        return {
            "provider": "comfyui",
            "base_url": self.base_url,
            "reachable": True,
            "ready": True,
            "status_level": "ready",
            "user_message": "ComfyUI is reachable and ready for image generation.",
            "next_action": "No action needed.",
            "error": "",
        }

    def generate(self, request_payload: ImageGenerationRequest, workflow_manager: WorkflowManager) -> ImageGenerationResult:
        workflow = workflow_manager.build_workflow(request_payload)
        payload = {"prompt": workflow}
        req = request.Request(
            f"{self.base_url}/prompt",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return ImageGenerationResult(
                success=False,
                workflow_id=request_payload.workflow_id,
                error=f"ComfyUI request failed: {exc}",
                metadata={"base_url": self.base_url},
            )

        return ImageGenerationResult(
            success=True,
            workflow_id=request_payload.workflow_id,
            prompt_id=str(body.get("prompt_id", "submitted")),
            result_path=body.get("result_path"),
            metadata={"base_url": self.base_url},
        )
