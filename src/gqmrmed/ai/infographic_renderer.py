"""Deterministic QMRMed compositor for the agreed premium visual system."""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from typing import cast

import cairosvg

from gqmrmed.ai.infographic_design import (
    InfographicDesignSpec,
    InfographicPage,
    TemplateFamily,
    TextBlock,
)
from gqmrmed.generation.providers import GeneratedIllustration

# The SVG compositor intentionally contains long markup literals.
# Ruff's E501 is disabled for this renderer; functional checks remain enforced.
# ruff: noqa: E501


@dataclass(frozen=True, slots=True)
class RenderConfig:
    """Canonical QMRMed canvas and brand palette."""

    width: int = 1080
    height: int = 1350
    navy: str = "#0B1F3A"
    teal: str = "#14B8A6"
    white: str = "#FFFFFF"
    gold: str = "#D4AF37"
    ink: str = "#0B1F3A"
    muted: str = "#64748B"
    panel: str = "#F5F8FC"
    line: str = "#DCE5EE"
    danger: str = "#C94B55"
    caution: str = "#D9902F"
    success: str = "#2F9B6B"


def render_infographic_page(
    spec: InfographicDesignSpec,
    page: InfographicPage,
    illustration: GeneratedIllustration,
    *,
    config: RenderConfig | None = None,
) -> bytes:
    """Render one polished 1080x1350 PNG with deterministic exact text."""
    cfg = config or RenderConfig()
    if cfg.width < 800 or cfg.height < 1000:
        raise ValueError("render_resolution_too_small")
    if cfg.width * 5 != cfg.height * 4:
        raise ValueError("render_canvas_must_be_4_5")
    if not illustration.image_bytes:
        raise ValueError("illustration_bytes_required")
    if page.page_number != 1 or len(spec.pages) != 1:
        raise ValueError("single_image_contract_violated")

    rtl = spec.language.lower().startswith(("ar", "fa", "ur"))
    direction = "rtl" if rtl else "ltr"
    anchor = "end" if rtl else "start"
    outer = 44
    card_x = outer
    card_y = 108
    card_w = cfg.width - outer * 2
    card_h = cfg.height - card_y - 44
    title = _compact(page.title, 80)
    source_body = page.blocks[1:]
    body = _usable_blocks(source_body)
    if not body:
        raise ValueError("infographic_body_required")

    svg: list[str] = [_root(cfg), _defs(cfg)]
    svg.append(_rect(0, 0, cfg.width, cfg.height, cfg.navy))
    svg.append(_background_decoration(cfg))
    svg.append(
        _rounded_rect(
            card_x,
            card_y,
            card_w,
            card_h,
            42,
            cfg.white,
            stroke="none",
        )
    )

    badge_x = cfg.width - outer - 228 if rtl else outer + 28
    svg.append(
        _pill(
            badge_x,
            card_y + 28,
            200,
            46,
            cfg.teal,
            "QMRMed  •  MEDICAL",
            cfg.white,
        )
    )
    title_lines = _wrap(title, 24 if rtl else 30)
    title_size = 52 if len(title_lines) == 1 else 44
    for index, line in enumerate(title_lines[:2]):
        svg.append(
            _text(
                line,
                cfg.width - outer - 30 if rtl else outer + 30,
                card_y + 125 + index * (title_size + 4),
                anchor=anchor,
                direction=direction,
                size=title_size,
                weight=800,
                fill=cfg.ink,
            )
        )

    subtitle = (
        "تثقيف طبي موثوق • مبني على الأدلة"
        if rtl
        else "Evidence-led medical education"
    )
    svg.append(
        _text(
            subtitle,
            cfg.width - outer - 30 if rtl else outer + 30,
            card_y + 182,
            anchor=anchor,
            direction=direction,
            size=19,
            weight=500,
            fill=cfg.muted,
        )
    )

    image_x = card_x + 28
    image_y = card_y + 214
    image_w = card_w - 56
    image_h = 348
    svg.append(
        _image_frame(
            image_x,
            image_y,
            image_w,
            image_h,
            illustration,
            cfg,
        )
    )
    svg.append(_image_badge(image_x + 20, image_y + 20, cfg))

    body_y = image_y + image_h + 24
    disclaimer = _disclaimer(source_body)
    footer_space = 54 if disclaimer else 26
    body_h = card_y + card_h - body_y - footer_space
    _render_content_grid(
        svg,
        body,
        x=card_x + 28,
        y=body_y,
        width=card_w - 56,
        height=body_h,
        rtl=rtl,
        cfg=cfg,
        template=spec.template,
    )

    if disclaimer:
        svg.append(
            _text(
                _compact(disclaimer, 96),
                cfg.width / 2,
                card_y + card_h - 30,
                anchor="middle",
                direction=direction,
                size=14,
                weight=500,
                fill=cfg.muted,
            )
        )
    svg.append(_watermark(cfg, card_x, card_y, card_w, card_h))
    svg.append("</svg>")
    rendered = cairosvg.svg2png(
        bytestring="".join(svg).encode("utf-8"),
        output_width=cfg.width,
        output_height=cfg.height,
    )
    return cast(bytes, rendered)


def _render_content_grid(
    svg: list[str],
    blocks: list[TextBlock],
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    rtl: bool,
    cfg: RenderConfig,
    template: TemplateFamily,
) -> None:
    count = min(len(blocks), 6)
    blocks = blocks[:count]
    if count <= 2:
        columns = 1
    elif count <= 4:
        columns = 2
    else:
        columns = 3
    gap = 16
    rows = (count + columns - 1) // columns
    card_w = (width - gap * (columns - 1)) / columns
    card_h = (height - gap * (rows - 1)) / rows
    for index, block in enumerate(blocks):
        row = index // columns
        col = index % columns
        card_x = x + col * (card_w + gap)
        card_y = y + row * (card_h + gap)
        accent = _accent(block.role, cfg)
        svg.append(
            _rounded_rect(
                card_x,
                card_y,
                card_w,
                card_h,
                22,
                cfg.panel,
                stroke=cfg.line,
            )
        )
        if rtl:
            svg.append(
                _accent_dot(card_x + card_w - 30, card_y + 28, accent)
            )
            text_x = card_x + card_w - 48
            text_anchor = "end"
        else:
            svg.append(_accent_dot(card_x + 30, card_y + 28, accent))
            text_x = card_x + 48
            text_anchor = "start"
        role = _role_label(block.role, template, rtl)
        svg.append(
            _text(
                role,
                text_x,
                card_y + 34,
                anchor=text_anchor,
                direction="rtl" if rtl else "ltr",
                size=16,
                weight=800,
                fill=accent,
            )
        )
        max_chars = 26 if columns == 3 else 39 if columns == 2 else 72
        font_size = 18 if columns == 3 else 20 if columns == 2 else 23
        max_lines = max(2, int((card_h - 62) / (font_size + 7)))
        lines = _fit_lines(block.text, max_chars, max_lines=max_lines)
        for line_index, line in enumerate(lines):
            svg.append(
                _text(
                    line,
                    text_x,
                    card_y + 68 + line_index * (font_size + 7),
                    anchor=text_anchor,
                    direction="rtl" if rtl else "ltr",
                    size=font_size,
                    weight=600,
                    fill=cfg.ink,
                )
            )


def _image_frame(
    x: float,
    y: float,
    width: float,
    height: float,
    illustration: GeneratedIllustration,
    cfg: RenderConfig,
) -> str:
    uri = _data_uri(illustration.image_bytes, illustration.mime_type)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" rx="28" fill="{cfg.navy}"/>'
        f'<image href="{uri}" x="{x + 3:.1f}" y="{y + 3:.1f}" '
        f'width="{width - 6:.1f}" height="{height - 6:.1f}" '
        'preserveAspectRatio="xMidYMid slice" opacity="0.98"/>'
    )


def _image_badge(x: float, y: float, cfg: RenderConfig) -> str:
    return _pill(
        x,
        y,
        142,
        38,
        cfg.white,
        "VISUAL",
        cfg.navy,
        opacity=0.88,
    )


def _watermark(
    cfg: RenderConfig,
    x: float,
    y: float,
    width: float,
    height: float,
) -> str:
    wx = x + width - 190
    wy = y + height - 54
    return (
        f'<g opacity="0.82"><rect x="{wx:.1f}" y="{wy:.1f}" '
        f'width="158" height="36" rx="18" fill="{cfg.white}" '
        f'stroke="{cfg.line}"/>'
        f'<circle cx="{wx + 21:.1f}" cy="{wy + 18:.1f}" r="9" '
        f'fill="{cfg.teal}"/>'
        f'<path d="M{wx + 16:.1f} {wy + 18:.1f} '
        f'L{wx + 20:.1f} {wy + 22:.1f} L{wx + 27:.1f} {wy + 14:.1f}" '
        f'fill="none" stroke="{cfg.white}" stroke-width="2.5" '
        f'stroke-linecap="round"/>'
        f'<text x="{wx + 38:.1f}" y="{wy + 23:.1f}" '
        f'font-family="DejaVu Sans, sans-serif" font-size="15" '
        f'font-weight="800" fill="{cfg.ink}">QMR7S</text></g>'
    )


def _background_decoration(cfg: RenderConfig) -> str:
    return (
        f'<circle cx="970" cy="90" r="150" fill="{cfg.teal}" '
        'opacity="0.08"/>'
        f'<circle cx="970" cy="90" r="92" fill="none" '
        f'stroke="{cfg.gold}" stroke-width="2" opacity="0.28"/>'
        f'<path d="M58 1120 C180 1040 210 1230 360 1160" '
        f'fill="none" stroke="{cfg.teal}" stroke-width="3" '
        'opacity="0.16"/>'
    )


def _defs(cfg: RenderConfig) -> str:
    return (
        '<defs>'
        f'<filter id="shadow" x="-20%" y="-20%" width="140%" '
        f'height="140%"><feDropShadow dx="0" dy="12" '
        f'stdDeviation="18" flood-opacity="0.16" '
        f'flood-color="{cfg.navy}"/></filter>'
        '</defs>'
    )


def _root(cfg: RenderConfig) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{cfg.width}" '
        f'height="{cfg.height}" viewBox="0 0 {cfg.width} {cfg.height}">'
    )


def _rect(x: float, y: float, width: float, height: float, fill: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" fill="{fill}"/>'
    )


def _rounded_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    fill: str,
    *,
    stroke: str,
) -> str:
    filter_attr = ' filter="url(#shadow)"' if fill == "#FFFFFF" else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" rx="{radius:.1f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2"{filter_attr}/>'
    )


def _pill(
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str,
    value: str,
    text_fill: str,
    *,
    opacity: float = 1.0,
) -> str:
    return (
        f'<g opacity="{opacity}"><rect x="{x:.1f}" y="{y:.1f}" '
        f'width="{width:.1f}" height="{height:.1f}" '
        f'rx="{height / 2:.1f}" fill="{fill}"/>'
        f'<text x="{x + width / 2:.1f}" '
        f'y="{y + height / 2 + 5:.1f}" text-anchor="middle" '
        'font-family="DejaVu Sans, Noto Sans Arabic, sans-serif" '
        f'font-size="15" font-weight="800" fill="{text_fill}">'
        f'{_escape(value)}</text></g>'
    )


def _accent_dot(x: float, y: float, fill: str) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{fill}"/>'


def _text(
    value: str,
    x: float,
    y: float,
    *,
    anchor: str,
    direction: str,
    size: int,
    weight: int,
    fill: str,
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'direction="{direction}" '
        'font-family="Noto Sans Arabic, DejaVu Sans, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
        f'{_escape(value)}</text>'
    )


def _data_uri(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _compact(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def _wrap(text: str, max_chars: int) -> list[str]:
    words = re.split(r"\s+", " ".join(text.split()))
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
    return lines or [text]


def _fit_lines(text: str, max_chars: int, *, max_lines: int) -> list[str]:
    lines = _wrap(text, max_chars)
    if len(lines) <= max_lines:
        return lines
    while len(lines) > max_lines and max_chars < 90:
        max_chars += 4
        lines = _wrap(text, max_chars)
    if len(lines) > max_lines:
        raise ValueError("medical_text_does_not_fit_single_image")
    return lines


def _usable_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    return [
        block
        for block in blocks
        if not _is_internal_artifact(block.text)
        and not _is_disclaimer(block.text)
    ][:6]


def _is_internal_artifact(text: str) -> bool:
    value = " ".join(text.lower().split())
    markers = (
        "automatic synthesis provider was unavailable",
        "synthesis provider was unavailable",
        "provider was unavailable",
        "provider unavailable",
        "image provider unavailable",
        "fallback provider",
        "internal error",
        "traceback",
    )
    return any(marker in value for marker in markers)


def _is_disclaimer(text: str) -> bool:
    value = text.lower()
    return "ليست تشخيص" in text or "ليست تشخيصاً" in text or "not a diagnosis" in value


def _first_non_internal(values: list[str]) -> str:
    for value in values:
        if value and not _is_internal_artifact(value):
            return value
    return ""


def _disclaimer(blocks: list[TextBlock]) -> str:
    for block in blocks:
        if _is_disclaimer(block.text):
            return block.text
    return ""


def _accent(role: str, cfg: RenderConfig) -> str:
    return {
        "caution": cfg.caution,
        "danger": cfg.danger,
        "claim": cfg.teal,
        "point": cfg.teal,
        "title": cfg.gold,
        "subtitle": cfg.teal,
    }.get(role, cfg.teal)


def _role_label(role: str, template: TemplateFamily, rtl: bool) -> str:
    del template
    if rtl:
        return {
            "claim": "معلومة موثقة",
            "point": "نقطة مهمة",
            "caution": "تنبيه",
            "danger": "تحذير",
            "subtitle": "ملخص",
            "title": "الموضوع",
        }.get(role, "معلومة")
    return {
        "claim": "Evidence",
        "point": "Key point",
        "caution": "Caution",
        "danger": "Warning",
        "subtitle": "Summary",
        "title": "Topic",
    }.get(role, "Evidence")


__all__ = ["RenderConfig", "render_infographic_page"]
