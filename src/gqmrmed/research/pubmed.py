"""PubMed E-utilities client used as the primary literature source."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from gqmrmed.contracts.research import EvidenceSource, ResearchRequest, SourceType


@dataclass(frozen=True, slots=True)
class PubMedConfig:
    """Connection and identity settings required by NCBI E-utilities."""

    api_key: str | None = None
    email: str | None = None
    tool: str = "GQMRMed"
    timeout_seconds: float = 15.0


class PubMedResearchProvider:
    """Retrieve a bounded set of PubMed records with explicit provenance."""

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, config: PubMedConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def search(self, request: ResearchRequest) -> list[EvidenceSource]:
        """Search PubMed and fetch abstracts for the best matching records."""
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            params = self._common_params()
            params.update(
                {
                    "db": "pubmed",
                    "term": request.query,
                    "retmax": str(request.max_sources),
                    "retmode": "json",
                }
            )
            response = await client.get(f"{self.base_url}/esearch.fcgi", params=params)
            response.raise_for_status()
            payload = response.json()
            ids = payload.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            fetch_params = self._common_params()
            fetch_params.update(
                {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "rettype": "abstract"}
            )
            fetched = await client.get(f"{self.base_url}/efetch.fcgi", params=fetch_params)
            fetched.raise_for_status()
            return self._parse_records(fetched.text)
        finally:
            if owns_client:
                await client.aclose()

    def _common_params(self) -> dict[str, str]:
        params = {"tool": self.config.tool}
        if self.config.email:
            params["email"] = self.config.email
        if self.config.api_key:
            params["api_key"] = self.config.api_key
        return params

    @staticmethod
    def _parse_records(xml_text: str) -> list[EvidenceSource]:
        root = ET.fromstring(xml_text)
        results: list[EvidenceSource] = []
        for article in root.findall(".//PubmedArticle"):
            pmid = _text(article.find(".//PMID"))
            title = _text(article.find(".//ArticleTitle")) or "Untitled PubMed record"
            abstract_parts = [
                "".join(node.itertext()).strip()
                for node in article.findall(".//Abstract/AbstractText")
                if "".join(node.itertext()).strip()
            ]
            abstract = " ".join(abstract_parts) or None
            journal = _text(article.find(".//Journal/Title"))
            year = _publication_year(article)
            if not pmid:
                continue
            results.append(
                EvidenceSource(
                    source_id=f"pubmed:{pmid}",
                    source_type=SourceType.PUBMED,
                    title=title,
                    abstract=abstract,
                    journal=journal,
                    published_year=year,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    pmid=pmid,
                    evidence_score=_score_record(abstract=abstract, year=year),
                )
            )
        return sorted(results, key=lambda item: item.evidence_score, reverse=True)


def _text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def _publication_year(article: ET.Element) -> int | None:
    for path in (".//PubDate/Year", ".//PubDate/MedlineDate"):
        value = _text(article.find(path))
        if value:
            for token in value.split():
                if len(token) == 4 and token.isdigit():
                    return int(token)
    return None


def _score_record(*, abstract: str | None, year: int | None) -> float:
    score = 0.45
    if abstract:
        score += 0.35
    if year is not None:
        score += 0.20
    return min(score, 1.0)
