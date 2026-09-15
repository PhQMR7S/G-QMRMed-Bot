"""OpenAI image generation adapter for the QMRMed reference-driven artwork layer."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from gqmrmed.generation.providers import GeneratedIllustration, ImageGenerationError

REFERENCE_DNA = """
Create only the medical illustration layer for a QMRMed editorial infographic.
The visual reference family is a polished Arabic medical education poster: warm
ivory paper background, soft rose/mint/cyan/lavender/amber pastel accents,
rounded modular cards, clean flat-to-soft 3D clinical illustration, refined
editorial spacing, subtle shadows, friendly but medically credible anatomy,
and restrained premium styling. The illustration must fit naturally inside a
large clean rounded visual panel and must leave negative space around the main
subject. Use the requested medical topic as the sole subject.

This is NOT a request to generate the final infographic. Do not generate any
readable text, Arabic letters, English letters, labels, numbers, doses, arrows
with text, logos, signatures, watermarks, citations, UI, or disclaimers.
Do not invent medical facts. Do not add unrelated medical objects. The final
text and cards are composed deterministically by QMRMed after generation.
""".strip()


@dataclass(frozen=True, slots=True)
class OpenAIImageConfig:
    """Configuration for the OpenAI image model."""

    api_key: str
    model: str = "gpt-image-2"
    quality: str = "medium"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 180.0


class OpenAIImageProvider:
    """Generate the illustration layer through OpenAI's Image API."""

    def __init__(
        self,
        config: OpenAIImageConfig,
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
        if not self.config.api_key.strip():
            raise ImageGenerationError("openai_image_api_key_missing")
        if width != 1024 or height != 1536:
            raise ImageGenerationError("openai_image_requires_1024x1536_reference_canvas")
        if self.config.quality not in {"low", "medium", "high"}:
            raise ImageGenerationError("openai_image_quality_invalid")
        if not prompt.strip():
            raise ImageGenerationError("image_prompt_empty")

        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": f"{REFERENCE_DNA}\n\nTopic-specific brief:\n{prompt[:12000]}",
            "size": "1024x1536",
            "quality": self.config.quality,
            "n": 1,
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}/images/generations",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if response.is_error:
                raise ImageGenerationError(
                    f"openai_image_request_failed:{response.status_code}"
                )
            data = response.json()
            encoded = _extract_base64(data)
            if encoded is None:
                raise ImageGenerationError("openai_image_missing_base64_output")
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
                image = Image.open(BytesIO(image_bytes))
                image.load()
            except Exception as exc:  # noqa: BLE001 - provider boundary
                raise ImageGenerationError("openai_image_invalid_output") from exc
            if image.size != (width, height):
                raise ImageGenerationError("openai_image_dimensions_mismatch")
            return GeneratedIllustration(
                image_bytes=image_bytes,
                width=width,
                height=height,
                mime_type="image/png",
            )
        except httpx.HTTPError as exc:
            raise ImageGenerationError("openai_image_network_error") from exc
        finally:
            if owns_client:
                await client.aclose()


def _extract_base64(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if not isinstance(first, dict):
        return None
    value = first.get("b64_json")
    return value if isinstance(value, str) and value else None


__all__ = ["OpenAIImageConfig", "OpenAIImageProvider", "REFERENCE_DNA"]
