"""Research router that prefers strong medical evidence and degrades safely."""

from __future__ import annotations

import asyncio

from gqmrmed.contracts.research import EvidenceSource, ResearchRequest


class HybridResearchProvider:
    """Run independent research sources concurrently and merge provenance."""

    def __init__(self, *providers) -> None:  # type: ignore[no-untyped-def]
        if not providers:
            raise ValueError("research_router_requires_provider")
        self.providers = tuple(provider for provider in providers if provider is not None)

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
    async def _safe_call(provider, request: ResearchRequest) -> list[EvidenceSource]:  # type: ignore[no-untyped-def]
        try:
            result = await provider(request)
        except Exception:  # noqa: BLE001 - isolate an individual research backend.
            return []
        return result if isinstance(result, list) else []


__all__ = ["HybridResearchProvider"]
