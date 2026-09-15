from gqmrmed.contracts.research import EvidenceSource, ResearchBundle, SourceType
from gqmrmed.services.research import validate_synthesis_evidence


def _bundle() -> ResearchBundle:
    return ResearchBundle(
        query="PCOS",
        sources=[
            EvidenceSource(
                source_id="pubmed:123456",
                source_type=SourceType.PUBMED,
                title="PCOS",
                abstract="Evidence",
                url="https://pubmed.ncbi.nlm.nih.gov/123456/",
                pmid="123456",
            )
        ],
    )


def test_pubmed_pmid_alias_is_accepted() -> None:
    validate_synthesis_evidence(
        claim_evidence_ids=[["PMID:123456"]],
        evidence=_bundle(),
    )


def test_unknown_pmid_alias_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="medical_claim_references_unknown_evidence"):
        validate_synthesis_evidence(
            claim_evidence_ids=[["PMID:999999"]],
            evidence=_bundle(),
        )
