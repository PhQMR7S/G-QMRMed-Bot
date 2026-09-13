import pytest

from gqmrmed.ai.providers import ProviderDescriptor, ProviderRouter
from gqmrmed.contracts.research import (
    EvidenceSource,
    MedicalClaim,
    ResearchBundle,
    ResearchRequest,
    SourceType,
    SynthesizedContent,
)
from gqmrmed.services.medical_pipeline import build_medical_plan


class FakeResearchProvider:
    async def __call__(self, request: ResearchRequest) -> list[EvidenceSource]:
        return [
            EvidenceSource(
                source_id="pubmed:1",
                source_type=SourceType.PUBMED,
                title=request.query,
                abstract="Evidence.",
                published_year=2026,
                url="https://pubmed.ncbi.nlm.nih.gov/1/",
                pmid="1",
                evidence_score=1.0,
            )
        ]


class FailingProvider:
    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        raise RuntimeError("provider unavailable")


class WorkingProvider:
    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        return SynthesizedContent(
            title="DKA",
            key_points=["Metabolic emergency"],
            claims=[
                MedicalClaim(
                    claim_id="c1",
                    text="DKA is a metabolic emergency.",
                    evidence_ids=["pubmed:1"],
                    confidence=0.95,
                    critical=True,
                )
            ],
        )


@pytest.mark.asyncio
async def test_router_falls_back_then_pipeline_validates_evidence() -> None:
    router = ProviderRouter(
        [
            (ProviderDescriptor(name="first", model="test", cost_tier="free"), FailingProvider()),
            (ProviderDescriptor(name="second", model="test", cost_tier="free"), WorkingProvider()),
        ]
    )
    plan = await build_medical_plan(
        user_input="DKA emergency",
        research_request=ResearchRequest(query="diabetic ketoacidosis"),
        research_provider=FakeResearchProvider(),
        synthesis_provider=router,
    )
    assert plan.content.claims[0].evidence_ids == ["pubmed:1"]
    assert plan.visual_plan.aspect_ratio == "9:16"


@pytest.mark.asyncio
async def test_router_reports_all_provider_failures() -> None:
    router = ProviderRouter(
        [
            (ProviderDescriptor(name="first", model="test"), FailingProvider()),
            (ProviderDescriptor(name="second", model="test"), FailingProvider()),
        ]
    )
    with pytest.raises(RuntimeError, match="all_synthesis_providers_failed"):
        await router.synthesize(
            user_input="DKA",
            research=ResearchBundle(query="DKA", sources=[]),
        )
