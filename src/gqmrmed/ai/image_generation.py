"""Provider-neutral medical illustration generation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ImageGenerationError(RuntimeError):
    """Raised when an illustration provider cannot produce an asset."""


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    """Validated request sent to an illustration-only provider."""

    prompt: str
    width: int = 1080
    height: int = 1920
    seed: int | None = None

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("image_prompt_required")
        if not 256 <= self.width <= 4096 or not 256 <= self.height <= 4096:
            raise ValueError("invalid_image_dimensions")
        if self.width * 16 != self.height * 9:
            raise ValueError("image_dimensions_must_be_9_16")
        if self.seed is not None and self.seed < 0:
            raise ValueError("image_seed_invalid")


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    """Provider result represented by an opaque storage reference."""

    storage_key: str
    width: int
    height: int
    provider: str
    model: str
    seed: int | None = None


class IllustrationProvider(Protocol):
    """Minimal async contract implemented by every image provider."""

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate illustration artwork without rendering readable text."""
        ...


@dataclass(frozen=True, slots=True)
class ComfyUIConfig:
    """Configuration for a ComfyUI-compatible illustration worker."""

    base_url: str
    workflow_id: str
    model: str = "FLUX.2 Klein 4B"
    timeout_seconds: float = 180.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("comfyui_base_url_required")
        if not self.workflow_id.strip():
            raise ValueError("comfyui_workflow_required")
        if self.timeout_seconds <= 0:
            raise ValueError("comfyui_timeout_invalid")


class ComfyUIIllustrationProvider:
    """Provider shell for a ComfyUI worker; transport is injected separately."""

    def __init__(self, config: ComfyUIConfig) -> None:
        self.config = config

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Reject until a concrete workflow transport is configured.

        The boundary intentionally does not fabricate an image or silently fall back
        to a text model. A deployment adapter can implement the ComfyUI API while the
        rest of GQMRMed remains provider-independent.
        """
        raise ImageGenerationError("comfyui_transport_not_configured")


__all__ = [
    "ComfyUIConfig",
    "ComfyUIIllustrationProvider",
    "ImageGenerationError",
    "ImageGenerationRequest",
    "ImageGenerationResult",
    "IllustrationProvider",
]
