"""Deterministic QMRMed infographic design system.

The image model supplies artwork only. This module owns the editorial layout,
content capacity, template family, exact-text policy, and branding rules.
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
    """One coherent page in a multi-page infographic series."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=160)
    sections: list[str] = Field(min_length=1, max_length=8)
    blocks: list[TextBlock] = Field(min_length=1, max_length=24)


class BrandingSpec(BaseModel):
    """Branding is composited after AI generation and never hallucinated by it."""

    model_config = ConfigDict(extra="forbid")

    telegram_handle: str = "QMR7S"
    position: str = "bottom_safe_zone"
    style: str = "frosted_glass"
    opacity: float = Field(default=0.82, ge=0.1, le=1.0)


class InfographicDesignSpec(BaseModel):
    """Complete deterministic rendering contract."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=20_000)
    language: str = Field(default="ar", min_length=2, max_length=8)
    aspect_ratio: str = "4:5"
    template: TemplateFamily
    pages: list[InfographicPage] = Field(min_length=1, max_length=20)
    illustration_prompt: str = Field(min_length=1, max_length=8_000)
    branding: BrandingSpec = Field(default_factory=BrandingSpec)


MASTER_VISUAL_LANGUAGE = """
QMRMed master visual language: premium editorial medical infographic.
Use the supplied reference designs as visual-language references only, never copy
specific content. Preserve their shared characteristics: clean modular grid,
rounded cards, soft clinical pastel palette, strong title hierarchy, generous
whitespace, compact information cards, topic-specific medical illustrations,
clear arrows and pathways, subtle gradients, restrained shadows, balanced density,
precise alignment, modern Arabic typography with correct RTL, and a polished
clinical-publication feel. Use red only for danger/warnings, green for favorable
or treatment states, blue/teal for information and mechanism, purple as a secondary
accent, and amber for caution. Never add decorative medical objects unrelated to
the topic. Never place a logo, watermark, signature, or readable text in the
illustration itself.
""".strip()


TEMPLATE_HINTS: dict[TemplateFamily, str] = {
    TemplateFamily.CLINICAL: (
        "Use a strong title, central clinical illustration, and balanced information cards."
    ),
    TemplateFamily.MECHANISM: (
        "Use a causal pathway with arrows and mechanism nodes."
    ),
    TemplateFamily.COMPARISON: (
        "Use a symmetrical comparison matrix with shared attributes and a key discriminator."
    ),
    TemplateFamily.DRUG: (
        "Use medication cards, mechanism/uses/cautions sections, and a dominant drug asset."
    ),
    TemplateFamily.DIAGNOSIS: (
        "Use a decision-oriented diagnostic flow with tests, findings, and interpretation."
    ),
    TemplateFamily.TREATMENT: (
        "Use a stepwise treatment pathway with priority, monitoring, and escalation blocks."
    ),
    TemplateFamily.SYMPTOMS: (
        "Use grouped symptom clusters with a clear hierarchy and warning strip when needed."
    ),
    TemplateFamily.ANATOMY: (
        "Use a central anatomical illustration with concise callout cards."
    ),
    TemplateFamily.EDUCATIONAL: (
        "Use a flexible teaching-card layout with definition and high-yield takeaways."
    ),
}


def choose_template(topic: str, visual_plan: VisualPlan) -> TemplateFamily:
    """Map the existing medical architecture to the QMRMed visual family."""
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


def build_design_spec(
    *,
    topic: str,
    content: SynthesizedContent,
    visual_plan: VisualPlan,
    language: str = "ar",
    max_blocks_per_page: int = 12,
) -> InfographicDesignSpec:
    """Build pages from evidence-locked content without shrinking typography."""
    if max_blocks_per_page < 4:
        raise ValueError("max_blocks_per_page_too_small")

    template = choose_template(topic, visual_plan)
    blocks: list[TextBlock] = [
        TextBlock(text=_compact(content.title, 120), role="title", importance=5)
    ]
    if content.subtitle:
        blocks.append(
            TextBlock(text=_compact(content.subtitle, 180), role="subtitle", importance=4)
        )
    for point in content.key_points:
        blocks.append(TextBlock(text=_compact(point, 240), role="point", importance=3))
    for claim in content.claims:
        importance = 4 if claim.critical else 3
        blocks.append(
            TextBlock(
                text=_compact(claim.text, 360),
                role="claim",
                importance=importance,
            )
        )
    for caution in content.cautions:
        blocks.append(TextBlock(text=_compact(caution, 240), role="caution", importance=5))

    pages: list[InfographicPage] = []
    payload = blocks[1:] if len(blocks) > 1 else blocks
    page_count = max(1, (len(payload) + max_blocks_per_page - 1) // max_blocks_per_page)
    for page_index in range(page_count):
        chunk = payload[
            page_index * max_blocks_per_page : (page_index + 1) * max_blocks_per_page
        ]
        title = content.title if page_index == 0 else f"{content.title} — {page_index + 1}"
        sections = list(dict.fromkeys(visual_plan.sections[:8])) or ["key points"]
        page_title = TextBlock(text=_compact(title, 160), role="title", importance=5)
        page_blocks = [page_title, *chunk]
        pages.append(
            InfographicPage(
                page_number=page_index + 1,
                title=_compact(title, 160),
                sections=sections,
                blocks=page_blocks,
            )
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
        template=template,
        pages=pages,
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
