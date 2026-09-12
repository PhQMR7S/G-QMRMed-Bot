"""Phase 4 pipeline: research -> evidence validation -> synthesis -> visual architecture."""

from dataclasses import dataclass

from gqmrmed.contracts.research import ResearchBundle, ResearchRequest, SynthesizedContent, VisualPlan
from gqmrmed.services.research import ResearchProvider, research_medical_topic, validate_synthesis_evidence
from gqmrmed.services.visual_architecture import select_visual_architecture


class SynthesisProvider:
    """Structural protocol for an async medical content synthesizer."""

    async def synthesize(
        self,
        *,
        user_input: str,
        research: ResearchBundle,
    ) -> SynthesizedContent:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class MedicalPlan:
    """Complete Phase 4 output passed to the future generation worker."""

    research: ResearchBundle
    content: SynthesizedContent
    visual_plan: VisualPlan


async def build_medical_plan(
    *,
    user_input: str,
    research_request: ResearchRequest,
    research_provider: ResearchProvider,
    synthesis_provider: SynthesisProvider,
) -> MedicalPlan:
    """Build a traceable medical content and visual plan."""
    research = await research_medical_topic(research_request, research_provider)
    content = await synthesis_provider.synthesize(user_input=user_input, research=research)
    validate_synthesis_evidence(
        claim_evidence_ids=[claim.evidence_ids for claim in content.claims],
        evidence=research,
    )
    visual_plan = select_visual_architecture(topic=user_input, content=content)
    return MedicalPlan(research=research, content=content, visual_plan=visual_plan)
