"""Evidence-grounded no-network synthesis fallback.

This fallback never invents medical facts. It converts retrieved evidence into a
traceable, clearly caveated content structure so the pipeline can continue when
all remote synthesis providers are unavailable.
"""
from __future__ import annotations

import re

from gqmrmed.contracts.research import MedicalClaim, ResearchBundle, SynthesizedContent


def synthesize_from_evidence(user_input: str, research: ResearchBundle) -> SynthesizedContent:
    """Build a conservative synthesis from retrieved evidence excerpts only."""
    sources = research.sources[:8]
    if not sources:
        raise RuntimeError("evidence_fallback_requires_sources")

    claims: list[MedicalClaim] = []
    points: list[str] = []
    for index, source in enumerate(sources[:6], start=1):
        points.append(source.title[:180])
        abstract = (source.abstract or "").strip()
        sentence = re.split(r"(?<=[.!?])\s+", abstract)[0].strip() if abstract else source.title
        claims.append(
            MedicalClaim(
                claim_id=f"evidence_{index}",
                text=sentence[:900],
                evidence_ids=[source.source_id],
                confidence=min(0.85, max(0.25, source.evidence_score)),
                critical=False,
            )
        )

    return SynthesizedContent(
        title=user_input[:160],
        subtitle="Evidence-grounded medical overview",
        key_points=points or ["Evidence retrieved from PubMed"],
        claims=claims,
        cautions=[
            "Automatic synthesis provider was unavailable; content is presented as evidence excerpts.",
            "Educational medical information; not a diagnosis.",
        ],
    )
