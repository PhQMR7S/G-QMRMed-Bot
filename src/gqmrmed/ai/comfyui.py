"""Concrete ComfyUI HTTP transport for provider-neutral illustration generation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import httpx

from gqmrmed.ai.image_generation import (
    ComfyUIConfig,
    ImageGenerationError,
    ImageGenerationRequest,
    ImageGenerationResult,
)

WorkflowFactory = Callable[[ImageGenerationRequest], Mapping[str, Any]]


class ImageArtifactStore(Protocol):
    """Persist generated image bytes and return an opaque storage key."""

    async def put_image(self, *, data: bytes, content_type: str) -> str:
        """Store an image and return its storage key."""
        ...


@dataclass(frozen=True, slots=True)
class ComfyUITransportConfig:
    """Runtime settings for the ComfyUI HTTP API."""

    poll_interval_seconds: float = 1.0
    max_poll_seconds: float = 180.0

    def __post_init__(self) -> None:
        if self.poll_interval_seconds <= 0:
            raise ValueError("comfyui_poll_interval_invalid")
        if self.max_poll_seconds <= 0:
            raise ValueError("comfyui_max_poll_invalid")


class ComfyUIHTTPTransport:
    """Submit a workflow to ComfyUI, wait for completion, and retrieve its image."""

    def __init__(
        self,
        *,
        config: ComfyUIConfig,
        workflow_factory: WorkflowFactory,
        artifact_store: ImageArtifactStore,
        transport_config: ComfyUITransportConfig | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.workflow_factory = workflow_factory
        self.artifact_store = artifact_store
        self.transport_config = transport_config or ComfyUITransportConfig(
            max_poll_seconds=config.timeout_seconds
        )
        self._client = client
        self._owns_client = client is None

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Execute one ComfyUI workflow and persist the resulting image."""
        client = self._client or httpx.AsyncClient(
            base_url=self.config.base_url.rstrip("/"),
            timeout=httpx.Timeout(self.config.timeout_seconds),
        )
        try:
            workflow = dict(self.workflow_factory(request))
            prompt_id = await self._submit(client, workflow)
            image_url, content_type = await self._wait_for_image(client, prompt_id)
            response = await client.get(image_url)
            response.raise_for_status()
            storage_key = await self.artifact_store.put_image(
                data=response.content,
                content_type=content_type,
            )
            return ImageGenerationResult(
                storage_key=storage_key,
                width=request.width,
                height=request.height,
                provider="comfyui",
                model=self.config.model,
                seed=request.seed,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ImageGenerationError("comfyui_generation_failed") from exc
        finally:
            if self._owns_client:
                await client.aclose()

    async def _submit(self, client: httpx.AsyncClient, workflow: Mapping[str, Any]) -> str:
        client_id = str(uuid4())
        response = await client.post(
            "/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        response.raise_for_status()
        payload = response.json()
        prompt_id = payload.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ValueError("comfyui_prompt_id_missing")
        return prompt_id

    async def _wait_for_image(
        self, client: httpx.AsyncClient, prompt_id: str
    ) -> tuple[str, str]:
        deadline = asyncio.get_running_loop().time() + self.transport_config.max_poll_seconds
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"/history/{prompt_id}")
            response.raise_for_status()
            payload = response.json()
            result = payload.get(prompt_id)
            if isinstance(result, Mapping):
                image = self._extract_image(result)
                if image is not None:
                    return image
                status = result.get("status")
                if isinstance(status, Mapping) and status.get("status_str") == "error":
                    raise ValueError("comfyui_workflow_failed")
            await asyncio.sleep(self.transport_config.poll_interval_seconds)
        raise ValueError("comfyui_generation_timeout")

    @staticmethod
    def _extract_image(history: Mapping[str, Any]) -> tuple[str, str] | None:
        outputs = history.get("outputs")
        if not isinstance(outputs, Mapping):
            return None
        for node_output in outputs.values():
            if not isinstance(node_output, Mapping):
                continue
            images = node_output.get("images")
            if not isinstance(images, list):
                continue
            for image in images:
                if not isinstance(image, Mapping):
                    continue
                filename = image.get("filename")
                if not isinstance(filename, str) or not filename:
                    continue
                subfolder = image.get("subfolder", "")
                image_type = image.get("type", "output")
                if not all(isinstance(value, str) for value in (subfolder, image_type)):
                    continue
                query = httpx.QueryParams(
                    {"filename": filename, "subfolder": subfolder, "type": image_type}
                )
                return f"/view?{query}", "image/png"
        return None


class ComfyUIIllustrationProvider:
    """IllustrationProvider backed by the concrete ComfyUI HTTP transport."""

    def __init__(self, *, config: ComfyUIConfig, transport: ComfyUIHTTPTransport) -> None:
        self.config = config
        self.transport = transport

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return await self.transport.generate(request)


__all__ = [
    "ComfyUIHTTPTransport",
    "ComfyUIIllustrationProvider",
    "ComfyUITransportConfig",
    "ImageArtifactStore",
    "WorkflowFactory",
]
