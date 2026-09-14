"""Research router that prefers strong medical evidence and degrades safely."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from gqmrmed.contracts.research import EvidenceSource, ResearchRequest

ResearchProvider = Callable[[ResearchRequest], Awaitable[list[EvidenceSource]]]


class HybridResearchProvider:
    """Run independent research sources concurrently and merge provenance."""

    def __init__(self, *providers: ResearchProvider) -> None:
        if not providers:
            raise ValueError("research_router_requires_provider")
        self.providers = tuple(providers)

    async def __call__(self, request: ResearchRequest) -> list[EvidenceSource]:
        results = await asyncio.gather(
            *(self._safe_call(provider, request) for provider in self.providers)
        )
        merged: list[EvidenceSource] = []
        seen: set[str] = set()
        for sources in results:
            for source in sources:
                if source.source_id in seen:
                    continue
                seen.add(source.source_id)
                merged.append(source)
        merged.sort(key=lambda source: source.evidence_score, reverse=True)
        return merged[: request.max_sources]

    @staticmethod
    async def _safe_call(
        provider: ResearchProvider, request: ResearchRequest
    ) -> list[EvidenceSource]:
        try:
            return await provider(request)
        except Exception:  # noqa: BLE001 - isolate an individual research backend.
            return []


__all__ = ["HybridResearchProvider", "ResearchProvider"]
