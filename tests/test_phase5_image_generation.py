import pytest

from gqmrmed.ai.image_generation import (
    ComfyUIConfig,
    ComfyUIIllustrationProvider,
    ImageGenerationError,
    ImageGenerationRequest,
)


def test_image_request_defaults_to_9_16() -> None:
    request = ImageGenerationRequest(prompt="Medical anatomy illustration")
    assert request.width == 1080
    assert request.height == 1920


def test_image_request_rejects_non_9_16_dimensions() -> None:
    with pytest.raises(ValueError, match="image_dimensions_must_be_9_16"):
        ImageGenerationRequest(prompt="illustration", width=1024, height=1024)


def test_image_request_rejects_empty_prompt() -> None:
    with pytest.raises(ValueError, match="image_prompt_required"):
        ImageGenerationRequest(prompt=" ")


def test_comfyui_provider_never_fabricates_an_asset() -> None:
    provider = ComfyUIIllustrationProvider(
        ComfyUIConfig(base_url="http://comfyui:8188", workflow_id="gqmrmed-flux")
    )
    request = ImageGenerationRequest(prompt="Medical illustration only")

    async def run() -> None:
        with pytest.raises(ImageGenerationError, match="comfyui_transport_not_configured"):
            await provider.generate(request)

    import asyncio

    asyncio.run(run())
