import base64
import io

import pytest
from PIL import Image

from gqmrmed.ai.openai_image import OpenAIImageConfig, OpenAIImageProvider
from gqmrmed.generation.providers import ImageGenerationError


class FakeResponse:
    is_error = False

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return FakeResponse(self.payload)


@pytest.mark.asyncio
async def test_openai_image_provider_uses_reference_canvas_and_illustration_only_prompt() -> None:
    image = Image.new("RGB", (1024, 1536), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    payload = {"data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode("ascii")}]}
    client = FakeClient(payload)
    provider = OpenAIImageProvider(
        OpenAIImageConfig(api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    result = await provider.generate(
        prompt="Medical illustration of a healthy human heart.",
        width=1024,
        height=1536,
    )

    assert result.width == 1024
    assert result.height == 1536
    request = client.calls[0]["json"]
    assert request["model"] == "gpt-image-2"
    assert request["size"] == "1024x1536"
    assert request["quality"] == "medium"
    assert "no readable text" in str(request["prompt"]).lower()
    assert "heart" in str(request["prompt"]).lower()


@pytest.mark.asyncio
async def test_openai_image_provider_rejects_non_reference_canvas() -> None:
    provider = OpenAIImageProvider(
        OpenAIImageConfig(api_key="test-key"),
        client=FakeClient({}),  # type: ignore[arg-type]
    )
    with pytest.raises(
        ImageGenerationError,
        match="openai_image_requires_1024x1536_reference_canvas",
    ):
        await provider.generate(prompt="medical illustration", width=1080, height=1350)
