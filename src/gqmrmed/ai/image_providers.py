"""Image-only provider adapters for the QMRMed infographic pipeline.

All providers are instructed to create artwork only. Exact medical text is rendered
locally after generation, which prevents image-model text hallucinations and layout drift.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from typing import Any

import httpx

from gqmrmed.generation.providers import GeneratedIllustration, ImageGenerationError


@dataclass(frozen=True, slots=True)
class CloudflareImageConfig:
    api_token: str
    account_id: str
    model: str = "@cf/black-forest-labs/flux-2-klein-4b"
    timeout_seconds: float = 180.0


class CloudflareImageProvider:
    """Workers AI FLUX image adapter using the documented REST API."""

    def __init__(
        self,
        config: CloudflareImageConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def generate(
        self, *, prompt: str, width: int, height: int
    ) -> GeneratedIllustration:
        _validate_request(prompt, width, height)
        if not self.config.api_token.strip() or not self.config.account_id.strip():
            raise ImageGenerationError("cloudflare_credentials_missing")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            url = (
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{self.config.account_id}/ai/run/{self.config.model}"
            )
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {self.config.api_token}"},
                files={
                    "prompt": (None, prompt),
                    "width": (None, str(width)),
                    "height": (None, str(height)),
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            result = payload.get("result")
            image = result.get("image") if isinstance(result, dict) else None
            if not isinstance(image, str) or not image:
                raise ImageGenerationError("cloudflare_image_missing")
            return GeneratedIllustration(
                image_bytes=base64.b64decode(image),
                width=width,
                height=height,
                mime_type="image/png",
            )
        except httpx.HTTPError as exc:
            raise ImageGenerationError("cloudflare_image_request_failed") from exc
        except (ValueError, TypeError) as exc:
            raise ImageGenerationError("cloudflare_image_response_invalid") from exc
        finally:
            if owns_client:
                await client.aclose()


@dataclass(frozen=True, slots=True)
class QwenImageConfig:
    api_key: str
    base_url: str
    model: str = "qwen-image-3.0-pro"
    timeout_seconds: float = 180.0


class QwenImageProvider:
    """Qwen Image 3.0 OpenAI-compatible image-generation adapter."""

    def __init__(
        self,
        config: QwenImageConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def generate(
        self, *, prompt: str, width: int, height: int
    ) -> GeneratedIllustration:
        _validate_request(prompt, width, height)
        if not self.config.api_key.strip() or not self.config.base_url.strip():
            raise ImageGenerationError("qwen_credentials_missing")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/images/generations",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "prompt": prompt,
                    "size": f"{width}x{height}",
                    "n": 1,
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            data = payload.get("data")
            url = data[0].get("url") if isinstance(data, list) and data else None
            if not isinstance(url, str) or not url:
                raise ImageGenerationError("qwen_image_url_missing")
            image_response = await client.get(url)
            image_response.raise_for_status()
            mime_type = image_response.headers.get("content-type", "image/png")
            return GeneratedIllustration(
                image_bytes=image_response.content,
                width=width,
                height=height,
                mime_type=mime_type.split(";", 1)[0],
            )
        except httpx.HTTPError as exc:
            raise ImageGenerationError("qwen_image_request_failed") from exc
        except (ValueError, TypeError) as exc:
            raise ImageGenerationError("qwen_image_response_invalid") from exc
        finally:
            if owns_client:
                await client.aclose()


@dataclass(frozen=True, slots=True)
class GeminiImageConfig:
    api_key: str
    model: str = "gemini-3.1-flash-image"
    timeout_seconds: float = 180.0


class GeminiImageProvider:
    """Gemini 3.1 Flash Image adapter using the current Interactions API."""

    def __init__(
        self,
        config: GeminiImageConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def generate(
        self, *, prompt: str, width: int, height: int
    ) -> GeneratedIllustration:
        _validate_request(prompt, width, height)
        if not self.config.api_key.strip():
            raise ImageGenerationError("gemini_credentials_missing")
        aspect_ratio = _aspect_ratio(width, height)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={
                    "x-goog-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "input": prompt,
                    "response_format": {
                        "type": "image",
                        "mime_type": "image/png",
                        "aspect_ratio": aspect_ratio,
                        "image_size": "2K",
                    },
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            image = _extract_interaction_image(payload)
            if image is None:
                raise ImageGenerationError("gemini_image_missing")
            image_data, mime_type = image
            return GeneratedIllustration(
                image_bytes=base64.b64decode(image_data),
                width=width,
                height=height,
                mime_type=mime_type,
            )
        except httpx.HTTPError as exc:
            raise ImageGenerationError("gemini_image_request_failed") from exc
        except (ValueError, TypeError) as exc:
            raise ImageGenerationError("gemini_image_response_invalid") from exc
        finally:
            if owns_client:
                await client.aclose()


def _extract_interaction_image(
    payload: dict[str, Any],
) -> tuple[str, str] | None:
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return None
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("type") != "model_output":
            continue
        content = step.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "image":
                continue
            data = block.get("data")
            if isinstance(data, str) and data:
                mime_type = str(block.get("mime_type", "image/png"))
                return data, mime_type
    return None


def _validate_request(prompt: str, width: int, height: int) -> None:
    if not prompt.strip():
        raise ImageGenerationError("image_prompt_empty")
    if not 256 <= width <= 1920 or not 256 <= height <= 1920:
        raise ImageGenerationError("invalid_image_dimensions")


def _aspect_ratio(width: int, height: int) -> str:
    pairs = {
        (1, 1): "1:1",
        (4, 5): "4:5",
        (5, 4): "5:4",
        (2, 3): "2:3",
        (3, 4): "3:4",
        (9, 16): "9:16",
        (16, 9): "16:9",
    }
    divisor = math.gcd(width, height)
    return pairs.get((width // divisor, height // divisor), "4:5")


__all__ = [
    "CloudflareImageConfig",
    "CloudflareImageProvider",
    "GeminiImageConfig",
    "GeminiImageProvider",
    "QwenImageConfig",
    "QwenImageProvider",
]
