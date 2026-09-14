from gqmrmed.ai.infographic_design import build_design_spec
from gqmrmed.ai.infographic_qa import InfographicQAError, validate_design_spec
from gqmrmed.ai.infographic_renderer import render_infographic_page
from gqmrmed.ai.research_router import split_long_research_query
from gqmrmed.contracts.research import (
    ArchitectureType,
    MedicalClaim,
    SynthesizedContent,
    VisualPlan,
)
from gqmrmed.generation.providers import GeneratedIllustration


def _content() -> SynthesizedContent:
    return SynthesizedContent(
        title="الحماض الكيتوني السكري",
        subtitle="نظرة تعليمية مختصرة",
        key_points=[f"نقطة سريرية مهمة رقم {index}" for index in range(1, 7)],
        claims=[
            MedicalClaim(
                claim_id=f"claim_{index}",
                text=f"معلومة موثقة عن الحالة رقم {index}",
                evidence_ids=["pmid:1"],
                confidence=0.9,
            )
            for index in range(1, 7)
        ],
        cautions=["هذه مادة تعليمية وليست تشخيصاً فردياً."],
    )


def _visual_plan() -> VisualPlan:
    return VisualPlan(
        architecture=ArchitectureType.PATHOPHYSIOLOGY_FLOW,
        aspect_ratio="4:5",
        sections=["trigger", "mechanism", "effect", "clinical result"],
        emphasis=["high-yield facts"],
        illustration_prompt="Clean medical pathway artwork without text or labels.",
    )


def test_design_always_produces_one_coherent_image() -> None:
    spec = build_design_spec(
        topic="DKA",
        content=_content(),
        visual_plan=_visual_plan(),
        max_blocks_per_page=4,
    )
    assert len(spec.pages) == 1
    assert spec.aspect_ratio == "4:5"
    assert spec.pages[0].page_number == 1
    assert spec.pages[0].blocks[0].role == "title"


def test_research_splits_long_input_into_bounded_queries() -> None:
    query = " ".join(["DKA treatment and diagnosis."] * 80)
    queries = split_long_research_query(query)
    assert 1 < len(queries) <= 6
    assert all(len(item) <= 700 for item in queries)


def test_design_qa_rejects_visible_source_urls() -> None:
    spec = build_design_spec(topic="DKA", content=_content(), visual_plan=_visual_plan())
    spec.pages[0].blocks[1].text = "https://example.com"
    try:
        validate_design_spec(spec)
    except InfographicQAError as exc:
        assert str(exc) == "visible_source_url_forbidden"
    else:
        raise AssertionError("expected QA failure")


def test_renderer_returns_single_4_5_png_with_glass_signature_layout() -> None:
    import cairosvg

    spec = build_design_spec(topic="DKA", content=_content(), visual_plan=_visual_plan())
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        b'<rect width="100%" height="100%" fill="#fff"/></svg>'
    )
    illustration = GeneratedIllustration(
        image_bytes=cairosvg.svg2png(bytestring=svg),
        width=100,
        height=100,
        mime_type="image/png",
    )
    output = render_infographic_page(spec, spec.pages[0], illustration)
    assert output.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(output) > 1_000
