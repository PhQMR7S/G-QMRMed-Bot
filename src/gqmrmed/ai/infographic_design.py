"""Deterministic QMRMed single-image infographic design system."""

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
    """Branding is composited after AI generation."""

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
QMRMed master visual language: premium medical editorial infographic.
Use the agreed QMRMed identity: deep navy #0B1F3A, turquoise #14B8A6, white #FFFFFF,
and restrained gold #D4AF37. Build a polished 4:5 composition with one dominant
rounded white card, a compact badge, strong title hierarchy, a dedicated medical
illustration panel, concise information cards, generous spacing, subtle depth,
precise alignment, and a restrained frosted-glass QMR7S watermark in the safe zone.
Use modern Arabic typography with correct RTL. Turquoise is the primary information
accent; gold is a premium secondary accent; red is reserved for danger/warnings.
Do not use unrelated decorative objects. The illustration is artwork only: never put
readable text, labels, numbers, logos, signatures, watermarks, UI, or disclaimers
inside the generated artwork. Keep the final composition publication-grade and
readable on a phone. Never expose provider errors, fallback status, tracebacks, or
internal system messages as medical content.
""".strip()


TEMPLATE_HINTS: dict[TemplateFamily, str] = {
    TemplateFamily.CLINICAL: "Strong title, dominant clinical illustration, then balanced high-yield cards.",
    TemplateFamily.MECHANISM: "Use a causal visual pathway with clear directional flow and concise mechanism cards.",
    TemplateFamily.COMPARISON: "Use a symmetrical comparison structure with shared attributes and discriminators.",
    TemplateFamily.DRUG: "Use a dominant medication illustration with indication, mechanism, and caution cards.",
    TemplateFamily.DIAGNOSIS: "Use a diagnostic visual flow with tests, findings, interpretation, and red flags.",
    TemplateFamily.TREATMENT: "Use a stepwise treatment pathway with priority, monitoring, and escalation cards.",
    TemplateFamily.SYMPTOMS: "Use grouped symptom clusters with clear hierarchy and warning treatment only when supported.",
    TemplateFamily.ANATOMY: "Use a central anatomical illustration with concise relationship callouts.",
    TemplateFamily.EDUCATIONAL: "Use a flexible teaching composition with definition and high-yield takeaways.",
}


def choose_template(topic: str, visual_plan: VisualPlan) -> TemplateFamily:
    """Map the medical architecture to the QMRMed visual family."""
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


def _is_internal_artifact(text: str) -> bool:
    value = " ".join(text.lower().split())
    markers = (
        "automatic synthesis provider was unavailable",
        "synthesis provider was unavailable",
        "provider was unavailable",
        "provider unavailable",
        "fallback provider",
        "internal error",
        "traceback",
    )
    return any(marker in value for marker in markers)


def _select_single_image_blocks(content: SynthesizedContent) -> list[TextBlock]:
    """Select balanced evidence-locked content for one readable image."""
    blocks: list[TextBlock] = []
    if content.subtitle and not _is_internal_artifact(content.subtitle):
        blocks.append(TextBlock(text=_compact(content.subtitle, 180), role="subtitle", importance=4))

    points = [point for point in content.key_points if not _is_internal_artifact(point)]
    for point in points[:3]:
        blocks.append(TextBlock(text=_compact(point, 220), role="point", importance=3))

    claims = [claim for claim in content.claims if not _is_internal_artifact(claim.text)]
    claims.sort(key=lambda claim: (claim.critical, claim.confidence), reverse=True)
    for claim in claims[:2]:
        blocks.append(
            TextBlock(
                text=_compact(claim.text, 300),
                role="danger" if claim.critical else "claim",
                importance=5 if claim.critical else 3,
            )
        )

    cautions = [caution for caution in content.cautions if not _is_internal_artifact(caution)]
    if cautions:
        blocks.append(TextBlock(text=_compact(cautions[0], 220), role="caution", importance=5))

    return blocks[:6]


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
    sections = [
        section for section in dict.fromkeys(visual_plan.sections[:8])
        if not _is_internal_artifact(section)
    ] or ["key points"]
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
        + "\nIMPORTANT: artwork only; no readable text, labels, numbers, logos, watermark, UI, or disclaimers."
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
