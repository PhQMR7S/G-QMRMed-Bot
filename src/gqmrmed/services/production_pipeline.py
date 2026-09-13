"""End-to-end text generation pipeline used by the durable worker."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from gqmrmed.ai.image_generation import build_illustration_request
from gqmrmed.contracts.generation import GenerationStage
from gqmrmed.contracts.research import ResearchRequest, SynthesizedContent, VisualPlan
from gqmrmed.db.models import GenerationJob
from gqmrmed.generation.providers import GeneratedIllustration, ImageGenerationProvider
from gqmrmed.rendering.raster import render_png
from gqmrmed.rendering.svg import render_svg
from gqmrmed.services.medical_pipeline import MedicalPlan, build_medical_plan
from gqmrmed.services.research import ResearchProvider


class SynthesisService(Protocol):
    async def synthesize(self, *, user_input: str, research: object) -> SynthesizedContent: ...


@dataclass(frozen=True, slots=True)
class ProductionPipelineConfig:
    width: int = 1080
    height: int = 1920


class ProductionGenerationPipeline:
    """Run research, synthesis, architecture, illustration and exact rendering."""

    def __init__(
        self,
        *,
        research_provider: ResearchProvider,
        synthesis_provider: SynthesisService,
        image_provider: ImageGenerationProvider,
        config: ProductionPipelineConfig | None = None,
    ) -> None:
        self._research_provider = research_provider
        self._synthesis_provider = synthesis_provider
        self._image_provider = image_provider
        self._config = config or ProductionPipelineConfig()

    async def run(
        self,
        job: GenerationJob,
        progress: Callable[[GenerationStage, int], Awaitable[None]],
    ) -> GeneratedIllustration:
        user_input = (job.input_text or "").strip()
        if not user_input:
            raise ValueError("text_input_required_for_medical_pipeline")

        await progress(GenerationStage.RESEARCHING, 10)
        plan = await build_medical_plan(
            user_input=user_input,
            research_request=ResearchRequest(query=user_input, max_sources=8),
            research_provider=self._research_provider,
            synthesis_provider=self._synthesis_provider,
        )

        await progress(GenerationStage.SYNTHESIZING, 35)
        await progress(GenerationStage.ARCHITECTURE, 50)
        illustration = await self._generate_illustration(plan.visual_plan, progress)

        await progress(GenerationStage.RENDERING, 85)
        svg = render_svg(
            content=plan.content,
            visual_plan=plan.visual_plan,
            illustration_href=_data_uri(illustration),
        )
        png = render_png(
            svg,
            width=self._config.width,
            height=self._config.height,
        )
        await progress(GenerationStage.QUALITY_CONTROL, 98)
        return GeneratedIllustration(
            image_bytes=png,
            width=self._config.width,
            height=self._config.height,
            mime_type="image/png",
        )

    async def _generate_illustration(
        self,
        visual_plan: VisualPlan,
        progress: Callable[[GenerationStage, int], Awaitable[None]],
    ) -> GeneratedIllustration:
        request = build_illustration_request(visual_plan)
        await progress(GenerationStage.GENERATING, 60)
        return await self._image_provider.generate(
            prompt=request.prompt,
            width=self._config.width,
            height=self._config.height,
        )


def _data_uri(image: GeneratedIllustration) -> str:
    encoded = base64.b64encode(image.image_bytes).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded}"


__all__ = ["ProductionGenerationPipeline", "ProductionPipelineConfig"]
