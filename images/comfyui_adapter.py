"""ComfyUI integration hook.

Keeps HTTP wiring isolated for easy replacement or extension.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
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
        debug_root = (self.output_dir.parent if self.output_dir else Path.cwd()) / "logs" / "comfy_debug"
        self.debug_dir = debug_root.resolve()
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.last_debug_snapshot: dict[str, object] = {
            "debug_dir": str(self.debug_dir),
            "last_payload_path": "",
            "last_response_path": "",
            "last_history_path": "",
            "last_error": "",
            "last_prompt_id": "",
        }

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
        self.debug_dir = workflow_manager.debug_dir
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.last_debug_snapshot["debug_dir"] = str(self.debug_dir)

        workflow_id = request_payload.workflow_id
        try:
            workflow_request = self._normalize_request(request_payload)
            workflow = workflow_manager.build_workflow(workflow_request)
            workflow_manager.validate_workflow(workflow)
            bindings = workflow_manager.inspect_bindings(workflow)
            print("[image-pipeline] workflow validated")
            print(f"[image-pipeline] payload_summary=nodes:{len(workflow)} workflow_id:{workflow_id}")
        except Exception as exc:
            self.last_debug_snapshot["last_error"] = f"ComfyUI workflow invalid: {exc}"
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                error=f"ComfyUI workflow invalid: {exc}",
                metadata={"base_url": self.base_url, "error_category": "invalid_workflow"},
            )

        payload = {"prompt": workflow}
        prompt_node_count = len(workflow) if isinstance(workflow, dict) else 0
        self._debug_log(f"prompt_endpoint={self.base_url}/prompt")
        self._debug_log(f"payload_top_keys={list(payload.keys())}")
        self._debug_log(f"payload_prompt_node_count={prompt_node_count}")
        self._debug_log(f"payload_preview={json.dumps(payload, ensure_ascii=False)[:600]}")
        payload_path = self._write_debug_artifact("comfy_prompt_payload.json", payload)
        self.last_debug_snapshot["last_payload_path"] = str(payload_path)

        req = request.Request(
            f"{self.base_url}/prompt",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                response_text = response.read().decode("utf-8")
            body = json.loads(response_text)
            self._debug_log(f"prompt_response_status=200")
            self._debug_log(f"prompt_response_body={response_text[:600]}")
            response_path = self._write_debug_artifact("comfy_response_last.json", body)
            self.last_debug_snapshot["last_response_path"] = str(response_path)
        except HTTPError as exc:
            return self._http_error_result(exc, workflow_id)
        except Exception as exc:
            self.last_debug_snapshot["last_error"] = str(exc)
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                error=f"ComfyUI request failed: {exc}",
                metadata={"base_url": self.base_url, "error_category": "request_failed"},
            )

        prompt_id = str(body.get("prompt_id", "")).strip()
        if not prompt_id:
            self.last_debug_snapshot["last_error"] = "missing prompt_id"
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                error="ComfyUI did not return a prompt_id.",
                metadata={"base_url": self.base_url, "error_category": "bad_response"},
            )

        self.last_debug_snapshot["last_prompt_id"] = prompt_id
        self._debug_log(f"prompt_id={prompt_id}")
        self._debug_log(f"history_poll_start={self.base_url}/history/{prompt_id}")
        image_info, history_error = self._wait_for_generated_image(prompt_id, bindings.save_image_node_ids)
        if not image_info:
            self.last_debug_snapshot["last_error"] = history_error or "missing output"
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                prompt_id=prompt_id,
                error=history_error or "ComfyUI accepted the prompt but no image output was found in history.",
                metadata={"base_url": self.base_url, "error_category": "missing_output", "save_nodes": bindings.save_image_node_ids},
            )

        saved_path = self._download_output_image(image_info)
        if not saved_path:
            self.last_debug_snapshot["last_error"] = "download failed"
            return ImageGenerationResult(
                success=False,
                workflow_id=workflow_id,
                prompt_id=prompt_id,
                error="ComfyUI generated an image but it could not be downloaded.",
                metadata={"base_url": self.base_url, "error_category": "download_failed", "image_info": image_info},
            )

        print("[image-pipeline] image generated successfully")
        self.last_debug_snapshot["last_error"] = ""
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
            preferred_stem = Path(preferred_checkpoint).stem.lower()
            for item in available:
                if Path(item).stem.lower() == preferred_stem:
                    return item, available
            normalized = re.sub(r"[^a-z0-9]+", "", preferred_stem)
            if normalized:
                for item in available:
                    model_normalized = re.sub(r"[^a-z0-9]+", "", Path(item).stem.lower())
                    if model_normalized.startswith(normalized):
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
        poll_attempt = 0
        while time.time() < deadline:
            poll_attempt += 1
            image_info, history_error = self._fetch_history_image(prompt_id, save_node_ids, poll_attempt)
            if image_info:
                self._debug_log(f"history_image_found_at_attempt={poll_attempt}")
                return image_info, None
            if history_error:
                last_error = history_error
            time.sleep(1)
        self._debug_log(f"history_timeout_seconds={timeout_seconds} prompt_id={prompt_id}")
        return None, last_error

    def _fetch_history_image(self, prompt_id: str, save_node_ids: list[str], poll_attempt: int) -> tuple[dict[str, str] | None, str | None]:
        req = request.Request(f"{self.base_url}/history/{prompt_id}")
        try:
            with request.urlopen(req, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None, None

        self._debug_log(f"history_poll_attempt={poll_attempt} prompt_id={prompt_id}")
        payload = body.get(prompt_id, {})
        if not isinstance(payload, dict):
            return None, None
        status = payload.get("status")
        if isinstance(status, dict):
            status_str = str(status.get("status_str", ""))
            self._debug_log(f"history_status={status_str}")
            messages = status.get("messages")
            if status_str.lower() in {"error", "failed"}:
                if isinstance(messages, list) and messages:
                    return None, f"ComfyUI generation failed: {messages[-1]}"
                return None, "ComfyUI generation failed."

        outputs = payload.get("outputs", {})
        if not isinstance(outputs, dict):
            return None, None

        output_node_ids = list(outputs.keys())
        self._debug_log(f"history_output_node_ids={output_node_ids}")
        ordered_node_ids = [node_id for node_id in save_node_ids if node_id in outputs]
        if not ordered_node_ids:
            ordered_node_ids = output_node_ids

        for node_id in ordered_node_ids:
            node_data = outputs.get(node_id)
            if not isinstance(node_data, dict):
                continue
            images = node_data.get("images")
            if not isinstance(images, list):
                continue
            for image in images:
                if isinstance(image, dict) and image.get("filename"):
                    image_info = {
                        "filename": str(image.get("filename", "")),
                        "subfolder": str(image.get("subfolder", "")),
                        "type": str(image.get("type", "output")),
                    }
                    self._debug_log(
                        "history_image="
                        f"filename:{image_info['filename']} subfolder:{image_info['subfolder']} type:{image_info['type']}"
                    )
                    history_path = self._write_debug_artifact("comfy_history_last.json", body)
                    self.last_debug_snapshot["last_history_path"] = str(history_path)
                    return image_info, None
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
        headers_dict = dict(exc.headers.items()) if exc.headers else {}
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""

        parsed_body: object = body_text
        response_filename = "comfy_response_last.txt"
        try:
            parsed_body = json.loads(body_text)
            response_filename = "comfy_response_last.json"
            self._debug_log(f"http_error_body_json={json.dumps(parsed_body, ensure_ascii=False)[:600]}")
        except Exception:
            self._debug_log(f"http_error_body_text={body_text[:600]}")

        response_path = self._write_debug_artifact(response_filename, parsed_body)
        self.last_debug_snapshot["last_response_path"] = str(response_path)
        self._debug_log(f"http_error_status={exc.code}")
        self._debug_log(f"http_error_headers={headers_dict}")

        error_message, error_category = self._classify_error(exc.code, body_text)
        print(f"[image-pipeline] request failed status={exc.code} reason={error_category}")
        self.last_debug_snapshot["last_error"] = error_message
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

    def _write_debug_artifact(self, filename: str, payload: object) -> Path:
        target = self.debug_dir / filename
        if isinstance(payload, str):
            serialized = payload
        else:
            serialized = json.dumps(payload, indent=2, ensure_ascii=False)
        target.write_text(serialized, encoding="utf-8")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stamped = self.debug_dir / f"{target.stem}_{timestamp}{target.suffix}"
        stamped.write_text(serialized, encoding="utf-8")
        return target

    def _debug_log(self, message: str) -> None:
        print(f"[comfy-debug] {message}")

    def get_debug_snapshot(self) -> dict[str, object]:
        return dict(self.last_debug_snapshot)
