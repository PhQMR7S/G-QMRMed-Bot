"""Select a visual architecture from the medical topic without generating artwork."""

from gqmrmed.contracts.research import ArchitectureType, SynthesizedContent, VisualPlan

_RULES: tuple[tuple[ArchitectureType, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ArchitectureType.CLINICAL_EMERGENCY_ALGORITHM,
        ("emergency", "shock", "arrest", "dka", "ketoacidosis", "sepsis", "anaphylaxis"),
        ("danger signs", "initial actions", "decision points", "escalation"),
    ),
    (
        ArchitectureType.LABORATORY_INTERPRETATION,
        (
            "lab",
            "laboratory",
            "blood test",
            "cbc",
            "electrolyte",
            "sodium",
            "potassium",
            "creatinine",
        ),
        ("test", "normal", "abnormal", "interpretation"),
    ),
    (
        ArchitectureType.ECG_ANALYSIS,
        ("ecg", "ekg", "electrocardiogram", "rhythm", "st elevation", "qt interval"),
        ("rhythm", "intervals", "waveform", "interpretation"),
    ),
    (
        ArchitectureType.DRUG_PROFILE,
        (
            "drug",
            "medication",
            "dose",
            "antibiotic",
            "insulin",
            "heparin",
            "aspirin",
            "metformin",
        ),
        ("class", "mechanism", "uses", "cautions"),
    ),
    (
        ArchitectureType.ANATOMY_EXPLORER,
        ("anatomy", "artery", "vein", "nerve", "organ", "heart", "brain", "kidney", "liver"),
        ("structure", "location", "blood supply", "relations"),
    ),
    (
        ArchitectureType.PATHOPHYSIOLOGY_FLOW,
        ("pathophysiology", "mechanism", "physiology", "pathway", "cascade", "inflammation"),
        ("trigger", "mechanism", "effect", "clinical result"),
    ),
    (
        ArchitectureType.COMPARISON_MATRIX,
        ("vs", "versus", "difference", "compare", "comparison", "distinguish"),
        ("similarities", "differences", "key discriminator"),
    ),
    (
        ArchitectureType.STEP_BY_STEP_PROCEDURE,
        ("procedure", "technique", "steps", "protocol", "algorithm"),
        ("preparation", "steps", "checks", "aftercare"),
    ),
)

_REFERENCE_LANGUAGE = """
QMRMed reference-driven visual language: premium editorial medical infographic.
Match the supplied reference images as closely as possible at the level of visual
system, not their protected or topic-specific content: clean 4:5 composition,
strong title area, rounded modular cards, soft clinical pastel accents, subtle
blue/teal/lavender gradients, precise grid alignment, generous whitespace,
clear information hierarchy, restrained shadows, topic-specific clinical
illustration, concise labels, comparison panels when appropriate, and clean
educational diagrams. The layout must adapt to the topic instead of forcing one
rigid template. Use red only for clinically meaningful warnings, green for
favorable/treatment states, blue/teal for information and mechanisms, purple for
secondary grouping, and amber for caution. Never add decorative medical objects
that are unrelated to the requested topic.

Artwork is illustration-only. Never render readable text, labels, numbers,
doses, drug names, logos, watermarks, signatures, citations, or invented facts
inside the artwork. Leave intentional clean regions for deterministic text
composition. The final image must contain only evidence-locked content supplied
by the renderer.
""".strip()


def select_visual_architecture(
    *,
    topic: str,
    content: SynthesizedContent,
) -> VisualPlan:
    """Choose the strongest architecture using transparent medical heuristics."""
    corpus = " ".join(
        [
            topic.lower(),
            content.title.lower(),
            content.subtitle or "",
            " ".join(content.key_points).lower(),
        ]
    )
    architecture = ArchitectureType.DISEASE_MASTER_CARD
    sections = ["definition", "mechanism", "key clinical points", "cautions"]
    emphasis: list[str] = ["medical terminology", "high-yield facts"]

    best_score = 0
    for candidate, keywords, candidate_sections in _RULES:
        score = sum(1 for keyword in keywords if keyword in corpus)
        if score > best_score:
            best_score = score
            architecture = candidate
            sections = list(candidate_sections)

    if len(content.claims) >= 8 and architecture is ArchitectureType.DISEASE_MASTER_CARD:
        architecture = ArchitectureType.CONCEPT_MAP
        sections = ["central concept", "mechanisms", "clinical manifestations", "key takeaways"]

    prompt = (
        _REFERENCE_LANGUAGE
        + "\n\nMedical topic: "
        + content.title
        + f"\nArchitecture: {architecture.value}."
        + "\nCreate medically appropriate vector-style anatomy or symbolic diagrams, "
        "anonymous figures only, with no readable text or labels. Preserve clear "
        "negative space for exact text overlays and do not place the main artwork "
        "over the footer branding safe zone."
    )
    return VisualPlan(
        architecture=architecture,
        aspect_ratio="4:5",
        sections=sections,
        emphasis=emphasis,
        illustration_prompt=prompt,
    )
