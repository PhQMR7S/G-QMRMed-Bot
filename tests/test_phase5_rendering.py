from gqmrmed.contracts.research import (
    ArchitectureType,
    MedicalClaim,
    SynthesizedContent,
    VisualPlan,
)
from gqmrmed.rendering.layout import HEIGHT, WIDTH, build_layout
from gqmrmed.rendering.svg import render_svg


def _content() -> SynthesizedContent:
    return SynthesizedContent(
        title="Diabetic ketoacidosis",
        subtitle="Medical infographic",
        key_points=[
            "Metabolic emergency",
            "Hyperglycemia",
            "Ketosis",
            "Volume depletion",
        ],
        claims=[
            MedicalClaim(
                claim_id="c1",
                text="DKA is a metabolic emergency.",
                evidence_ids=["pubmed:1"],
                confidence=0.9,
            )
        ],
    )


def _plan() -> VisualPlan:
    return VisualPlan(
        architecture=ArchitectureType.CLINICAL_EMERGENCY_ALGORITHM,
        sections=["danger signs", "initial actions"],
        illustration_prompt="Medical vector illustration only.",
    )


def test_layout_is_2_3_and_has_expected_canvas() -> None:
    layout = build_layout(_content(), _plan())
    assert layout.canvas.width == WIDTH == 1024
    assert layout.canvas.height == HEIGHT == 1536
    assert HEIGHT / WIDTH == 3 / 2


def test_layout_keeps_all_regions_non_overlapping_at_max_key_points() -> None:
    content = _content().model_copy(
        update={"key_points": [f"Point {index}" for index in range(12)]}
    )
    layout = build_layout(content, _plan())
    assert len(layout.content_boxes) == 12
    assert layout.illustration.y + layout.illustration.height <= min(
        box.y for box in layout.content_boxes
    )
    for index, previous in enumerate(layout.content_boxes):
        for current in layout.content_boxes[index + 1 :]:
            separated = (
                previous.x + previous.width <= current.x
                or current.x + current.width <= previous.x
                or previous.y + previous.height <= current.y
                or current.y + current.height <= previous.y
            )
            assert separated
    assert max(box.y + box.height for box in layout.content_boxes) <= layout.footer.y


def test_svg_escapes_exact_text_and_keeps_watermark() -> None:
    content = _content().model_copy(update={"title": "DKA & <test>"})
    svg = render_svg(content=content, visual_plan=_plan())
    assert "DKA &amp; &lt;test&gt;" in svg
    assert "GQMRMed" in svg
    assert 'width="1024" height="1536"' in svg


def test_svg_can_embed_illustration_asset_without_changing_text_layer() -> None:
    svg = render_svg(
        content=_content(),
        visual_plan=_plan(),
        illustration_href="illustration.png",
    )
    assert 'href="illustration.png"' in svg
    assert "Metabolic emergency" in svg
