"""Workflow template loader/injector for image generation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from images.base import ImageGenerationRequest


class WorkflowManager:
    """Loads workflow templates from data/workflows and injects runtime prompt values."""

    def __init__(self, workflow_dir: Path) -> None:
        self.workflow_dir = workflow_dir
        self.workflow_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[str]:
        return sorted(path.stem for path in self.workflow_dir.glob("*.json"))

    def load_template(self, workflow_id: str) -> dict[str, Any]:
        path = self.workflow_dir / f"{workflow_id}.json"
        if not path.exists():
            raise ValueError(f"Workflow template '{workflow_id}' not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def build_workflow(self, request: ImageGenerationRequest) -> dict[str, Any]:
        template = self.load_template(request.workflow_id)
        context = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "seed": request.parameters.get("seed", 42),
            "steps": request.parameters.get("steps", 28),
            "cfg": request.parameters.get("cfg", 7.0),
            "width": request.parameters.get("width", 768),
            "height": request.parameters.get("height", 512),
            "sampler_name": request.parameters.get("sampler_name", "euler"),
            "scheduler": request.parameters.get("scheduler", "normal"),
            "denoise": request.parameters.get("denoise", 1.0),
            "checkpoint": request.parameters.get("checkpoint", ""),
            **request.parameters,
        }

        workflow = _inject_string_tokens(template, context)
        node_updates = request.parameters.get("node_updates", {}) if isinstance(request.parameters, dict) else {}
        if node_updates:
            _apply_node_updates(workflow, node_updates)
        return workflow

    def validate_workflow(self, workflow: dict[str, Any]) -> None:
        if not isinstance(workflow, dict):
            raise ValueError("Workflow payload must be a dictionary")
        required_nodes = {
            "CheckpointLoaderSimple": False,
            "CLIPTextEncode": False,
            "KSampler": False,
            "VAEDecode": False,
            "SaveImage": False,
        }
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("class_type", "")).strip()
            if class_type in required_nodes:
                required_nodes[class_type] = True
        missing = [node for node, present in required_nodes.items() if not present]
        if missing:
            raise ValueError(f"Workflow missing required nodes: {', '.join(missing)}")


_TOKEN_PATTERN = re.compile(r"^\{\{([a-zA-Z0-9_]+)\}\}$")


def _inject_string_tokens(payload: Any, context: dict[str, Any]) -> Any:
    if isinstance(payload, dict):
        return {key: _inject_string_tokens(value, context) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_inject_string_tokens(value, context) for value in payload]
    if isinstance(payload, str):
        token_match = _TOKEN_PATTERN.match(payload)
        if token_match:
            key = token_match.group(1)
            return context.get(key, payload)
        output = payload
        for key, value in context.items():
            output = output.replace(f"{{{{{key}}}}}", str(value))
        return output
    return payload


def _apply_node_updates(workflow: dict[str, Any], updates: dict[str, dict[str, Any]]) -> None:
    for node_id, patch in updates.items():
        node = workflow.get(node_id)
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        if isinstance(inputs, dict):
            for key, value in patch.items():
                inputs[key] = value
