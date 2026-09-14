"""Research router that prefers strong medical evidence and degrades safely."""

from __future__ import annotations

import asyncio
import re
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
        queries = split_long_research_query(request.query)
        per_query = max(2, request.max_sources // len(queries))
        tasks = [
            self._search_query(provider, query, per_query)
            for query in queries
            for provider in self.providers
        ]
        results = await asyncio.gather(*tasks)
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
    async def _search_query(
        provider: ResearchProvider,
        query: str,
        max_sources: int,
    ) -> list[EvidenceSource]:
        try:
            result = await provider(
                ResearchRequest(query=query, max_sources=max_sources)
            )
        except Exception:  # noqa: BLE001 - isolate an individual research backend.
            return []
        return result if isinstance(result, list) else []


def split_long_research_query(
    query: str,
    *,
    max_query_length: int = 700,
    max_queries: int = 6,
) -> tuple[str, ...]:
    """Split long user text into bounded, semantically useful research queries."""
    normalized = " ".join(query.split())
    if len(normalized) <= max_query_length:
        return (normalized,)

    segments = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?؟])\s+|[\n;،]+", normalized)
        if segment.strip()
    ]
    chunks: list[str] = []
    current = ""
    for segment in segments:
        if len(segment) <= max_query_length:
            candidate = segment if not current else f"{current} {segment}"
            if len(candidate) <= max_query_length:
                current = candidate
                continue
        if current:
            chunks.append(current)
            current = ""
        words = segment.split()
        while words:
            piece_words: list[str] = []
            while words and len(" ".join(piece_words + [words[0]])) <= max_query_length:
                piece_words.append(words.pop(0))
            if not piece_words:
                piece_words.append(words.pop(0))
            chunks.append(" ".join(piece_words))
    if current:
        chunks.append(current)

    if not chunks:
        return (normalized[:max_query_length],)
    if len(chunks) <= max_queries:
        return tuple(chunks)
    merged_tail = " ".join(chunks[max_queries - 1 :])
    return tuple(chunks[: max_queries - 1] + [merged_tail[:max_query_length]])


__all__ = [
    "HybridResearchProvider",
    "ResearchProvider",
    "split_long_research_query",
]
