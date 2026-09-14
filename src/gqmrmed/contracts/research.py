"""Contracts for evidence retrieval, synthesis, and visual planning."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceType(StrEnum):
    PUBMED = "pubmed"
    WEB = "web"
    USER_INPUT = "user_input"


class EvidenceSource(BaseModel):
    """A traceable medical evidence item used by the synthesis stage."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=128)
    source_type: SourceType
    title: str = Field(min_length=1, max_length=500)
    abstract: str | None = Field(default=None, max_length=20_000)
    journal: str | None = Field(default=None, max_length=500)
    published_year: int | None = Field(default=None, ge=1800, le=2100)
    url: str = Field(min_length=1, max_length=2_048)
    pmid: str | None = Field(default=None, max_length=32)
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("title", "url")
    @classmethod
    def normalize_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("research_required_string_empty")
        return value


class ResearchRequest(BaseModel):
    """Bounded input for the medical research stage."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=20_000)
    max_sources: int = Field(default=8, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("research_query_empty")
        return value


class ResearchBundle(BaseModel):
    """Research output with explicit provenance and search metadata."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=20_000)
    sources: list[EvidenceSource] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class MedicalClaim(BaseModel):
    """A concise factual claim and the evidence supporting it."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=1_000)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    critical: bool = False


class SynthesizedContent(BaseModel):
    """Structured medical content prepared for visual architecture/rendering."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    subtitle: str | None = Field(default=None, max_length=240)
    key_points: list[str] = Field(min_length=1, max_length=12)
    claims: list[MedicalClaim] = Field(min_length=1, max_length=30)
    cautions: list[str] = Field(default_factory=list, max_length=8)
    disclaimer: str = Field(
        default="Educational medical information; not a diagnosis.",
        max_length=240,
    )


class ArchitectureType(StrEnum):
    ANATOMY_EXPLORER = "anatomy_explorer"
    PATHOPHYSIOLOGY_FLOW = "pathophysiology_flow"
    DISEASE_MASTER_CARD = "disease_master_card"
    DRUG_PROFILE = "drug_profile"
    MECHANISM_OF_ACTION = "mechanism_of_action"
    CLINICAL_EMERGENCY_ALGORITHM = "clinical_emergency_algorithm"
    LABORATORY_INTERPRETATION = "laboratory_interpretation"
    ECG_ANALYSIS = "ecg_analysis"
    RADIOLOGY_ANNOTATION = "radiology_annotation"
    COMPARISON_MATRIX = "comparison_matrix"
    TIMELINE = "timeline"
    STEP_BY_STEP_PROCEDURE = "step_by_step_procedure"
    CLINICAL_CASE = "clinical_case"
    CONCEPT_MAP = "concept_map"
    REVISION_EXAM_CARD = "revision_exam_card"
    HYBRID_ANATOMY_ALGORITHM = "hybrid_anatomy_algorithm"
    CUSTOM = "custom"


class VisualPlan(BaseModel):
    """Deterministic visual architecture selected from medical content."""

    model_config = ConfigDict(extra="forbid")

    architecture: ArchitectureType
    aspect_ratio: str = "9:16"
    sections: list[str] = Field(min_length=1, max_length=12)
    emphasis: list[str] = Field(default_factory=list, max_length=12)
    illustration_prompt: str = Field(min_length=1, max_length=4_000)
    render_exact_text: bool = True
    watermark: str = "GQMRMed"
