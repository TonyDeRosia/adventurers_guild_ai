"""ComfyUI integration hook.

Keeps HTTP wiring isolated for easy replacement or extension.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError

from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter
from images.workflow_manager import WorkflowManager


class ComfyUIAdapter(ImageGeneratorAdapter):
    def __init__(self, base_url: str = "http://localhost:8188", output_dir: Path | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

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
        print("[image-pipeline] request started")
        print(f"[image-pipeline] endpoint={self.base_url}/prompt")

        workflow_id = request_payload.workflow_id
        try:
            workflow_request = self._normalize_request(request_payload)
            workflow = workflow_manager.build_workflow(workflow_request)
            workflow_manager.validate_workflow(workflow)
            bindings = workflow_manager.inspect_bindings(workflow)
            print("[image-pipeline] workflow validated")
            print(f"[image-pipeline] payload_summary=nodes:{len(workflow)} workflow_id:{workflow_id}")
        except Exception as exc:
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                error=f"ComfyUI workflow invalid: {exc}",
                metadata={"base_url": self.base_url, "error_category": "invalid_workflow"},
            )

        payload = {"prompt": workflow}
        req = request.Request(
            f"{self.base_url}/prompt",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return self._http_error_result(exc, workflow_id)
        except Exception as exc:
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                error=f"ComfyUI request failed: {exc}",
                metadata={"base_url": self.base_url, "error_category": "request_failed"},
            )

        prompt_id = str(body.get("prompt_id", "")).strip()
        if not prompt_id:
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                error="ComfyUI did not return a prompt_id.",
                metadata={"base_url": self.base_url, "error_category": "bad_response"},
            )

        image_info, history_error = self._wait_for_generated_image(prompt_id, bindings.save_image_node_ids)
        if not image_info:
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                prompt_id=prompt_id,
                error=history_error or "ComfyUI accepted the prompt but no image output was found in history.",
                metadata={"base_url": self.base_url, "error_category": "missing_output", "save_nodes": bindings.save_image_node_ids},
            )

        saved_path = self._download_output_image(image_info)
        if not saved_path:
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                prompt_id=prompt_id,
                error="ComfyUI generated an image but it could not be downloaded.",
                metadata={"base_url": self.base_url, "error_category": "download_failed", "image_info": image_info},
            )

        print("[image-pipeline] image generated successfully")
        return ImageGenerationResult(
            success=True,
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            result_path=str(saved_path),
            metadata={"base_url": self.base_url, "image": image_info, "save_nodes": bindings.save_image_node_ids},
        )

    def _normalize_request(self, request_payload: ImageGenerationRequest) -> ImageGenerationRequest:
        params = dict(request_payload.parameters or {})
        params.setdefault("seed", int(time.time()))
        params.setdefault("steps", 28)
        params.setdefault("cfg", 7.0)
        params.setdefault("width", 768)
        params.setdefault("height", 512)
        params.setdefault("sampler_name", "euler")
        params.setdefault("scheduler", "normal")
        params.setdefault("denoise", 1.0)

        preferred_checkpoint = str(params.get("checkpoint", "")).strip()
        selected_checkpoint, available_checkpoints = self._resolve_checkpoint(preferred_checkpoint)
        if not selected_checkpoint:
            raise ValueError("No ComfyUI checkpoint models were found. Add a checkpoint in models/checkpoints.")
        params["checkpoint"] = selected_checkpoint
        return ImageGenerationRequest(
            workflow_id=request_payload.workflow_id,
            prompt=request_payload.prompt,
            negative_prompt=request_payload.negative_prompt,
            parameters={**params, "available_checkpoints": available_checkpoints},
        )

    def _resolve_checkpoint(self, preferred_checkpoint: str) -> tuple[str | None, list[str]]:
        available = self._list_checkpoints()
        if not available:
            return None, []
        if preferred_checkpoint:
            preferred_lower = preferred_checkpoint.lower()
            for item in available:
                if item.lower() == preferred_lower:
                    return item, available
        for item in available:
            if "dreamshaper" in item.lower():
                return item, available
        return available[0], available

    def _list_checkpoints(self) -> list[str]:
        req = request.Request(f"{self.base_url}/object_info/CheckpointLoaderSimple")
        try:
            with request.urlopen(req, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
            return [str(item) for item in body.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0] if str(item).strip()]
        except Exception:
            return []

    def _wait_for_generated_image(self, prompt_id: str, save_node_ids: list[str], timeout_seconds: int = 90) -> tuple[dict[str, str] | None, str | None]:
        deadline = time.time() + timeout_seconds
        last_error: str | None = None
        while time.time() < deadline:
            image_info, history_error = self._fetch_history_image(prompt_id, save_node_ids)
            if image_info:
                return image_info, None
            if history_error:
                last_error = history_error
            time.sleep(1)
        return None, last_error

    def _fetch_history_image(self, prompt_id: str, save_node_ids: list[str]) -> tuple[dict[str, str] | None, str | None]:
        req = request.Request(f"{self.base_url}/history/{prompt_id}")
        try:
            with request.urlopen(req, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None, None

        payload = body.get(prompt_id, {})
        if not isinstance(payload, dict):
            return None, None
        status = payload.get("status")
        if isinstance(status, dict):
            status_str = str(status.get("status_str", ""))
            messages = status.get("messages")
            if status_str.lower() in {"error", "failed"}:
                if isinstance(messages, list) and messages:
                    return None, f"ComfyUI generation failed: {messages[-1]}"
                return None, "ComfyUI generation failed."

        outputs = payload.get("outputs", {})
        if not isinstance(outputs, dict):
            return None, None

        ordered_node_ids = [node_id for node_id in save_node_ids if node_id in outputs]
        if not ordered_node_ids:
            ordered_node_ids = list(outputs.keys())

        for node_id in ordered_node_ids:
            node_data = outputs.get(node_id)
            if not isinstance(node_data, dict):
                continue
            images = node_data.get("images")
            if not isinstance(images, list):
                continue
            for image in images:
                if isinstance(image, dict) and image.get("filename"):
                    return {
                        "filename": str(image.get("filename", "")),
                        "subfolder": str(image.get("subfolder", "")),
                        "type": str(image.get("type", "output")),
                    }, None
        return None, None

    def _download_output_image(self, image_info: dict[str, str]) -> Path | None:
        if not self.output_dir:
            return None
        params = parse.urlencode(
            {
                "filename": image_info.get("filename", ""),
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "output"),
            }
        )
        req = request.Request(f"{self.base_url}/view?{params}")
        try:
            with request.urlopen(req, timeout=30) as response:
                content = response.read()
        except Exception:
            return None

        suffix = Path(image_info.get("filename", "output.png")).suffix or ".png"
        output_path = self.output_dir / f"comfyui_{uuid.uuid4().hex}{suffix}"
        output_path.write_bytes(content)
        return output_path

    def _http_error_result(self, exc: HTTPError, workflow_id: str) -> ImageGenerationResult:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        error_message, error_category = self._classify_error(exc.code, body_text)
        print(f"[image-pipeline] request failed status={exc.code} reason={error_category}")
        return ImageGenerationResult(
            success=False,
            workflow_id=workflow_id,
            error=error_message,
            metadata={
                "base_url": self.base_url,
                "status_code": exc.code,
                "error_category": error_category,
                "error_body": body_text[:2000],
            },
        )

    def _classify_error(self, status_code: int, body_text: str) -> tuple[str, str]:
        lower = body_text.lower()
        category = "bad_request" if status_code == 400 else "http_error"
        if "invalid prompt" in lower or "invalid workflow" in lower:
            category = "invalid_workflow"
        elif "missing" in lower and ("input" in lower or "node" in lower):
            category = "missing_required_node_or_input"
        elif "ckpt_name" in lower or "checkpoint" in lower:
            category = "invalid_checkpoint"
        elif "no such file" in lower or "not found" in lower:
            category = "missing_model_file"
        elif "not allowed" in lower or "404" in lower:
            category = "bad_endpoint"

        detail = body_text.strip() or f"HTTP {status_code}"
        return f"ComfyUI request failed ({category}): {detail}", category
