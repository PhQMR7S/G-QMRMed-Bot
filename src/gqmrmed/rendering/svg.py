"""SVG renderer for exact infographic text and layout."""

from html import escape
from pathlib import Path

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan
from gqmrmed.rendering.layout import build_layout, HEIGHT, LayoutBox, WIDTH


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
        _wrapped_text(layout.title, content.title, 58, bold=True, max_lines=2),
    ]
    if content.subtitle:
        subtitle_box = layout.subtitle
        if subtitle_box is None:
            raise SVGRenderError("subtitle content requires a subtitle layout box")
        parts.append(_wrapped_text(subtitle_box, content.subtitle, 30, max_lines=2))
    if illustration_href:
        parts.append(
            f'<image href="{escape(illustration_href, quote=True)}" '
            f'x="{layout.illustration.x}" y="{layout.illustration.y}" '
            f'width="{layout.illustration.width}" height="{layout.illustration.height}" '
            'preserveAspectRatio="xMidYMid meet"/>'
        )
    else:
        parts.append(
            f'<rect x="{layout.illustration.x}" y="{layout.illustration.y}" '
            f'width="{layout.illustration.width}" height="{layout.illustration.height}" '
            'rx="28" fill="#eeeeeb"/>'
        )
    for box, point in zip(layout.content_boxes, content.key_points, strict=False):
        parts.append(_wrapped_text(box, point, 27, max_lines=4))
    parts.append(_wrapped_text(layout.footer, content.disclaimer, 16, max_lines=2))
    parts.append(
        _text_box(
            LayoutBox(layout.footer.x, layout.footer.y + 36, layout.footer.width, 24),
            visual_plan.watermark,
            16,
            anchor="end",
        )
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


def _wrapped_text(
    box: LayoutBox,
    text: str,
    size: int,
    *,
    bold: bool = False,
    max_lines: int,
    anchor: str = "start",
) -> str:
    lines = _wrap(text, max_chars=max(12, box.width // max(1, size // 2)))[:max_lines]
    if not lines:
        return ""
    weight = "700" if bold else "400"
    x = box.x + box.width if anchor == "end" else box.x
    dy = max(size + 8, int(size * 1.25))
    tspans = []
    for index, line in enumerate(lines):
        y = box.y + size + index * dy
        tspans.append(f'<tspan x="{x}" y="{y}">{escape(line)}</tspan>')
    return (
        f'<text font-family="Arial, sans-serif" font-size="{size}px" '
        f'font-weight="{weight}" text-anchor="{anchor}" fill="#18212b">'
        + "".join(tspans)
        + "</text>"
    )


def _text_box(
    box: LayoutBox,
    text: str,
    size: int,
    *,
    bold: bool = False,
    anchor: str = "start",
) -> str:
    return _wrapped_text(box, text, size, bold=bold, max_lines=1, anchor=anchor)


def _wrap(text: str, *, max_chars: int) -> list[str]:
    """Wrap on whitespace while preserving medical tokens and short inputs."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


__all__ = ["SVGRenderError", "render_svg", "write_svg"]
