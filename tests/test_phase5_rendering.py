from gqmrmed.contracts.research import (
    ArchitectureType,
    MedicalClaim,
    SynthesizedContent,
    VisualPlan,
)
from gqmrmed.rendering.layout import build_layout, HEIGHT, WIDTH
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


def test_layout_is_4_5_and_has_expected_canvas() -> None:
    layout = build_layout(_content(), _plan())
    assert layout.canvas.width == WIDTH == 1080
    assert layout.canvas.height == HEIGHT == 1350
    assert HEIGHT / WIDTH == 5 / 4


def test_layout_keeps_all_regions_non_overlapping_at_max_key_points() -> None:
    content = _content().model_copy(
        update={"key_points": [f"Point {index}" for index in range(12)]}
    )
    layout = build_layout(content, _plan())
    assert len(layout.content_boxes) == 12
    assert layout.illustration.y + layout.illustration.height <= layout.content_boxes[0].y
    for previous, current in zip(layout.content_boxes, layout.content_boxes[1:], strict=False):
        assert previous.y + previous.height <= current.y
    assert layout.content_boxes[-1].y + layout.content_boxes[-1].height <= layout.footer.y


def test_svg_escapes_exact_text_and_keeps_watermark() -> None:
    content = _content().model_copy(update={"title": "DKA & <test>"})
    svg = render_svg(content=content, visual_plan=_plan())
    assert "DKA &amp; &lt;test&gt;" in svg
    assert "GQMRMed" in svg
    assert 'width="1080" height="1350"' in svg


def test_svg_can_embed_illustration_asset_without_changing_text_layer() -> None:
    svg = render_svg(
        content=_content(),
        visual_plan=_plan(),
        illustration_href="illustration.png",
    )
    assert 'href="illustration.png"' in svg
    assert "Metabolic emergency" in svg
