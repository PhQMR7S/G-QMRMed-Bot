"""Provider-neutral image generation contracts and ComfyUI HTTP adapter."""

from dataclasses import dataclass
from typing import Protocol

import httpx


class ImageGenerationError(RuntimeError):
    """Raised when an image provider cannot produce an illustration."""


@dataclass(frozen=True, slots=True)
class GeneratedIllustration:
    asset_uri: str
    width: int
    height: int


class ImageGenerationProvider(Protocol):
    async def generate(self, *, prompt: str, width: int, height: int) -> GeneratedIllustration:
        ...


@dataclass(frozen=True, slots=True)
class ComfyUIConfig:
    base_url: str = "http://127.0.0.1:8188"
    timeout_seconds: float = 120.0


class ComfyUIImageProvider:
    """Minimal provider boundary; workflow construction stays configurable."""

    def __init__(self, config: ComfyUIConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def generate(self, *, prompt: str, width: int, height: int) -> GeneratedIllustration:
        if width <= 0 or height <= 0:
            raise ImageGenerationError("invalid_image_dimensions")
        if not prompt.strip():
            raise ImageGenerationError("image_prompt_empty")
        # The actual ComfyUI workflow is injected in the worker/provider layer.
        # This contract intentionally prevents the core pipeline from depending on
        # a specific checkpoint or node graph.
        raise ImageGenerationError("comfyui_workflow_not_configured")
