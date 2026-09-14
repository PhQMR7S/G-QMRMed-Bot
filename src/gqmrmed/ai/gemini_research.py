"""Google-grounded research adapter with provenance-aware evidence extraction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from gqmrmed.contracts.research import (
    EvidenceSource,
    ResearchRequest,
    SourceType,
)

_TRUSTED_DOMAINS = {
    "who.int",
    "cdc.gov",
    "fda.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "nice.org.uk",
    "ema.europa.eu",
    "cochrane.org",
    "nejm.org",
    "thelancet.com",
    "jamanetwork.com",
    "bmj.com",
    "nature.com",
    "science.org",
    "pubmed.ncbi.nlm.nih.gov",
}


@dataclass(frozen=True, slots=True)
class GeminiResearchConfig:
    api_key: str
    model: str = "gemini-3.8-flash"
    timeout_seconds: float = 120.0


class GeminiGroundedResearchProvider:
    """Retrieve web-grounded evidence and preserve source-to-claim mappings."""

    def __init__(
        self,
        config: GeminiResearchConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def __call__(self, request: ResearchRequest) -> list[EvidenceSource]:
        if not self.config.api_key.strip():
            raise RuntimeError("gemini_research_api_key_missing")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            prompt = (
                "Research the following medical topic for an educational infographic. "
                "Search the web and prioritize official guidelines, regulators, NIH/PubMed, "
                "major medical societies, systematic reviews, and high-quality peer-reviewed "
                "literature. Avoid blogs, SEO pages, forums, and unsourced claims. "
                "Every factual statement must be grounded in retrieved sources. "
                "Return a concise evidence-oriented synthesis; do not give patient-specific "
                "advice.\n\n"
                f"TOPIC: {request.query}"
            )
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.config.model}:generateContent"
            )
            response = await client.post(
                url,
                headers={
                    "x-goog-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "tools": [{"google_search": {}}],
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return _extract_sources(payload, request.max_sources)
        except httpx.HTTPError as exc:
            raise RuntimeError("gemini_research_request_failed") from exc
        finally:
            if owns_client:
                await client.aclose()


def _extract_sources(payload: dict[str, Any], limit: int) -> list[EvidenceSource]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return []
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return []
    metadata = candidate.get("groundingMetadata")
    if not isinstance(metadata, dict):
        return []
    chunks = metadata.get("groundingChunks")
    if not isinstance(chunks, list):
        return []

    text = _candidate_text(candidate)
    summaries: dict[int, list[str]] = {}
    supports = metadata.get("groundingSupports", [])
    if isinstance(supports, list):
        for support in supports:
            if not isinstance(support, dict):
                continue
            segment = support.get("segment")
            indices = support.get("groundingChunkIndices")
            if not isinstance(segment, dict) or not isinstance(indices, list):
                continue
            segment_text = segment.get("text")
            if not isinstance(segment_text, str) or not segment_text.strip():
                continue
            for index in indices:
                if isinstance(index, int):
                    summaries.setdefault(index, []).append(segment_text.strip())

    sources: list[EvidenceSource] = []
    seen_urls: set[str] = set()
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        web = chunk.get("web")
        if not isinstance(web, dict):
            continue
        url = web.get("uri")
        title = web.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not url.strip():
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        domain = _domain(url)
        score = _domain_score(domain)
        abstract_parts = summaries.get(index, [])
        abstract = " ".join(dict.fromkeys(abstract_parts))[:20_000]
        if not abstract and text:
            abstract = text[:4_000]
        source_id = "web_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        sources.append(
            EvidenceSource(
                source_id=source_id,
                source_type=SourceType.WEB,
                title=title[:500],
                abstract=abstract or None,
                url=url[:2_048],
                evidence_score=score,
            )
        )

    sources.sort(key=lambda source: source.evidence_score, reverse=True)
    return sources[:limit]


def _candidate_text(candidate: dict[str, Any]) -> str:
    content = candidate.get("content")
    parts = content.get("parts", []) if isinstance(content, dict) else []
    text_parts = [
        part.get("text")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    return " ".join(text_parts).strip()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _domain_score(domain: str) -> float:
    trusted = any(
        domain == item or domain.endswith("." + item) for item in _TRUSTED_DOMAINS
    )
    if trusted:
        return 0.95
    if domain.endswith((".edu", ".gov")):
        return 0.90
    return 0.70


__all__ = ["GeminiGroundedResearchProvider", "GeminiResearchConfig"]
