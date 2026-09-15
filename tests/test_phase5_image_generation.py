import pytest

from gqmrmed.ai.image_generation import (
    build_illustration_request,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    ComfyUIConfig,
    ComfyUIIllustrationProvider,
    ImageGenerationError,
    ImageGenerationRequest,
)
from gqmrmed.contracts.research import ArchitectureType, VisualPlan


def test_image_request_defaults_to_2_3() -> None:
    request = ImageGenerationRequest(prompt="Medical anatomy illustration")
    assert request.width == CANVAS_WIDTH == 1024
    assert request.height == CANVAS_HEIGHT == 1536


def test_image_request_rejects_non_2_3_dimensions() -> None:
    with pytest.raises(ValueError, match="image_dimensions_must_be_2_3"):
        ImageGenerationRequest(prompt="illustration", width=1024, height=1024)


def test_image_request_rejects_empty_prompt() -> None:
    with pytest.raises(ValueError, match="image_prompt_required"):
        ImageGenerationRequest(prompt=" ")


def test_visual_plan_becomes_illustration_request() -> None:
    plan = VisualPlan(
        architecture=ArchitectureType.ANATOMY_EXPLORER,
        sections=["structure"],
        illustration_prompt="Medical vector anatomy illustration only.",
    )
    request = build_illustration_request(plan, seed=42)
    assert request.prompt == plan.illustration_prompt
    assert request.seed == 42
    assert (request.width, request.height) == (1024, 1536)


def test_non_2_3_visual_plan_is_rejected() -> None:
    plan = VisualPlan(
        architecture=ArchitectureType.ANATOMY_EXPLORER,
        aspect_ratio="1:1",
        sections=["structure"],
        illustration_prompt="Medical vector anatomy illustration only.",
    )
    with pytest.raises(ValueError, match="visual_plan_must_be_2_3"):
        build_illustration_request(plan)


@pytest.mark.asyncio
async def test_comfyui_provider_never_fabricates_an_asset() -> None:
    provider = ComfyUIIllustrationProvider(
        ComfyUIConfig(base_url="http://comfyui:8188", workflow_id="gqmrmed-flux")
    )
    request = ImageGenerationRequest(prompt="Medical illustration only")

    with pytest.raises(ImageGenerationError, match="comfyui_transport_not_configured"):
        await provider.generate(request)
