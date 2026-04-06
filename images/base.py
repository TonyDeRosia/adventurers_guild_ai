"""Image generation abstractions and request/response models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ImageGenerationRequest:
    workflow_id: str
    prompt: str
    negative_prompt: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenerationResult:
    success: bool
    workflow_id: str
    result_path: str | None = None
    prompt_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImageGeneratorAdapter(ABC):
    """Optional adapter for generating scene art."""

    @abstractmethod
    def generate(self, request: ImageGenerationRequest, workflow_manager: Any) -> ImageGenerationResult:
        """Generate image content from workflow templates."""


class NullImageAdapter(ImageGeneratorAdapter):
    """Default local fallback when image backends are not configured."""

    def generate(self, request: ImageGenerationRequest, workflow_manager: Any) -> ImageGenerationResult:
        return ImageGenerationResult(
            success=False,
            workflow_id=request.workflow_id,
            error="Image generation is disabled (using NullImageAdapter).",
            metadata={"prompt": request.prompt, "parameters": request.parameters},
        )
