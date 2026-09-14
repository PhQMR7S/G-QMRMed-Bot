"""Deterministic QMRMed compositor.

The model-generated artwork is treated as a visual asset. All visible text,
cards, hierarchy, and the QMR7S signature are rendered here for exactness.
"""

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


@dataclass(frozen=True, slots=True)
class RenderConfig:
    width: int = 1080
    height: int = 1350
    background: str = "#F7FAFC"
    ink: str = "#172033"
    muted: str = "#5E6B7A"
    primary: str = "#3978A9"
    teal: str = "#4FA7A0"
    purple: str = "#8067A8"
    caution: str = "#D89234"
    danger: str = "#C75B61"
    success: str = "#4C9A72"


def render_infographic_page(
    spec: InfographicDesignSpec,
    page: InfographicPage,
    illustration: GeneratedIllustration,
    *,
    config: RenderConfig | None = None,
) -> bytes:
    """Render one final PNG page with exact text and a protected signature zone."""
    cfg = config or RenderConfig()
    if cfg.width < 800 or cfg.height < 1000:
        raise ValueError("render_resolution_too_small")
    if not illustration.image_bytes:
        raise ValueError("illustration_bytes_required")

    artwork_uri = _data_uri(illustration.image_bytes, illustration.mime_type)
    rtl = spec.language.lower().startswith(("ar", "fa", "ur"))
    safe_bottom = 82
    card_top = 206
    card_bottom = cfg.height - safe_bottom - 28
    card_height = max(220, card_bottom - card_top)
    blocks = page.blocks
    title_block = blocks[0]
    body_blocks = blocks[1:]
    columns = 2 if len(body_blocks) > 4 else 1
    gap = 22
    outer = 52

    svg: list[str] = [
        _svg_root(cfg),
        _defs(),
        _rect(0, 0, cfg.width, cfg.height, cfg.background),
        _rect(0, 0, cfg.width, 182, "url(#topGradient)"),
    ]

    if spec.template in {
        TemplateFamily.ANATOMY,
        TemplateFamily.MECHANISM,
        TemplateFamily.DRUG,
    }:
        svg.append(
            _rounded_rect(
                outer,
                card_top,
                cfg.width - 2 * outer,
                card_height,
                32,
                "#FFFFFF",
            )
        )
        image_height = min(390, card_height * 0.38)
        svg.append(
            _image(
                artwork_uri,
                outer + 24,
                card_top + 24,
                cfg.width - 2 * outer - 48,
                image_height,
            )
        )
        body_y = card_top + image_height + 48
        _render_cards(
            svg,
            body_blocks,
            x=outer + 22,
            y=body_y,
            width=cfg.width - 2 * outer - 44,
            height=card_bottom - body_y - 18,
            columns=columns,
            gap=gap,
            rtl=rtl,
            cfg=cfg,
            template=spec.template,
        )
    else:
        _render_cards(
            svg,
            body_blocks,
            x=outer,
            y=card_top,
            width=cfg.width - 2 * outer,
            height=card_height,
            columns=columns,
            gap=gap,
            rtl=rtl,
            cfg=cfg,
            template=spec.template,
        )

    title_x = cfg.width - outer if rtl else outer
    anchor = "end" if rtl else "start"
    direction = "rtl" if rtl else "ltr"
    svg.append(
        _text(
            title_block.text,
            title_x,
            82,
            anchor=anchor,
            direction=direction,
            size=48,
            weight=800,
            fill="#FFFFFF",
        )
    )
    section = page.sections[0] if page.sections else "Medical education"
    svg.append(
        _text(
            section,
            title_x,
            124,
            anchor=anchor,
            direction=direction,
            size=22,
            weight=500,
            fill="#EAF4FB",
        )
    )
    svg.append(_signature(cfg, safe_bottom))
    svg.append("</svg>")

    rendered = cairosvg.svg2png(
        bytestring="".join(svg).encode("utf-8"),
        output_width=cfg.width,
        output_height=cfg.height,
    )
    return cast(bytes, rendered)


def _render_cards(
    svg: list[str],
    blocks: list[TextBlock],
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    columns: int,
    gap: float,
    rtl: bool,
    cfg: RenderConfig,
    template: TemplateFamily,
) -> None:
    if not blocks:
        return
    rows = max(1, (len(blocks) + columns - 1) // columns)
    card_width = (width - gap * (columns - 1)) / columns
    card_height = (height - gap * (rows - 1)) / rows
    for index, block in enumerate(blocks):
        row = index // columns
        col = index % columns
        card_x = x + col * (card_width + gap)
        card_y = y + row * (card_height + gap)
        accent = _accent(block.role, cfg)
        svg.append(_rounded_rect(card_x, card_y, card_width, card_height, 26, "#FFFFFF"))
        svg.append(_accent_bar(card_x, card_y, card_height, accent))
        text_x = card_x + card_width - 28 if rtl else card_x + 30
        anchor = "end" if rtl else "start"
        direction = "rtl" if rtl else "ltr"
        role = _role_label(block.role, template, rtl)
        svg.append(
            _text(
                role,
                text_x,
                card_y + 38,
                anchor=anchor,
                direction=direction,
                size=18,
                weight=700,
                fill=accent,
            )
        )
        font_size = 24 if block.importance >= 4 else 21
        max_chars = 31 if columns == 2 else 54
        lines = _wrap(block.text, max_chars=max_chars)
        max_lines = max(3, int((card_height - 70) // (font_size + 9)))
        for line_index, line in enumerate(lines[:max_lines]):
            baseline = card_y + 76 + line_index * (font_size + 9)
            svg.append(
                _text(
                    line,
                    text_x,
                    baseline,
                    anchor=anchor,
                    direction=direction,
                    size=font_size,
                    weight=600,
                    fill=cfg.ink,
                )
            )


def _svg_root(cfg: RenderConfig) -> str:
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
) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" rx="{radius:.1f}" fill="{fill}" '
        'stroke="#DCE5ED" stroke-width="2"/>'
    )


def _accent_bar(x: float, y: float, height: float, fill: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="7" '
        f'height="{height:.1f}" rx="3" fill="{fill}"/>'
    )


def _image(uri: str, x: float, y: float, width: float, height: float) -> str:
    return (
        f'<image href="{uri}" x="{x:.1f}" y="{y:.1f}" '
        f'width="{width:.1f}" height="{height:.1f}" '
        'preserveAspectRatio="xMidYMid slice" opacity="0.92"/>'
    )


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
        f'direction="{direction}" font-family="Noto Sans Arabic, DejaVu Sans, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
        f'{_escape(value)}</text>'
    )


def _signature(cfg: RenderConfig, safe_bottom: int) -> str:
    y = cfg.height - safe_bottom + 8
    x = cfg.width - 52
    return (
        '<g opacity="0.88">'
        f'<rect x="{x - 190}" y="{y - 38}" width="190" height="52" '
        'rx="26" fill="#FFFFFF" fill-opacity="0.60" stroke="#FFFFFF" '
        'stroke-opacity="0.72" stroke-width="1.5"/>'
        f'<path d="M{x - 166} {y - 12} L{x - 132} {y - 1} '
        f'L{x - 160} {y + 11} Z" fill="#229ED9" opacity="0.9"/>'
        f'<path d="M{x - 166} {y - 12} L{x - 150} {y + 4} '
        f'L{x - 132} {y - 1} Z" fill="#FFFFFF" opacity="0.82"/>'
        f'<text x="{x - 108}" y="{y + 5}" font-family="DejaVu Sans, sans-serif" '
        f'font-size="20" font-weight="800" fill="{cfg.ink}">QMR7S</text>'
        '</g>'
    )


def _defs() -> str:
    return (
        '<defs><linearGradient id="topGradient" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#315F87"/>'
        '<stop offset="1" stop-color="#5AA5A0"/>'
        '</linearGradient></defs>'
    )


def _data_uri(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


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


def _accent(role: str, cfg: RenderConfig) -> str:
    return {
        "caution": cfg.caution,
        "danger": cfg.danger,
        "claim": cfg.primary,
        "point": cfg.teal,
        "title": cfg.purple,
    }.get(role, cfg.primary)


def _role_label(role: str, template: TemplateFamily, rtl: bool) -> str:
    del template
    if rtl:
        return {
            "claim": "معلومة",
            "point": "نقطة مهمة",
            "caution": "تنبيه",
            "danger": "تحذير",
            "subtitle": "ملخص",
            "title": "الموضوع",
        }.get(role, "معلومة")
    return {
        "claim": "Fact",
        "point": "Key point",
        "caution": "Caution",
        "danger": "Warning",
        "subtitle": "Summary",
        "title": "Topic",
    }.get(role, "Fact")


__all__ = ["RenderConfig", "render_infographic_page"]
