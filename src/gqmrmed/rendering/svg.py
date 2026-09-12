"""SVG renderer for exact infographic text and layout."""

from html import escape
from pathlib import Path

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan
from gqmrmed.rendering.layout import build_layout, HEIGHT, WIDTH


class SVGRenderError(RuntimeError):
    """Raised when an infographic cannot be rendered safely."""


def render_svg(
    *,
    content: SynthesizedContent,
    visual_plan: VisualPlan,
    illustration_href: str | None = None,
) -> str:
    """Render exact text as SVG; illustration is an optional pre-generated asset."""
    layout = build_layout(content, visual_plan)
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
            f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
        ),
        '<rect width="100%" height="100%" fill="#f7f7f5"/>',
        _text_box(layout.title, content.title, 58, bold=True),
    ]
    if content.subtitle:
        parts.append(_text_box(layout.subtitle, content.subtitle, 30, bold=False))
    if illustration_href:
        parts.append(
            f'<image href="{escape(illustration_href, quote=True)}" '
            f'x="{layout.illustration.x}" y="{layout.illustration.y}" '
            f'width="{layout.illustration.width}" '
            f'height="{layout.illustration.height}" '
            'preserveAspectRatio="xMidYMid meet"/>'
        )
    else:
        parts.append(
            f'<rect x="{layout.illustration.x}" y="{layout.illustration.y}" '
            f'width="{layout.illustration.width}" '
            f'height="{layout.illustration.height}" '
            'rx="28" fill="#eeeeeb"/>'
        )
    for box, point in zip(layout.content_boxes, content.key_points, strict=False):
        parts.append(_text_box(box, point, 27, bold=False))
    parts.append(
        _text_box(layout.footer, visual_plan.watermark, 20, bold=False, anchor="end")
    )
    parts.append("</svg>")
    return "".join(parts)


def write_svg(
    *,
    path: Path,
    content: SynthesizedContent,
    visual_plan: VisualPlan,
    illustration_href: str | None = None,
) -> Path:
    """Write a UTF-8 SVG artifact and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_svg(
            content=content,
            visual_plan=visual_plan,
            illustration_href=illustration_href,
        ),
        encoding="utf-8",
    )
    return path


def _text_box(
    box,
    text: str,
    size: int,
    *,
    bold: bool,
    anchor: str = "start",
) -> str:
    weight = "700" if bold else "400"
    x = box.x + box.width if anchor == "end" else box.x
    y = box.y + size
    safe = escape(text)
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" '
        f'font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}" '
        f'fill="#18212b">{safe}</text>'
    )
