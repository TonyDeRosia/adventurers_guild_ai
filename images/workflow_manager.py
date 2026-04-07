"""Workflow template loader/injector for image generation."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from images.base import ImageGenerationRequest


@dataclass
class WorkflowBindings:
    positive_prompt_node_ids: list[str]
    negative_prompt_node_ids: list[str]
    checkpoint_node_ids: list[str]
    save_image_node_ids: list[str]


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

        workflow = _inject_string_tokens(copy.deepcopy(template), context)
        node_updates = request.parameters.get("node_updates", {}) if isinstance(request.parameters, dict) else {}
        if node_updates:
            _apply_node_updates(workflow, node_updates)
        bindings = self.inspect_bindings(workflow)
        self._apply_dynamic_patches(workflow, bindings, request)
        return workflow

    def validate_workflow(self, workflow: dict[str, Any]) -> None:
        if not isinstance(workflow, dict):
            raise ValueError("Workflow payload must be a dictionary")
        node_count = 0
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            if isinstance(node.get("inputs"), dict):
                node_count += 1
        if node_count == 0:
            raise ValueError("Workflow does not contain any executable nodes.")
        bindings = self.inspect_bindings(workflow)
        if not bindings.save_image_node_ids:
            raise ValueError("Workflow does not contain a save/image output node.")

    def inspect_bindings(self, workflow: dict[str, Any]) -> WorkflowBindings:
        positive_nodes: list[str] = []
        negative_nodes: list[str] = []
        checkpoint_nodes: list[str] = []
        save_nodes: list[str] = []

        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("class_type", "")).strip()
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if class_type.lower().startswith("checkpointloader") and "ckpt_name" in inputs:
                checkpoint_nodes.append(str(node_id))
            if _is_save_image_like_node(class_type, inputs):
                save_nodes.append(str(node_id))

        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            positive_link = _extract_link_node_id(inputs.get("positive"))
            negative_link = _extract_link_node_id(inputs.get("negative"))
            if positive_link:
                positive_nodes.append(positive_link)
            if negative_link:
                negative_nodes.append(negative_link)

        if not positive_nodes or not negative_nodes:
            text_node_ids = [
                str(node_id)
                for node_id, node in workflow.items()
                if isinstance(node, dict)
                and isinstance(node.get("inputs"), dict)
                and "text" in node["inputs"]
            ]
            if text_node_ids and not positive_nodes:
                positive_nodes = [text_node_ids[0]]
            if len(text_node_ids) >= 2 and not negative_nodes:
                negative_nodes = [text_node_ids[1]]
            elif text_node_ids and not negative_nodes:
                negative_nodes = [text_node_ids[0]]

        return WorkflowBindings(
            positive_prompt_node_ids=_unique(positive_nodes),
            negative_prompt_node_ids=_unique(negative_nodes),
            checkpoint_node_ids=_unique(checkpoint_nodes),
            save_image_node_ids=_unique(save_nodes),
        )

    def _apply_dynamic_patches(
        self,
        workflow: dict[str, Any],
        bindings: WorkflowBindings,
        request: ImageGenerationRequest,
    ) -> None:
        for node_id in bindings.positive_prompt_node_ids:
            _set_node_input(workflow, node_id, "text", request.prompt)
        for node_id in bindings.negative_prompt_node_ids:
            _set_node_input(workflow, node_id, "text", request.negative_prompt)
        checkpoint = str(request.parameters.get("checkpoint", "")).strip()
        if checkpoint:
            for node_id in bindings.checkpoint_node_ids:
                _set_node_input(workflow, node_id, "ckpt_name", checkpoint)

        sampler_inputs = {
            "seed": request.parameters.get("seed"),
            "steps": request.parameters.get("steps"),
            "cfg": request.parameters.get("cfg"),
            "sampler_name": request.parameters.get("sampler_name"),
            "scheduler": request.parameters.get("scheduler"),
            "denoise": request.parameters.get("denoise"),
        }
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            for key, value in sampler_inputs.items():
                if value is not None and key in inputs:
                    inputs[key] = value
            if "width" in inputs and request.parameters.get("width") is not None:
                inputs["width"] = request.parameters.get("width")
            if "height" in inputs and request.parameters.get("height") is not None:
                inputs["height"] = request.parameters.get("height")


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


def _set_node_input(workflow: dict[str, Any], node_id: str, key: str, value: Any) -> None:
    node = workflow.get(node_id)
    if not isinstance(node, dict):
        return
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        return
    if key in inputs:
        inputs[key] = value


def _extract_link_node_id(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    return None


def _is_save_image_like_node(class_type: str, inputs: dict[str, Any]) -> bool:
    lowered = class_type.lower()
    if lowered in {"saveimage", "saveimagewebsocket", "previewimage"}:
        return True
    return "images" in inputs and ("filename_prefix" in inputs or "filename" in inputs)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        output.append(value)
        seen.add(value)
    return output
