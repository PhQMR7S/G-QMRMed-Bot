"""End-to-end QMRMed infographic generation orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import cairosvg

from gqmrmed.ai.gemini_research import GeminiGroundedResearchProvider, GeminiResearchConfig
from gqmrmed.ai.image_providers import (
    CloudflareImageConfig,
    CloudflareImageProvider,
    GeminiImageConfig,
    GeminiImageProvider,
    QwenImageConfig,
    QwenImageProvider,
)
from gqmrmed.ai.infographic_design import InfographicDesignSpec, build_design_spec
from gqmrmed.ai.infographic_renderer import RenderConfig, render_infographic_page
from gqmrmed.ai.pubmed_research import PubMedResearchConfig, PubMedResearchProvider
from gqmrmed.ai.research_router import HybridResearchProvider
from gqmrmed.config import Settings
from gqmrmed.contracts.research import ResearchRequest, SynthesizedContent, VisualPlan
from gqmrmed.generation.providers import (
    GeneratedIllustration,
    ImageGenerationError,
    ImageGenerationProvider,
)
from gqmrmed.services.medical_pipeline import MedicalPlan, SynthesisProvider, build_medical_plan
from gqmrmed.services.research import ResearchProvider
from gqmrmed.services.visual_architecture import select_visual_architecture


@dataclass(frozen=True, slots=True)
class InfographicGenerationResult:
    """Final image pages plus provenance metadata kept outside visible artwork."""

    images: tuple[bytes, ...]
    design: InfographicDesignSpec
    source_urls: tuple[str, ...]


class InfographicPipeline:
    """Generate evidence-locked, multi-page QMRMed infographics."""

    def __init__(
        self,
        *,
        image_providers: tuple[ImageGenerationProvider, ...],
        renderer_config: RenderConfig | None = None,
    ) -> None:
        if not image_providers:
            raise ValueError("infographic_requires_image_provider")
        self.image_providers = image_providers
        self.renderer_config = renderer_config or RenderConfig()

    @classmethod
    def from_settings(cls, settings: Settings) -> "InfographicPipeline":
        providers: list[ImageGenerationProvider] = []
        for name in _csv(settings.image_provider_order):
            if (
                name == "cloudflare"
                and settings.cloudflare_api_token
                and settings.cloudflare_account_id
            ):
                providers.append(
                    CloudflareImageProvider(
                        CloudflareImageConfig(
                            api_token=settings.cloudflare_api_token,
                            account_id=settings.cloudflare_account_id,
                            model=settings.cloudflare_image_model,
                            timeout_seconds=settings.image_generation_timeout_seconds,
                        )
                    )
                )
            elif name == "qwen" and settings.dashscope_api_key and settings.dashscope_base_url:
                providers.append(
                    QwenImageProvider(
                        QwenImageConfig(
                            api_key=settings.dashscope_api_key,
                            base_url=settings.dashscope_base_url,
                            model=settings.dashscope_image_model,
                            timeout_seconds=settings.image_generation_timeout_seconds,
                        )
                    )
                )
            elif name == "gemini" and settings.gemini_api_key:
                providers.append(
                    GeminiImageProvider(
                        GeminiImageConfig(
                            api_key=settings.gemini_api_key,
                            model=settings.gemini_image_model,
                            timeout_seconds=settings.gemini_timeout_seconds,
                        )
                    )
                )
        providers.append(_BlankIllustrationProvider())
        return cls(image_providers=tuple(providers))

    async def generate(
        self, *, user_input: str, plan: MedicalPlan
    ) -> InfographicGenerationResult:
        design = build_design_spec(
            topic=user_input,
            content=plan.content,
            visual_plan=plan.visual_plan,
            language="ar",
        )
        images: list[bytes] = []
        for page in design.pages:
            illustration = await self._generate_illustration(design.illustration_prompt)
            images.append(
                render_infographic_page(
                    design,
                    page,
                    illustration,
                    config=self.renderer_config,
                )
            )
        return InfographicGenerationResult(
            images=tuple(images),
            design=design,
            source_urls=tuple(source.url for source in plan.research.sources),
        )

    async def _generate_illustration(self, prompt: str) -> GeneratedIllustration:
        errors: list[str] = []
        for provider in self.image_providers:
            try:
                return await provider.generate(prompt=prompt, width=1024, height=1280)
            except (ImageGenerationError, RuntimeError) as exc:
                errors.append(type(exc).__name__)
        raise ImageGenerationError("all_infographic_image_providers_failed:" + ",".join(errors))


async def build_infographic_medical_plan(
    *,
    user_input: str,
    settings: Settings,
    synthesis_provider: SynthesisProvider,
) -> MedicalPlan:
    """Build the research-first medical plan used by the final compositor."""
    providers: list[ResearchProvider] = []
    if settings.gemini_api_key:
        providers.append(
            GeminiGroundedResearchProvider(
                GeminiResearchConfig(
                    api_key=settings.gemini_api_key,
                    model=settings.gemini_text_model,
                    timeout_seconds=settings.gemini_timeout_seconds,
                )
            )
        )
    providers.append(
        PubMedResearchProvider(
            PubMedResearchConfig(
                email=settings.research_email,
                api_key=settings.research_api_key,
            )
        )
    )
    research_provider = HybridResearchProvider(*providers)
    return await build_medical_plan(
        user_input=user_input,
        research_request=ResearchRequest(query=user_input, max_sources=10),
        research_provider=research_provider,
        synthesis_provider=synthesis_provider,
    )


def build_visual_plan(*, topic: str, content: SynthesizedContent) -> VisualPlan:
    """Public helper for callers that already have evidence-locked content."""
    return select_visual_architecture(topic=topic, content=content)


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


class _BlankIllustrationProvider:
    """Zero-network fallback with no readable text or branding."""

    async def generate(self, *, prompt: str, width: int, height: int) -> GeneratedIllustration:
        del prompt
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
          <defs>
            <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#EAF3F7"/>
              <stop offset="1" stop-color="#D9E9E6"/>
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#g)"/>
          <circle cx="50%" cy="42%" r="28%" fill="#FFFFFF" opacity="0.45"/>
          <circle cx="50%" cy="42%" r="18%" fill="none" stroke="#5E93A8" stroke-width="10" opacity="0.45"/>
          <path d="M25% 42% H38% L44% 32% L50% 53% L57% 36% L63% 42% H75%" fill="none" stroke="#5E93A8" stroke-width="10" opacity="0.48"/>
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


__all__ = [
    "InfographicGenerationResult",
    "InfographicPipeline",
    "build_infographic_medical_plan",
    "build_visual_plan",
]
