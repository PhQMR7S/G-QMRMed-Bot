"""QMRMed single-image editorial design contract."""
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
    """Exact text permitted in the final image."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2_000)
    role: str = Field(min_length=1, max_length=32)
    importance: int = Field(default=1, ge=1, le=5)


class InfographicPage(BaseModel):
    """The single final image page."""

    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(default=1, ge=1, le=1)
    title: str = Field(min_length=1, max_length=160)
    sections: list[str] = Field(min_length=1, max_length=8)
    blocks: list[TextBlock] = Field(min_length=1, max_length=12)


class BrandingSpec(BaseModel):
    """Deterministic brand overlay."""

    model_config = ConfigDict(extra="forbid")
    telegram_handle: str = "QMR7S"
    position: str = "bottom_safe_zone"
    style: str = "frosted_glass"
    opacity: float = Field(default=0.82, ge=0.1, le=1.0)


class InfographicDesignSpec(BaseModel):
    """Complete one-image rendering contract."""

    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=20_000)
    language: str = Field(default="ar", min_length=2, max_length=8)
    aspect_ratio: str = "4:5"
    template: TemplateFamily
    pages: list[InfographicPage] = Field(min_length=1, max_length=1)
    illustration_prompt: str = Field(min_length=1, max_length=8_000)
    branding: BrandingSpec = Field(default_factory=BrandingSpec)


MASTER_VISUAL_LANGUAGE = """
QMRMed editorial medical infographic. Match the supplied professional reference
family: publication-grade hierarchy, clean white paper, restrained pastel section
panels, strong title typography, dominant clinically relevant illustration,
precise alignment, generous whitespace, rounded panels, small editorial labels,
and a subtle QMR7S signature. The final composition is 1080x1350 (4:5).
Use deep navy #0B1F3A, turquoise #14B8A6, white #FFFFFF and restrained gold #D4AF37,
with soft rose, mint, cyan and lavender secondary panels. Never use random colors.
Arabic text must be rendered with correct RTL shaping; English must remain LTR;
mixed input may remain mixed. Never transliterate Arabic into broken Latin glyphs.
Never put provider errors, fallback status, tracebacks, source URLs, citations,
file paths, internal metadata, or system messages into visible artwork.
The illustration is artwork only: no readable text, labels, numbers, logos,
watermarks or UI inside the generated illustration.
""".strip()


TEMPLATE_HINTS: dict[TemplateFamily, str] = {
    TemplateFamily.CLINICAL: "Title + definition/clinical overview + dominant illustration + high-yield clinical panels.",
    TemplateFamily.MECHANISM: "Title + causal pathway + dominant mechanism illustration + ordered mechanism/result panels.",
    TemplateFamily.COMPARISON: "Title + comparison matrix with strong column hierarchy and a concise takeaway.",
    TemplateFamily.DRUG: "Title + drug illustration + indication/mechanism/safety/monitoring panels.",
    TemplateFamily.DIAGNOSIS: "Title + diagnostic visual + signs/tests/interpretation/red flags panels.",
    TemplateFamily.TREATMENT: "Title + treatment pathway + first-line/monitoring/escalation panels.",
    TemplateFamily.SYMPTOMS: "Title + symptom illustration + grouped symptoms, evaluation and red flags.",
    TemplateFamily.ANATOMY: "Title + anatomical illustration + labeled relationship panels outside the artwork.",
    TemplateFamily.EDUCATIONAL: "Title + teaching illustration + definition, key concepts and takeaways.",
}


def detect_language_mode(text: str) -> str:
    """Detect Arabic, English, or genuinely mixed user input."""
    has_ar = any("\u0600" <= char <= "\u06ff" for char in text)
    has_lat = any("a" <= char.lower() <= "z" for char in text)
    if has_ar and has_lat:
        return "mixed"
    if has_ar:
        return "ar"
    return "en"


def choose_template(topic: str, visual_plan: VisualPlan) -> TemplateFamily:
    value = visual_plan.architecture.value.lower()
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
    if "revision" in value or "disease" in value:
        return TemplateFamily.EDUCATIONAL
    lowered = topic.lower()
    if any(word in lowered for word in ("symptom", "signs", "أعراض", "علامات")):
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
        "stack trace",
    )
    return any(marker in value for marker in markers)


def _select_single_image_blocks(content: SynthesizedContent) -> list[TextBlock]:
    """Select concise evidence-locked facts; subtitle is header text, not a card."""
    blocks: list[TextBlock] = []
    for point in content.key_points:
        if not _is_internal_artifact(point):
            blocks.append(TextBlock(text=_compact(point, 260), role="point", importance=3))
        if len(blocks) >= 3:
            break

    claims = [claim for claim in content.claims if not _is_internal_artifact(claim.text)]
    claims.sort(key=lambda claim: (claim.critical, claim.confidence), reverse=True)
    for claim in claims:
        blocks.append(
            TextBlock(
                text=_compact(claim.text, 320),
                role="danger" if claim.critical else "claim",
                importance=5 if claim.critical else 4,
            )
        )
        if len(blocks) >= 5:
            break

    for caution in content.cautions:
        if not _is_internal_artifact(caution):
            blocks.append(TextBlock(text=_compact(caution, 260), role="caution", importance=5))
            break
    return blocks[:6]


def build_design_spec(
    *,
    topic: str,
    content: SynthesizedContent,
    visual_plan: VisualPlan,
    language: str | None = None,
    max_blocks_per_page: int = 9,
) -> InfographicDesignSpec:
    """Build one image while preserving the input language contract."""
    if max_blocks_per_page < 4 or max_blocks_per_page > 9:
        raise ValueError("single_image_capacity_must_be_between_4_and_9")
    mode = language or detect_language_mode(topic)
    if mode not in {"ar", "en", "mixed"}:
        raise ValueError("unsupported_infographic_language")

    template = choose_template(topic, visual_plan)
    selected = _select_single_image_blocks(content)[:max_blocks_per_page]
    if not selected:
        raise ValueError("single_image_content_required")

    title = _compact(content.title, 160)
    if _is_internal_artifact(title):
        title = _compact(topic, 160)
    sections = [section for section in dict.fromkeys(visual_plan.sections[:8]) if not _is_internal_artifact(section)] or ["key points"]
    page = InfographicPage(
        page_number=1,
        title=title,
        sections=sections,
        blocks=[TextBlock(text=title, role="title", importance=5), *selected],
    )

    prompt = (
        MASTER_VISUAL_LANGUAGE
        + "\n\n"
        + TEMPLATE_HINTS[template]
        + "\nLanguage mode: "
        + mode
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
        language=mode,
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
    "detect_language_mode",
]
