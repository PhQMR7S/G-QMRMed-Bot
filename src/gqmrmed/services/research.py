"""Medical research orchestration with provenance validation."""

from collections.abc import Awaitable, Callable

from gqmrmed.contracts.research import EvidenceSource, ResearchBundle, ResearchRequest

ResearchProvider = Callable[[ResearchRequest], Awaitable[list[EvidenceSource]]]


async def research_medical_topic(
    request: ResearchRequest,
    provider: ResearchProvider,
) -> ResearchBundle:
    """Retrieve evidence and enforce deterministic provenance rules."""
    raw_sources = await provider(request)
    sources = _deduplicate_sources(raw_sources)
    warnings: list[str] = []

    if not sources:
        warnings.append("no_pubmed_evidence_found")
    if sources and not any(source.abstract for source in sources):
        warnings.append("evidence_has_no_abstracts")

    return ResearchBundle(query=request.query, sources=sources[: request.max_sources], warnings=warnings)


def _deduplicate_sources(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    seen: set[str] = set()
    unique: list[EvidenceSource] = []
    for source in sorted(sources, key=lambda item: item.evidence_score, reverse=True):
        if source.source_id in seen:
            continue
        seen.add(source.source_id)
        unique.append(source)
    return unique


def validate_synthesis_evidence(
    *,
    claim_evidence_ids: list[list[str]],
    evidence: ResearchBundle,
) -> None:
    """Reject synthesized claims that cite unknown or missing evidence."""
    known_ids = {source.source_id for source in evidence.sources}
    for evidence_ids in claim_evidence_ids:
        if not evidence_ids:
            raise ValueError("medical_claim_without_evidence")
        if any(source_id not in known_ids for source_id in evidence_ids):
            raise ValueError("medical_claim_references_unknown_evidence")
