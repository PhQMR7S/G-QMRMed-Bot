"""End-to-end single-image medical infographic production pipeline."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from gqmrmed.ai.design_preferences import DesignPreferences, extract_design_preferences
from gqmrmed.ai.infographic_design import build_design_spec, detect_language_mode
from gqmrmed.ai.infographic_qa import validate_design_spec
from gqmrmed.ai.infographic_renderer import render_infographic_page
from gqmrmed.contracts.generation import GenerationStage
from gqmrmed.contracts.research import ResearchBundle, ResearchRequest, SynthesizedContent
from gqmrmed.db.models import GenerationJob
from gqmrmed.generation.providers import GeneratedIllustration, ImageGenerationProvider
from gqmrmed.services.quality import validate_png_contract
from gqmrmed.services.research import (
    ResearchProvider,
    research_medical_topic,
    validate_synthesis_evidence,
)
from gqmrmed.services.visual_architecture import select_visual_architecture


class SynthesisService(Protocol):
    async def synthesize(
        self, *, user_input: str, research: ResearchBundle
    ) -> SynthesizedContent: ...


@dataclass(frozen=True, slots=True)
class ProductionPipelineConfig:
    """Canonical 1024x1536 canvas matching the supplied master reference."""

    width: int = 1024
    height: int = 1536

    def __post_init__(self) -> None:
        if self.width * 3 != self.height * 2:
            raise ValueError("production_canvas_must_be_2_3")


class ProductionGenerationPipeline:
    """Research, evidence-lock, plan, illustrate, and render exactly one image."""

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

        design_preferences = _design_preferences_for_job(job, user_input)
        await progress(GenerationStage.RESEARCHING, 10)
        research = await research_medical_topic(
            ResearchRequest(query=user_input, max_sources=8),
            self._research_provider,
        )

        await progress(GenerationStage.SYNTHESIZING, 30)
        content = await self._synthesis_provider.synthesize(
            user_input=user_input,
            research=research,
        )
        validate_synthesis_evidence(
            claim_evidence_ids=[claim.evidence_ids for claim in content.claims],
            evidence=research,
        )
        language = detect_language_mode(user_input)
        _validate_content_language(content, language)

        await progress(GenerationStage.ARCHITECTURE, 50)
        visual_plan = select_visual_architecture(topic=user_input, content=content)
        design = build_design_spec(
            topic=user_input,
            content=content,
            visual_plan=visual_plan,
            language=language,
            design_preferences=design_preferences,
        )
        validate_design_spec(design)
        page = design.pages[0]

        await progress(GenerationStage.GENERATING, 60)
        illustration = await self._image_provider.generate(
            prompt=design.illustration_prompt,
            width=self._config.width,
            height=self._config.height,
        )
        if illustration.width != self._config.width or illustration.height != self._config.height:
            raise ValueError("illustration_dimensions_mismatch")

        await progress(GenerationStage.RENDERING, 85)
        png = render_infographic_page(design, page, illustration)

        await progress(GenerationStage.QUALITY_CONTROL, 98)
        validate_png_contract(png, width=self._config.width, height=self._config.height)
        return GeneratedIllustration(
            image_bytes=png,
            width=self._config.width,
            height=self._config.height,
            mime_type="image/png",
        )


def _design_preferences_for_job(job: GenerationJob, user_input: str) -> DesignPreferences:
    """Use structured metadata when present and fall back to natural-language controls."""
    metadata = job.input_metadata or {}
    raw = metadata.get("design_preferences")
    if isinstance(raw, dict):
        try:
            return DesignPreferences(**raw)
        except (TypeError, ValueError):
            pass
    return extract_design_preferences(user_input)


def _validate_content_language(content: SynthesizedContent, language: str) -> None:
    """Reject provider output that would visibly violate the requested language."""
    text = " ".join(
        [
            content.title,
            content.subtitle,
            *content.key_points,
            *(claim.text for claim in content.claims),
            *content.cautions,
        ]
    )
    ar_count = sum("\u0600" <= char <= "\u06ff" for char in text)
    latin_count = sum("a" <= char.lower() <= "z" for char in text)
    if language == "ar" and (ar_count < 20 or latin_count > ar_count * 0.35):
        raise ValueError("synthesis_language_mismatch_ar")
    if language == "en" and ar_count > 0:
        raise ValueError("synthesis_language_mismatch_en")
    if language == "mixed" and not (ar_count >= 10 and latin_count >= 10):
        raise ValueError("synthesis_language_mismatch_mixed")


__all__ = ["ProductionGenerationPipeline", "ProductionPipelineConfig"]
