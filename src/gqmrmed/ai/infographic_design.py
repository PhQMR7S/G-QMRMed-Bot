"""Deterministic QMRMed single-image infographic design system.

The image model supplies artwork only. This module owns the editorial layout,
content capacity, reference-driven visual language, exact-text policy, and branding rules.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan


class TemplateFamily(StrEnum):
    CLINICAL = "clinical"
    MECHANISM = "mechanism"
    COMPARISON = "comparison"
    DRUG = "drug"
    DIAGNOSIS = "diagnosis"
    TREATMENT = "treatment"
    SYMPTOMS = "symptoms"
    ANATOMY = "anatomy"
    EDUCATIONAL = "educational"


class TextBlock(BaseModel):
    """Exact text that may appear in the final image."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2_000)
    role: str = Field(min_length=1, max_length=32)
    importance: int = Field(default=1, ge=1, le=5)


class InfographicPage(BaseModel):
    """The single final page returned to the user."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(default=1, ge=1, le=1)
    title: str = Field(min_length=1, max_length=160)
    sections: list[str] = Field(min_length=1, max_length=8)
    blocks: list[TextBlock] = Field(min_length=1, max_length=12)


class BrandingSpec(BaseModel):
    """Branding is composited after AI generation and never hallucinated by it."""

    model_config = ConfigDict(extra="forbid")

    telegram_handle: str = "QMR7S"
    position: str = "bottom_safe_zone"
    style: str = "frosted_glass"
    opacity: float = Field(default=0.82, ge=0.1, le=1.0)


class InfographicDesignSpec(BaseModel):
    """Complete deterministic rendering contract for exactly one image."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=20_000)
    language: str = Field(default="ar", min_length=2, max_length=8)
    aspect_ratio: str = "4:5"
    template: TemplateFamily
    pages: list[InfographicPage] = Field(min_length=1, max_length=1)
    illustration_prompt: str = Field(min_length=1, max_length=8_000)
    branding: BrandingSpec = Field(default_factory=BrandingSpec)


MASTER_VISUAL_LANGUAGE = """
QMRMed master visual language: premium editorial medical infographic.
Use the supplied reference designs as visual-language references only, never copy
specific content. Preserve their shared characteristics: clean 4:5 grid, rounded
cards, soft clinical pastel palette, strong title hierarchy, generous whitespace,
compact information cards, topic-specific medical illustrations, clear arrows and
pathways, subtle gradients, restrained shadows, balanced density, precise alignment,
modern Arabic typography with correct RTL, and a polished clinical-publication feel.
Use red only for danger/warnings, green for favorable or treatment states, blue/teal
for information and mechanism, purple as a secondary accent, and amber for caution.
Adapt the composition to the topic: comparison topics use comparison panels, drug
topics use medication-focused cards, mechanisms use causal diagrams, anatomy uses
central anatomy with callouts, and symptom/clinical topics use grouped cards.
Never add decorative medical objects unrelated to the topic. Never place a logo,
watermark, signature, or readable text in the illustration itself.
""".strip()


TEMPLATE_HINTS: dict[TemplateFamily, str] = {
    TemplateFamily.CLINICAL: (
        "Use a strong title, central clinical illustration, and balanced information cards."
    ),
    TemplateFamily.MECHANISM: "Use a causal pathway with arrows and mechanism nodes.",
    TemplateFamily.COMPARISON: (
        "Use a symmetrical comparison matrix with shared attributes and key discriminators."
    ),
    TemplateFamily.DRUG: (
        "Use medication-focused cards, mechanism/uses/cautions sections, and a dominant drug asset."
    ),
    TemplateFamily.DIAGNOSIS: (
        "Use a decision-oriented diagnostic flow with tests, findings, and interpretation."
    ),
    TemplateFamily.TREATMENT: (
        "Use a stepwise treatment pathway with priority, monitoring, and escalation blocks."
    ),
    TemplateFamily.SYMPTOMS: (
        "Use grouped symptom clusters with a clear hierarchy and warning strip only when "
        "evidence supports it."
    ),
    TemplateFamily.ANATOMY: (
        "Use a central anatomical illustration with concise callout cards."
    ),
    TemplateFamily.EDUCATIONAL: (
        "Use a flexible teaching-card layout with definition and high-yield takeaways."
    ),
}


def choose_template(topic: str, visual_plan: VisualPlan) -> TemplateFamily:
    """Map the medical architecture to the QMRMed reference visual family."""
    value = visual_plan.architecture.value
    if "mechanism" in value or "pathophysiology" in value or "concept_map" in value:
        return TemplateFamily.MECHANISM
    if "comparison" in value:
        return TemplateFamily.COMPARISON
    if "drug" in value:
        return TemplateFamily.DRUG
    if "emergency" in value or "treatment" in value:
        return TemplateFamily.TREATMENT
    if "laboratory" in value or "ecg" in value or "radiology" in value:
        return TemplateFamily.DIAGNOSIS
    if "anatomy" in value:
        return TemplateFamily.ANATOMY
    if "step_by_step" in value:
        return TemplateFamily.CLINICAL
    if "revision" in value or "disease" in value:
        return TemplateFamily.EDUCATIONAL
    if any(word in topic.lower() for word in ("symptom", "signs", "أعراض", "علامات")):
        return TemplateFamily.SYMPTOMS
    return TemplateFamily.CLINICAL


def _compact(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def _select_single_image_blocks(content: SynthesizedContent) -> list[TextBlock]:
    """Select high-value evidence-locked facts that fit one readable image."""
    blocks: list[TextBlock] = []
    if content.subtitle:
        blocks.append(
            TextBlock(
                text=_compact(content.subtitle, 180),
                role="subtitle",
                importance=4,
            )
        )

    for point in content.key_points:
        blocks.append(TextBlock(text=_compact(point, 220), role="point", importance=3))

    claims = sorted(
        content.claims,
        key=lambda claim: (claim.critical, claim.confidence),
        reverse=True,
    )
    for claim in claims:
        blocks.append(
            TextBlock(
                text=_compact(claim.text, 300),
                role="danger" if claim.critical else "claim",
                importance=5 if claim.critical else 3,
            )
        )

    for caution in content.cautions:
        blocks.append(
            TextBlock(text=_compact(caution, 220), role="caution", importance=5)
        )

    ranked = sorted(
        enumerate(blocks),
        key=lambda item: (item[1].importance, -item[0]),
        reverse=True,
    )
    return [block for _, block in ranked[:9]]


def build_design_spec(
    *,
    topic: str,
    content: SynthesizedContent,
    visual_plan: VisualPlan,
    language: str = "ar",
    max_blocks_per_page: int = 9,
) -> InfographicDesignSpec:
    """Build exactly one readable image from evidence-locked content."""
    if max_blocks_per_page < 4 or max_blocks_per_page > 9:
        raise ValueError("single_image_capacity_must_be_between_4_and_9")

    template = choose_template(topic, visual_plan)
    selected = _select_single_image_blocks(content)[:max_blocks_per_page]
    if not selected:
        raise ValueError("single_image_content_required")

    page_title = TextBlock(text=_compact(content.title, 120), role="title", importance=5)
    sections = list(dict.fromkeys(visual_plan.sections[:8])) or ["key points"]
    page = InfographicPage(
        page_number=1,
        title=_compact(content.title, 160),
        sections=sections,
        blocks=[page_title, *selected],
    )

    prompt = (
        MASTER_VISUAL_LANGUAGE
        + "\n\n"
        + TEMPLATE_HINTS[template]
        + "\nTopic: "
        + _compact(topic, 500)
        + "\nArchitecture: "
        + visual_plan.architecture.value
        + "\nIllustration brief: "
        + visual_plan.illustration_prompt
        + "\nIMPORTANT: artwork only; no readable text, labels, numbers, logos, or watermark."
    )
    return InfographicDesignSpec(
        topic=topic,
        language=language,
        aspect_ratio="4:5",
        template=template,
        pages=[page],
        illustration_prompt=prompt[:8_000],
    )


__all__ = [
    "BrandingSpec",
    "InfographicDesignSpec",
    "InfographicPage",
    "MASTER_VISUAL_LANGUAGE",
    "TEMPLATE_HINTS",
    "TemplateFamily",
    "TextBlock",
    "build_design_spec",
    "choose_template",
]
