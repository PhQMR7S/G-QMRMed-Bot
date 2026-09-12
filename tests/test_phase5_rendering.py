from gqmrmed.contracts.research import ArchitectureType, MedicalClaim, SynthesizedContent, VisualPlan
from gqmrmed.rendering.layout import HEIGHT, WIDTH, build_layout
from gqmrmed.rendering.svg import render_svg


def _content() -> SynthesizedContent:
    return SynthesizedContent(
        title="Diabetic ketoacidosis",
        subtitle="Medical infographic",
        key_points=["Metabolic emergency", "Hyperglycemia", "Ketosis", "Volume depletion"],
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


def test_layout_is_9_16_and_has_expected_canvas() -> None:
    layout = build_layout(_content(), _plan())
    assert layout.canvas.width == WIDTH == 1080
    assert layout.canvas.height == HEIGHT == 1920
    assert HEIGHT / WIDTH == 16 / 9


def test_svg_escapes_exact_text_and_keeps_watermark() -> None:
    content = _content().model_copy(update={"title": "DKA & <test>"})
    svg = render_svg(content=content, visual_plan=_plan())
    assert "DKA &amp; &lt;test&gt;" in svg
    assert "GQMRMed" in svg
    assert 'width="1080" height="1920"' in svg


def test_svg_can_embed_illustration_asset_without_changing_text_layer() -> None:
    svg = render_svg(content=_content(), visual_plan=_plan(), illustration_href="illustration.png")
    assert 'href="illustration.png"' in svg
    assert "Metabolic emergency" in svg
