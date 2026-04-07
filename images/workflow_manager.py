"""Workflow template loader/injector for image generation."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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
        self.debug_dir = (self.workflow_dir.parent / "logs" / "comfy_debug").resolve()
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.last_debug_info: dict[str, Any] = {}

    def list_templates(self) -> list[str]:
        return sorted(path.stem for path in self.workflow_dir.glob("*.json"))

    def load_template(self, workflow_id: str) -> dict[str, Any]:
        path = self.workflow_dir / f"{workflow_id}.json"
        abs_path = path.resolve()
        exists = path.exists()
        size_bytes = path.stat().st_size if exists else 0
        self._debug_log(f"workflow_path={abs_path}")
        self._debug_log(f"workflow_exists={exists}")
        self._debug_log(f"workflow_size={size_bytes}")
        if not exists:
            raise ValueError(f"Workflow template '{workflow_id}' not found")
        payload = json.loads(path.read_text(encoding="utf-8"))
        format_name, format_reason = detect_workflow_format(payload)
        top_keys = list(payload.keys()) if isinstance(payload, dict) else []
        self._debug_log(f"workflow_top_keys={top_keys}")
        self._debug_log(f"workflow_detected_format={format_name}")
        self._debug_log(f"workflow_detected_reason={format_reason}")
        self._write_debug_json("comfy_workflow_loaded.json", payload)
        self.last_debug_info["workflow_source"] = {
            "workflow_id": workflow_id,
            "workflow_path": str(abs_path),
            "workflow_exists": exists,
            "workflow_size": size_bytes,
            "workflow_top_keys": top_keys,
            "workflow_detected_format": format_name,
            "workflow_detected_reason": format_reason,
            "loaded_workflow_path": str(self.debug_dir / "comfy_workflow_loaded.json"),
        }
        return payload

    def build_workflow(self, request: ImageGenerationRequest) -> dict[str, Any]:
        template = self.load_template(request.workflow_id)
        pre_summary = self.summarize_workflow(template)
        self._log_workflow_summary("loaded", pre_summary)
        self.last_debug_info["loaded_summary"] = pre_summary

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
        patch_events: list[dict[str, Any]] = []
        node_updates = request.parameters.get("node_updates", {}) if isinstance(request.parameters, dict) else {}
        if node_updates:
            _apply_node_updates(workflow, node_updates, patch_events)
        bindings = self.inspect_bindings(workflow)
        self._apply_dynamic_patches(workflow, bindings, request, patch_events)

        post_summary = self.summarize_workflow(workflow)
        self._log_workflow_summary("patched", post_summary)
        self._log_patch_events(patch_events)
        self._log_missing_required_inputs(pre_summary, post_summary)

        self._write_debug_json("comfy_workflow_patched.json", workflow)
        self.last_debug_info["patched_summary"] = post_summary
        self.last_debug_info["patch_events"] = patch_events
        self.last_debug_info["patched_workflow_path"] = str(self.debug_dir / "comfy_workflow_patched.json")
        return workflow

    def validate_workflow(self, workflow: dict[str, Any]) -> None:
        if not isinstance(workflow, dict):
            self._debug_log("workflow_invalid_reason=workflow_not_dict")
            raise ValueError("Workflow payload must be a dictionary")
        node_count = 0
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            if isinstance(node.get("inputs"), dict):
                node_count += 1
        if node_count == 0:
            self._debug_log("workflow_invalid_reason=no_executable_nodes")
            raise ValueError("Workflow does not contain any executable nodes.")

        format_name, format_reason = detect_workflow_format(workflow)
        if format_name != "api_prompt":
            self._debug_log(
                "workflow_not_prompt_compatible="
                f"format={format_name} reason={format_reason} expected=api_prompt"
            )

        bindings = self.inspect_bindings(workflow)
        if not bindings.save_image_node_ids:
            self._debug_log("workflow_invalid_reason=no_save_image_output_node")
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

    def summarize_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        format_name, format_reason = detect_workflow_format(workflow)
        executable_nodes: list[dict[str, Any]] = []
        if isinstance(workflow, dict):
            for node_id, node in workflow.items():
                if not isinstance(node, dict):
                    continue
                inputs = node.get("inputs")
                if not isinstance(inputs, dict):
                    continue
                executable_nodes.append(
                    {
                        "id": str(node_id),
                        "class_type": str(node.get("class_type", "")),
                        "input_keys": sorted(str(key) for key in inputs.keys()),
                    }
                )

        bindings = self.inspect_bindings(workflow if isinstance(workflow, dict) else {})
        return {
            "detected_format": format_name,
            "detected_reason": format_reason,
            "node_count": len(executable_nodes),
            "nodes": executable_nodes,
            "positive_prompt_nodes": bindings.positive_prompt_node_ids,
            "negative_prompt_nodes": bindings.negative_prompt_node_ids,
            "checkpoint_nodes": bindings.checkpoint_node_ids,
            "save_like_nodes": bindings.save_image_node_ids,
        }

    def _apply_dynamic_patches(
        self,
        workflow: dict[str, Any],
        bindings: WorkflowBindings,
        request: ImageGenerationRequest,
        patch_events: list[dict[str, Any]],
    ) -> None:
        for node_id in bindings.positive_prompt_node_ids:
            _set_node_input(workflow, node_id, "text", request.prompt, patch_events)
        for node_id in bindings.negative_prompt_node_ids:
            _set_node_input(workflow, node_id, "text", request.negative_prompt, patch_events)
        checkpoint = str(request.parameters.get("checkpoint", "")).strip()
        if checkpoint:
            for node_id in bindings.checkpoint_node_ids:
                _set_node_input(workflow, node_id, "ckpt_name", checkpoint, patch_events)

        sampler_inputs = {
            "seed": request.parameters.get("seed"),
            "steps": request.parameters.get("steps"),
            "cfg": request.parameters.get("cfg"),
            "sampler_name": request.parameters.get("sampler_name"),
            "scheduler": request.parameters.get("scheduler"),
            "denoise": request.parameters.get("denoise"),
        }
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            for key, value in sampler_inputs.items():
                if value is not None and key in inputs:
                    prior = inputs.get(key)
                    if prior != value:
                        inputs[key] = value
                        patch_events.append({"node_id": str(node_id), "field": f"inputs.{key}", "value": value})
            if "width" in inputs and request.parameters.get("width") is not None:
                width = request.parameters.get("width")
                if inputs.get("width") != width:
                    inputs["width"] = width
                    patch_events.append({"node_id": str(node_id), "field": "inputs.width", "value": width})
            if "height" in inputs and request.parameters.get("height") is not None:
                height = request.parameters.get("height")
                if inputs.get("height") != height:
                    inputs["height"] = height
                    patch_events.append({"node_id": str(node_id), "field": "inputs.height", "value": height})

    def _log_workflow_summary(self, stage: str, summary: dict[str, Any]) -> None:
        self._debug_log(f"{stage}_workflow_detected_format={summary.get('detected_format')}")
        self._debug_log(f"{stage}_workflow_detected_reason={summary.get('detected_reason')}")
        self._debug_log(f"{stage}_node_count={summary.get('node_count')}")
        for node in summary.get("nodes", []):
            self._debug_log(
                f"{stage}_node={node['id']} class_type={node['class_type']} input_keys={node['input_keys']}"
            )
        self._debug_log(f"{stage}_positive_prompt_nodes={summary.get('positive_prompt_nodes', [])}")
        self._debug_log(f"{stage}_negative_prompt_nodes={summary.get('negative_prompt_nodes', [])}")
        self._debug_log(f"{stage}_checkpoint_nodes={summary.get('checkpoint_nodes', [])}")
        self._debug_log(f"{stage}_save_like_nodes={summary.get('save_like_nodes', [])}")

    def _log_patch_events(self, patch_events: list[dict[str, Any]]) -> None:
        if not patch_events:
            self._debug_log("patched_nodes=none")
            return
        self._debug_log(f"patched_event_count={len(patch_events)}")
        for event in patch_events:
            value = event.get("value")
            preview = str(value)
            if len(preview) > 120:
                preview = f"{preview[:117]}..."
            self._debug_log(
                f"patched_node={event.get('node_id')} field={event.get('field')} value_preview={preview}"
            )

    def _log_missing_required_inputs(self, pre_summary: dict[str, Any], post_summary: dict[str, Any]) -> None:
        pre_map = {node["id"]: set(node.get("input_keys", [])) for node in pre_summary.get("nodes", [])}
        post_map = {node["id"]: set(node.get("input_keys", [])) for node in post_summary.get("nodes", [])}
        missing: list[dict[str, Any]] = []
        for node_id, pre_inputs in pre_map.items():
            dropped = sorted(pre_inputs - post_map.get(node_id, set()))
            if dropped:
                missing.append({"node_id": node_id, "missing_inputs": dropped})
        if missing:
            self._debug_log(f"patched_missing_required_inputs={missing}")
        else:
            self._debug_log("patched_missing_required_inputs=none")

    def _write_debug_json(self, filename: str, payload: Any) -> Path:
        target = self.debug_dir / filename
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stamped = self.debug_dir / f"{target.stem}_{timestamp}{target.suffix}"
        stamped.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    def _debug_log(self, message: str) -> None:
        print(f"[image-debug] {message}")


_TOKEN_PATTERN = re.compile(r"^\{\{([a-zA-Z0-9_]+)\}\}$")


def detect_workflow_format(workflow: Any) -> tuple[str, str]:
    if not isinstance(workflow, dict):
        return "unknown", "top-level payload is not an object"

    keys = set(workflow.keys())
    if {"last_node_id", "last_link_id", "nodes", "links"}.issubset(keys) or (
        isinstance(workflow.get("nodes"), list) and isinstance(workflow.get("links"), list)
    ):
        return "ui_graph", "contains UI graph fields like nodes/links"

    if "prompt" in workflow and isinstance(workflow.get("prompt"), dict):
        return "app_mode_export", "contains top-level prompt envelope"

    numeric_like = all(str(key).isdigit() for key in workflow.keys()) if workflow else False
    if numeric_like:
        valid_prompt_nodes = True
        for node in workflow.values():
            if not isinstance(node, dict):
                valid_prompt_nodes = False
                break
            if not isinstance(node.get("inputs"), dict) or not node.get("class_type"):
                valid_prompt_nodes = False
                break
        if valid_prompt_nodes:
            return "api_prompt", "top-level numeric node map with class_type+inputs"

    if any(key in keys for key in {"nodes", "links", "groups", "extra"}):
        return "unknown", "contains graph-like keys but not recognized prompt format"

    return "unknown", "does not match known ComfyUI prompt or UI export formats"


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


def _apply_node_updates(workflow: dict[str, Any], updates: dict[str, dict[str, Any]], patch_events: list[dict[str, Any]]) -> None:
    for node_id, patch in updates.items():
        node = workflow.get(node_id)
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        if isinstance(inputs, dict):
            for key, value in patch.items():
                prior = inputs.get(key)
                if prior != value:
                    inputs[key] = value
                    patch_events.append({"node_id": str(node_id), "field": f"inputs.{key}", "value": value})


def _set_node_input(workflow: dict[str, Any], node_id: str, key: str, value: Any, patch_events: list[dict[str, Any]]) -> None:
    node = workflow.get(node_id)
    if not isinstance(node, dict):
        return
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        return
    if key in inputs and inputs.get(key) != value:
        inputs[key] = value
        patch_events.append({"node_id": str(node_id), "field": f"inputs.{key}", "value": value})


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
