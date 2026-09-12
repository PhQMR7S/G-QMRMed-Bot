"""Safe, deterministic layout planning for 9:16 medical infographics."""

from dataclasses import dataclass

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan

WIDTH = 1080
HEIGHT = 1920


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
    del content
    del visual_plan
    margin = 64
    title_h = 150
    subtitle_h = 72
    footer_h = 64
    gap = 24
    top = margin

    title = LayoutBox(margin, top, WIDTH - 2 * margin, title_h)
    top += title_h + gap
    subtitle = LayoutBox(margin, top, WIDTH - 2 * margin, subtitle_h)
    top += subtitle_h + gap

    footer = LayoutBox(margin, HEIGHT - margin - footer_h, WIDTH - 2 * margin, footer_h)
    illustration_h = min(560, max(360, int((footer.y - top) * 0.38)))
    illustration = LayoutBox(margin, top, WIDTH - 2 * margin, illustration_h)
    top += illustration_h + gap

    available = footer.y - top - gap
    box_count = 4
    box_h = max(120, (available - gap * (box_count - 1)) // box_count)
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
