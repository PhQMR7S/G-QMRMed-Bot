"""Safe, deterministic layout planning for 4:5 medical infographics."""

from dataclasses import dataclass

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan

WIDTH = 1080
HEIGHT = 1350


@dataclass(frozen=True, slots=True)
class LayoutBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class InfographicLayout:
    canvas: LayoutBox
    title: LayoutBox
    subtitle: LayoutBox | None
    illustration: LayoutBox
    content_boxes: tuple[LayoutBox, ...]
    footer: LayoutBox


def build_layout(content: SynthesizedContent, visual_plan: VisualPlan) -> InfographicLayout:
    """Allocate non-overlapping regions before any text or artwork is rendered."""
    del visual_plan
    margin = 64
    title_h = 150
    subtitle_h = 72 if content.subtitle else 0
    footer_h = 64
    gap = 24
    top = margin

    title = LayoutBox(margin, top, WIDTH - 2 * margin, title_h)
    top += title_h + gap

    subtitle: LayoutBox | None = None
    if content.subtitle:
        subtitle = LayoutBox(margin, top, WIDTH - 2 * margin, subtitle_h)
        top += subtitle_h + gap

    footer = LayoutBox(margin, HEIGHT - margin - footer_h, WIDTH - 2 * margin, footer_h)
    box_count = len(content.key_points)
    if box_count < 1:
        raise ValueError("layout_requires_key_points")

    total_content_gap = gap * (box_count - 1)
    minimum_box_h = 48
    minimum_illustration_h = 280
    illustration_h = min(
        560,
        max(
            minimum_illustration_h,
            int((footer.y - top) * 0.38),
        ),
    )

    required_content = minimum_box_h * box_count + total_content_gap
    if top + illustration_h + gap + required_content > footer.y:
        illustration_h = max(
            minimum_illustration_h,
            footer.y - top - gap - required_content,
        )
    if top + illustration_h + gap + required_content > footer.y:
        minimum_box_h = max(
            1,
            (footer.y - top - illustration_h - gap - total_content_gap) // box_count,
        )

    illustration = LayoutBox(margin, top, WIDTH - 2 * margin, illustration_h)
    top += illustration_h + gap

    available = max(0, footer.y - top - gap)
    box_h = max(
        1,
        (available - total_content_gap) // box_count,
    )
    boxes = tuple(
        LayoutBox(margin, top + i * (box_h + gap), WIDTH - 2 * margin, box_h)
        for i in range(box_count)
    )
    return InfographicLayout(
        canvas=LayoutBox(0, 0, WIDTH, HEIGHT),
        title=title,
        subtitle=subtitle,
        illustration=illustration,
        content_boxes=boxes,
        footer=footer,
    )


__all__ = ["HEIGHT", "WIDTH", "InfographicLayout", "LayoutBox", "build_layout"]
