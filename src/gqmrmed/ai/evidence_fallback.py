"""Safety boundary for synthesis outages.

A medical infographic must never turn raw or unrelated evidence excerpts into
apparently authoritative educational content. If synthesis providers are down,
the generation must fail rather than publish misleading material.
"""
from __future__ import annotations

from gqmrmed.contracts.research import ResearchBundle, SynthesizedContent


def synthesize_from_evidence(user_input: str, research: ResearchBundle) -> SynthesizedContent:
    """Reject unsafe no-model fallback instead of rendering raw evidence as prose."""
    del user_input, research
    raise RuntimeError("medical_synthesis_provider_required")
