from typing import cast
from uuid import uuid4

import pytest

from gqmrmed.contracts.generation import GenerationStage
from gqmrmed.contracts.research import (
    ArchitectureType,
    EvidenceSource,
    MedicalClaim,
    ResearchBundle,
    ResearchRequest,
    SourceType,
    SynthesizedContent,
    VisualPlan,
)
from gqmrmed.db.models import GenerationJob
from gqmrmed.generation.providers import GeneratedIllustration
from gqmrmed.rendering.raster import render_png
from gqmrmed.rendering.svg import render_svg
from gqmrmed.services.production_pipeline import ProductionGenerationPipeline


class FakeSynthesis:
    async def synthesize(
        self, *, user_input: str, research: ResearchBundle
    ) -> SynthesizedContent:
        del user_input, research
        return SynthesizedContent(
            title="Acute myocardial infarction",
            subtitle="Core pathophysiology",
            key_points=[
                "Plaque rupture can trigger coronary thrombosis.",
                "Ischemia reduces myocardial oxygen supply.",
            ],
            claims=[
                MedicalClaim(
                    claim_id="c1",
                    text="Acute coronary thrombosis can cause myocardial ischemia.",
                    evidence_ids=["pubmed:1"],
                    confidence=0.9,
                    critical=True,
                )
            ],
        )


class FakeImage:
    async def generate(
        self, *, prompt: str, width: int, height: int
    ) -> GeneratedIllustration:
        del prompt
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}"><rect width="100%" height="100%" fill="#dddddd"/></svg>'
        )
        return GeneratedIllustration(
            image_bytes=render_png(svg, width=width, height=height),
            width=width,
            height=height,
        )


async def fake_research(request: ResearchRequest) -> list[EvidenceSource]:
    assert request.query
    return [
        EvidenceSource(
            source_id="pubmed:1",
            source_type=SourceType.PUBMED,
            title="Example evidence",
            abstract="Example abstract.",
            url="https://pubmed.ncbi.nlm.nih.gov/1/",
            pmid="1",
            published_year=2025,
            evidence_score=1.0,
        )
    ]


@pytest.mark.asyncio
async def test_pipeline_returns_final_9_16_png() -> None:
    pipeline = ProductionGenerationPipeline(
        research_provider=fake_research,
        synthesis_provider=FakeSynthesis(),
        image_provider=FakeImage(),
    )
    job = cast(GenerationJob, type("Job", (), {"input_text": "acute myocardial infarction", "id": uuid4()})())
    seen: list[GenerationStage] = []

    async def progress(stage: GenerationStage, value: int) -> None:
        del value
        seen.append(stage)

    result = await pipeline.run(job, progress)
    assert result.mime_type == "image/png"
    assert result.width == 1080
    assert result.height == 1920
    assert result.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert seen == [
        GenerationStage.RESEARCHING,
        GenerationStage.SYNTHESIZING,
        GenerationStage.ARCHITECTURE,
        GenerationStage.GENERATING,
        GenerationStage.RENDERING,
        GenerationStage.QUALITY_CONTROL,
    ]


def test_svg_renders_exact_text_and_watermark() -> None:
    content = SynthesizedContent(
        title="Test",
        key_points=["Important medical point."],
        claims=[
            MedicalClaim(
                claim_id="c1",
                text="Evidence-linked claim",
                evidence_ids=["pubmed:1"],
                confidence=1.0,
            )
        ],
    )
    plan = VisualPlan(
        architecture=ArchitectureType.DISEASE_MASTER_CARD,
        sections=["overview"],
        illustration_prompt="medical illustration",
    )
    svg = render_svg(content=content, visual_plan=plan)
    assert "Important medical point." in svg
    assert "Educational medical information" in svg
    assert "GQMRMed" in svg
