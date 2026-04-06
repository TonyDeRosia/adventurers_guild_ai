"""ComfyUI integration hook.

Keeps HTTP wiring isolated for easy replacement or extension.
"""

from __future__ import annotations

import json
from urllib import request

from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter
from images.workflow_manager import WorkflowManager


class ComfyUIAdapter(ImageGeneratorAdapter):
    def __init__(self, base_url: str = "http://localhost:8188") -> None:
        self.base_url = base_url.rstrip("/")

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
