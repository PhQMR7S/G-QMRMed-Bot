"""Provider-neutral image generation contracts and ComfyUI/Hugging Face adapters."""

from __future__ import annotations

import asyncio
import copy
import time
from dataclasses import dataclass
from typing import Any, cast, Protocol
from uuid import uuid4

import cairosvg
import httpx
from huggingface_hub import InferenceClient


class ImageGenerationError(RuntimeError):
    """Raised when an image provider cannot produce an illustration."""


@dataclass(frozen=True, slots=True)
class GeneratedIllustration:
    """Image-model output before exact-text rendering."""

    image_bytes: bytes
    width: int
    height: int
    mime_type: str = "image/png"


class ImageGenerationProvider(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
    ) -> GeneratedIllustration:
        ...


class ProceduralMedicalIllustrationProvider:
    """Deterministic no-network illustration fallback with no visible text."""

    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
    ) -> GeneratedIllustration:
        del prompt
        if width <= 0 or height <= 0:
            raise ImageGenerationError("invalid_image_dimensions")
        cx = width / 2
        cy = height * 0.42
        radius = min(width, height) * 0.24
        path = (
            f"M{width * 0.25:.1f} {cy:.1f} H{width * 0.38:.1f} "
            f"L{width * 0.44:.1f} {height * 0.32:.1f} "
            f"L{width * 0.50:.1f} {height * 0.53:.1f} "
            f"L{width * 0.57:.1f} {height * 0.36:.1f} "
            f"L{width * 0.63:.1f} {cy:.1f} H{width * 0.75:.1f}"
        )
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#EAF3F7"/>
              <stop offset="1" stop-color="#D9E9E6"/>
            </linearGradient>
          </defs>
          <rect width="{width}" height="{height}" rx="48" fill="url(#bg)"/>
          <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" fill="#ffffff" opacity="0.38"/>
          <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius * 0.70:.1f}" fill="none" stroke="#5E93A8" stroke-width="10" opacity="0.45"/>
          <path d="{path}" fill="none" stroke="#5E93A8" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" opacity="0.48"/>
          <circle cx="{cx:.1f}" cy="{cy:.1f}" r="34" fill="#5E93A8" opacity="0.30"/>
          <path d="M{cx:.1f} {cy - radius * 1.18:.1f} V{cy - radius * 0.90:.1f} M{cx:.1f} {cy + radius * 0.90:.1f} V{cy + radius * 1.18:.1f} M{cx - radius * 1.18:.1f} {cy:.1f} H{cx - radius * 0.90:.1f} M{cx + radius * 0.90:.1f} {cy:.1f} H{cx + radius * 1.18:.1f}" stroke="#5E93A8" stroke-width="8" stroke-linecap="round" opacity="0.28"/>
        </svg>
        """
        image_bytes = await asyncio.to_thread(
            cairosvg.svg2png,
            bytestring=svg.encode("utf-8"),
            output_width=width,
            output_height=height,
        )
        return GeneratedIllustration(
            image_bytes=image_bytes,
            width=width,
            height=height,
            mime_type="image/png",
        )


@dataclass(frozen=True, slots=True)
class HuggingFaceImageConfig:
    token: str
    model: str = "black-forest-labs/FLUX.1-dev"
    provider: str = "auto"
    timeout_seconds: float = 180.0


class HuggingFaceImageProvider:
    """Generate illustrations through Hugging Face Inference Providers."""

    def __init__(self, config: HuggingFaceImageConfig) -> None:
        self.config = config

    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
    ) -> GeneratedIllustration:
        if width <= 0 or height <= 0:
            raise ImageGenerationError("invalid_image_dimensions")
        if not prompt.strip():
            raise ImageGenerationError("image_prompt_empty")
        if not self.config.token.strip():
            raise ImageGenerationError("huggingface_token_missing")
        if not self.config.model.strip():
            raise ImageGenerationError("huggingface_model_missing")

        def generate_sync() -> bytes:
            client = InferenceClient(
                provider=cast(Any, self.config.provider),
                api_key=self.config.token,
            )
            image = client.text_to_image(
                prompt=prompt,
                model=self.config.model,
                width=width,
                height=height,
            )
            from io import BytesIO

            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

        try:
            image_bytes = await asyncio.wait_for(
                asyncio.to_thread(generate_sync),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError as exc:
            raise ImageGenerationError("huggingface_generation_timeout") from exc
        except Exception as exc:  # noqa: BLE001 - provider boundary
            raise ImageGenerationError("huggingface_generation_failed") from exc

        return GeneratedIllustration(
            image_bytes=image_bytes,
            width=width,
            height=height,
            mime_type="image/png",
        )


@dataclass(frozen=True, slots=True)
class ComfyUIConfig:
    """Configuration for a ComfyUI API-format illustration worker."""

    base_url: str = "http://127.0.0.1:8188"
    timeout_seconds: float = 180.0
    poll_interval_seconds: float = 1.0
    max_wait_seconds: float = 180.0
    workflow: dict[str, Any] | None = None


class ComfyUIImageProvider:
    """Execute a configurable ComfyUI API-format workflow and download its image."""

    def __init__(
        self,
        config: ComfyUIConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
    ) -> GeneratedIllustration:
        if width <= 0 or height <= 0:
            raise ImageGenerationError("invalid_image_dimensions")
        if not prompt.strip():
            raise ImageGenerationError("image_prompt_empty")
        if not self.config.workflow:
            raise ImageGenerationError("comfyui_workflow_not_configured")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            workflow = copy.deepcopy(self.config.workflow)
            _inject_inputs(workflow, prompt=prompt, width=width, height=height)
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/prompt",
                json={"prompt": workflow, "client_id": str(uuid4())},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(
                payload.get("prompt_id"), str
            ):
                raise ImageGenerationError("comfyui_invalid_prompt_response")
            metadata = await self._wait_for_output(client, payload["prompt_id"])
            image = await client.get(
                f"{self.config.base_url.rstrip('/')}/view",
                params={
                    "filename": metadata["filename"],
                    "subfolder": metadata.get("subfolder", ""),
                    "type": metadata.get("type", "output"),
                },
            )
            image.raise_for_status()
            return GeneratedIllustration(
                image_bytes=image.content,
                width=width,
                height=height,
                mime_type=image.headers.get("content-type", "image/png").split(";", 1)[0],
            )
        except httpx.HTTPError as exc:
            raise ImageGenerationError("comfyui_request_failed") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def _wait_for_output(
        self,
        client: httpx.AsyncClient,
        prompt_id: str,
    ) -> dict[str, str]:
        deadline = time.monotonic() + self.config.max_wait_seconds
        while time.monotonic() < deadline:
            response = await client.get(
                f"{self.config.base_url.rstrip('/')}/history/{prompt_id}"
            )
            response.raise_for_status()
            history = response.json()
            result = history.get(prompt_id) if isinstance(history, dict) else None
            outputs = result.get("outputs", {}) if isinstance(result, dict) else {}
            for node_output in outputs.values() if isinstance(outputs, dict) else []:
                images = (
                    node_output.get("images", [])
                    if isinstance(node_output, dict)
                    else []
                )
                if (
                    images
                    and isinstance(images[0], dict)
                    and isinstance(images[0].get("filename"), str)
                ):
                    return images[0]
            await asyncio.sleep(self.config.poll_interval_seconds)
        raise ImageGenerationError("comfyui_generation_timeout")


def _inject_inputs(
    workflow: dict[str, Any],
    *,
    prompt: str,
    width: int,
    height: int,
) -> None:
    """Inject values into common API-format ComfyUI nodes."""
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        class_type = node.get("class_type")
        if class_type in {
            "CLIPTextEncode",
            "CLIPTextEncodeSDXL",
            "TextEncodeQwenImageEdit",
        }:
            inputs["text"] = prompt
        if class_type in {"EmptyLatentImage", "EmptySD3LatentImage"}:
            inputs["width"] = width
            inputs["height"] = height
