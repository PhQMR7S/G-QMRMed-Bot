"""Deterministic QMRMed compositor.

The model-generated artwork is treated as a visual asset. All visible text,
cards, hierarchy, and the QMR7S signature are rendered here for exactness.
"""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass

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
    """Render one final PNG page with exact text and a non-overlapping signature."""
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
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{cfg.width}" '
            f'height="{cfg.height}" viewBox="0 0 {cfg.width} {cfg.height}">'
        ),
        _defs(),
        f'<rect width="{cfg.width}" height="{cfg.height}" fill="{cfg.background}"/>',
        f'<rect x="0" y="0" width="{cfg.width}" height="182" fill="url(#topGradient)"/>',
    ]

    if spec.template in {
        TemplateFamily.ANATOMY,
        TemplateFamily.MECHANISM,
        TemplateFamily.DRUG,
    }:
        svg.append(
            f'<rect x="{outer}" y="{card_top}" width="{cfg.width - 2 * outer}" '
            f'height="{card_height}" rx="32" fill="#FFFFFF" stroke="#DCE5ED"/>'
        )
        image_height = min(390, card_height * 0.38)
        svg.append(
            f'<image href="{artwork_uri}" x="{outer + 24}" y="{card_top + 24}" '
            f'width="{cfg.width - 2 * outer - 48}" height="{image_height}" '
            'preserveAspectRatio="xMidYMid slice" opacity="0.92"/>'
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
    svg.extend(
        [
            f'<text x="{title_x}" y="82" text-anchor="{anchor}" direction="{direction}" '
            'font-family="Noto Sans Arabic, DejaVu Sans, sans-serif" '
            f'font-size="48" font-weight="800" fill="#FFFFFF">{_escape(title_block.text)}</text>',
            f'<text x="{title_x}" y="124" text-anchor="{anchor}" direction="{direction}" '
            'font-family="Noto Sans Arabic, DejaVu Sans, sans-serif" '
            'font-size="22" fill="#EAF4FB">'
            f'{_escape(page.sections[0] if page.sections else "Medical education")}</text>',
        ]
    )
    svg.append(_signature(cfg, safe_bottom))
    svg.append("</svg>")

    return cairosvg.svg2png(
        bytestring="".join(svg).encode("utf-8"),
        output_width=cfg.width,
        output_height=cfg.height,
    )


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
        svg.append(
            f'<rect x="{card_x:.1f}" y="{card_y:.1f}" width="{card_width:.1f}" '
            f'height="{card_height:.1f}" rx="26" fill="#FFFFFF" '
            'stroke="#DCE5ED" stroke-width="2"/>'
        )
        svg.append(
            f'<rect x="{card_x:.1f}" y="{card_y:.1f}" width="7" '
            f'height="{card_height:.1f}" rx="3" fill="{accent}"/>'
        )
        text_x = card_x + card_width - 28 if rtl else card_x + 30
        anchor = "end" if rtl else "start"
        direction = "rtl" if rtl else "ltr"
        role = _role_label(block.role, template)
        svg.append(
            f'<text x="{text_x:.1f}" y="{card_y + 38:.1f}" '
            f'text-anchor="{anchor}" direction="{direction}" '
            'font-family="Noto Sans Arabic, DejaVu Sans, sans-serif" '
            'font-size="18" font-weight="700" '
            f'fill="{accent}">{_escape(role)}</text>'
        )
        font_size = 24 if block.importance >= 4 else 21
        max_chars = 31 if columns == 2 else 54
        lines = _wrap(block.text, max_chars=max_chars)
        max_lines = max(3, int((card_height - 70) // (font_size + 9)))
        for line_index, line in enumerate(lines[:max_lines]):
            baseline = card_y + 76 + line_index * (font_size + 9)
            svg.append(
                f'<text x="{text_x:.1f}" y="{baseline:.1f}" '
                f'text-anchor="{anchor}" direction="{direction}" '
                'font-family="Noto Sans Arabic, DejaVu Sans, sans-serif" '
                f'font-size="{font_size}" font-weight="600" fill="{cfg.ink}">'
                f'{_escape(line)}</text>'
            )


def _signature(cfg: RenderConfig, safe_bottom: int) -> str:
    y = cfg.height - safe_bottom + 8
    x = cfg.width - 52
    return (
        '<g opacity="0.88">'
        f'<rect x="{x - 190}" y="{y - 38}" width="190" height="52" rx="26" '
        'fill="#FFFFFF" fill-opacity="0.60" stroke="#FFFFFF" '
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
        '<stop offset="0" stop-color="#315F87"/><stop offset="1" '
        'stop-color="#5AA5A0"/></linearGradient></defs>'
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


def _role_label(role: str, template: TemplateFamily) -> str:
    del template
    return {
        "claim": "معلومة",
        "point": "نقطة مهمة",
        "caution": "تنبيه",
        "danger": "تحذير",
        "subtitle": "ملخص",
        "title": "الموضوع",
    }.get(role, "معلومة")


__all__ = ["RenderConfig", "render_infographic_page"]
