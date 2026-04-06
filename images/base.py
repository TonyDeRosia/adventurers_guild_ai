"""Image generation adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ImageGeneratorAdapter(ABC):
    """Optional adapter for generating scene art."""

    @abstractmethod
    def generate_scene_image(self, prompt: str) -> str:
        """Return path or URL to generated image."""


class NullImageAdapter(ImageGeneratorAdapter):
    def generate_scene_image(self, prompt: str) -> str:
        return "Image generation disabled"
