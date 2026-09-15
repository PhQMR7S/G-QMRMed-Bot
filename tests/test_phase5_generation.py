import pytest

from gqmrmed.contracts.research import (
    ArchitectureType,
    MedicalClaim,
    SynthesizedContent,
    VisualPlan,
)
from gqmrmed.generation.providers import (
    ComfyUIConfig,
    ComfyUIImageProvider,
    ImageGenerationError,
)
from gqmrmed.generation.renderer import HEIGHT, render_infographic_svg, WIDTH


def _content() -> SynthesizedContent:
    return SynthesizedContent(
        title="DKA",
        key_points=["Metabolic emergency"],
        claims=[
            MedicalClaim(
                claim_id="c1",
                text="DKA is an emergency.",
                evidence_ids=["e1"],
                confidence=0.9,
            )
        ],
    )


def test_renderer_is_2_3_and_keeps_exact_text_outside_image_model() -> None:
    plan = VisualPlan(
        architecture=ArchitectureType.CLINICAL_EMERGENCY_ALGORITHM,
        sections=["danger"],
        illustration_prompt="illustration only",
    )
    svg = render_infographic_svg(content=_content(), plan=plan)
    assert WIDTH == 1024
    assert HEIGHT == 1536
    assert HEIGHT / WIDTH == 3 / 2
    assert f'width="{WIDTH}"' in svg
    assert f'height="{HEIGHT}"' in svg
    assert "Metabolic emergency" in svg
    assert "GQMRMed" in svg


@pytest.mark.asyncio
async def test_comfyui_requires_explicit_workflow() -> None:
    provider = ComfyUIImageProvider(ComfyUIConfig())
    with pytest.raises(
        ImageGenerationError,
        match="comfyui_workflow_not_configured",
    ):
        await provider.generate(
            prompt="medical illustration",
            width=WIDTH,
            height=HEIGHT,
        )
