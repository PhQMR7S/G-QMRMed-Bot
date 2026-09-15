"""Safe, deterministic layout planning for 2:3 medical infographics."""

from dataclasses import dataclass

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan

WIDTH = 1024
HEIGHT = 1536


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
    """Allocate bounded, non-overlapping regions on the canonical 2:3 canvas."""
    if visual_plan.aspect_ratio != "2:3":
        raise ValueError("layout_requires_2_3_visual_plan")
    margin = 48
    gap = 20
    title = LayoutBox(margin, 34, WIDTH - 2 * margin, 132)
    top = title.y + title.height + gap
    subtitle = None
    if content.subtitle:
        subtitle = LayoutBox(margin, top, WIDTH - 2 * margin, 48)
        top += subtitle.height + gap
    footer = LayoutBox(margin, HEIGHT - margin - 58, WIDTH - 2 * margin, 58)
    illustration_h = min(330, max(260, int((footer.y - top) * 0.42)))
    illustration = LayoutBox(margin, top, WIDTH - 2 * margin, illustration_h)
    content_top = illustration.y + illustration.height + gap
    count = len(content.key_points)
    if count < 1:
        raise ValueError("layout_requires_key_points")
    cols = 2 if count > 1 else 1
    rows = (count + cols - 1) // cols
    available_h = footer.y - content_top
    content_gap = 16
    box_h = (available_h - content_gap * (rows - 1)) // rows
    if box_h < 80:
        raise ValueError("layout_content_area_too_small")
    box_w = (WIDTH - 2 * margin - content_gap * (cols - 1)) // cols
    boxes = tuple(
        LayoutBox(
            margin + col * (box_w + content_gap),
            content_top + row * (box_h + content_gap),
            box_w,
            box_h,
        )
        for row in range(rows)
        for col in range(cols)
        if row * cols + col < count
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
