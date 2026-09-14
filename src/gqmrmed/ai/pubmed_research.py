"""PubMed E-utilities adapter used as the high-confidence medical fallback."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx

from gqmrmed.contracts.research import EvidenceSource, ResearchRequest, SourceType


@dataclass(frozen=True, slots=True)
class PubMedResearchConfig:
    email: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 30.0


class PubMedResearchProvider:
    """Search PubMed and retrieve titles/abstracts with explicit provenance."""

    def __init__(
        self,
        config: PubMedResearchConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def __call__(self, request: ResearchRequest) -> list[EvidenceSource]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": request.query,
            "retmode": "json",
            "retmax": min(request.max_sources, 20),
            "sort": "relevance",
        }
        _add_identity_params(params, self.config)
        try:
            search = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params=params,
            )
            search.raise_for_status()
            payload = search.json()
            ids = payload.get("esearchresult", {}).get("idlist", [])
            if not isinstance(ids, list) or not ids:
                return []

            fetch_params = {
                "db": "pubmed",
                "id": ",".join(str(item) for item in ids),
                "retmode": "xml",
            }
            _add_identity_params(fetch_params, self.config)
            fetched = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                params=fetch_params,
            )
            fetched.raise_for_status()
            return _parse_pubmed(fetched.text, limit=request.max_sources)
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("pubmed_research_request_failed") from exc
        finally:
            if owns_client:
                await client.aclose()


def _add_identity_params(
    params: dict[str, Any], config: PubMedResearchConfig
) -> None:
    if config.email:
        params["email"] = config.email
    if config.api_key:
        params["api_key"] = config.api_key


def _parse_pubmed(xml_text: str, *, limit: int) -> list[EvidenceSource]:
    root = ET.fromstring(xml_text)
    sources: list[EvidenceSource] = []
    for article in root.findall(".//PubmedArticle")[:limit]:
        pmid = _text(article.find(".//PMID"))
        title = _text(article.find(".//ArticleTitle"))
        abstract_nodes = article.findall(".//Abstract/AbstractText")
        abstract = " ".join(
            _text(node) for node in abstract_nodes if _text(node)
        ).strip()
        journal = _text(article.find(".//Journal/Title"))
        year = _publication_year(article)
        if not pmid or not title:
            continue
        sources.append(
            EvidenceSource(
                source_id=f"pmid:{pmid}",
                source_type=SourceType.PUBMED,
                title=title[:500],
                abstract=abstract[:20_000] or None,
                journal=journal[:500] or None,
                published_year=year,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                pmid=pmid,
                evidence_score=0.96 if abstract else 0.90,
            )
        )
    return sources


def _publication_year(article: ET.Element) -> int | None:
    for path in (".//PubDate/Year", ".//PubDate/MedlineDate"):
        value = _text(article.find(path))
        if not value:
            continue
        for token in value.split():
            if len(token) == 4 and token.isdigit():
                year = int(token)
                if 1800 <= year <= 2100:
                    return year
    return None


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


__all__ = ["PubMedResearchConfig", "PubMedResearchProvider"]
