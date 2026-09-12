import pytest

from gqmrmed.contracts.research import (
    ArchitectureType,
    EvidenceSource,
    MedicalClaim,
    ResearchBundle,
    ResearchRequest,
    SourceType,
    SynthesizedContent,
)
from gqmrmed.research.pubmed import PubMedResearchProvider, _score_record
from gqmrmed.services.medical_pipeline import build_medical_plan
from gqmrmed.services.research import validate_synthesis_evidence
from gqmrmed.services.visual_architecture import select_visual_architecture


class FakeResearchProvider:
    async def __call__(self, request: ResearchRequest) -> list[EvidenceSource]:
        return [
            EvidenceSource(
                source_id="pubmed:1",
                source_type=SourceType.PUBMED,
                title=request.query,
                abstract="Evidence.",
                published_year=2026,
                url="https://pubmed.ncbi.nlm.nih.gov/1/",
                pmid="1",
                evidence_score=1.0,
            )
        ]


class FakeSynthesisProvider:
    async def synthesize(self, *, user_input: str, research: ResearchBundle) -> SynthesizedContent:
        assert user_input == "DKA emergency"
        assert research.sources
        return SynthesizedContent(
            title="Diabetic ketoacidosis",
            key_points=["Metabolic emergency"],
            claims=[
                MedicalClaim(
                    claim_id="c1",
                    text="DKA is a metabolic emergency.",
                    evidence_ids=["pubmed:1"],
                    confidence=0.95,
                    critical=True,
                )
            ],
        )


def test_pubmed_record_score_prefers_complete_records() -> None:
    assert _score_record(abstract="", year=None) < _score_record(abstract="Evidence", year=2026)


def test_visual_architecture_selects_emergency_algorithm() -> None:
    content = SynthesizedContent(
        title="DKA emergency management",
        key_points=["Danger signs", "Initial actions"],
        claims=[
            MedicalClaim(
                claim_id="c1",
                text="Metabolic emergency",
                evidence_ids=["pubmed:1"],
                confidence=0.9,
            )
        ],
    )
    plan = select_visual_architecture(topic="DKA emergency", content=content)
    assert plan.architecture is ArchitectureType.CLINICAL_EMERGENCY_ALGORITHM
    assert plan.aspect_ratio == "9:16"
    assert plan.render_exact_text is True
    assert plan.watermark == "GQMRMed"


@pytest.mark.asyncio
async def test_phase4_pipeline_keeps_evidence_traceability() -> None:
    plan = await build_medical_plan(
        user_input="DKA emergency",
        research_request=ResearchRequest(query="diabetic ketoacidosis"),
        research_provider=FakeResearchProvider(),
        synthesis_provider=FakeSynthesisProvider(),
    )
    assert plan.research.sources[0].source_id == "pubmed:1"
    assert plan.content.claims[0].evidence_ids == ["pubmed:1"]


def test_unknown_evidence_is_rejected() -> None:
    evidence = ResearchBundle(
        query="DKA",
        sources=[],
    )
    with pytest.raises(ValueError, match="medical_claim_references_unknown_evidence"):
        validate_synthesis_evidence(
            claim_evidence_ids=[["pubmed:missing"]],
            evidence=evidence,
        )


def test_pubmed_parser_extracts_provenance() -> None:
    xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
    <ArticleTitle>DKA</ArticleTitle><Abstract><AbstractText>Evidence text.</AbstractText></Abstract>
    <Journal><Title>Example Journal</Title></Journal></Article><PubmedData><History>
    </History></PubmedData></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    records = PubMedResearchProvider._parse_records(xml)
    assert records[0].source_id == "pubmed:123"
    assert records[0].url.endswith("/123/")
