"""Deterministic QMRMed compositor matching the agreed editorial infographic style."""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass
from typing import cast

import cairosvg

from gqmrmed.ai.infographic_design import InfographicDesignSpec, InfographicPage, TextBlock
from gqmrmed.generation.providers import GeneratedIllustration

# Long SVG literals are intentional in this deterministic compositor.
# ruff: noqa: E501


@dataclass(frozen=True, slots=True)
class RenderConfig:
    """Canonical 1080x1350 editorial canvas and restrained medical palette."""

    width: int = 1080
    height: int = 1350
    background: str = "#FCF7F5"
    paper: str = "#FFFDFC"
    ink: str = "#3B2334"
    muted: str = "#6F6470"
    pink: str = "#D98BA4"
    pink_light: str = "#F8E6EC"
    rose: str = "#A94F76"
    mint: str = "#BFDCCF"
    mint_light: str = "#E7F2EC"
    cyan: str = "#8CCDD8"
    cyan_light: str = "#E5F4F6"
    purple: str = "#B59BD2"
    purple_light: str = "#EEE8F6"
    gold: str = "#C79A55"
    gold_light: str = "#F6EBD9"
    line: str = "#E8DDE1"
    danger: str = "#B94F62"


def render_infographic_page(
    spec: InfographicDesignSpec,
    page: InfographicPage,
    illustration: GeneratedIllustration,
    *,
    config: RenderConfig | None = None,
) -> bytes:
    """Render one readable 4:5 medical editorial infographic."""
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
    title = _compact(page.title, 76)
    body = _usable_blocks(page.blocks[1:])
    if not body:
        raise ValueError("infographic_body_required")

    svg: list[str] = [_root(cfg), _defs()]
    svg.append(_rect(0, 0, cfg.width, cfg.height, cfg.background))
    svg.append(_editorial_background(cfg))

    # Header
    svg.append(_pill(56, 44, 184, 42, cfg.rose, "QMRMed  •  MEDICAL", cfg.paper))
    title_lines = _wrap(title, 24 if rtl else 29)
    title_size = 58 if len(title_lines) == 1 else 48
    for index, line in enumerate(title_lines[:2]):
        svg.append(
            _text(
                line,
                cfg.width - 56 if rtl else 56,
                126 + index * (title_size + 4),
                anchor=anchor,
                direction=direction,
                size=title_size,
                weight=900,
                fill=cfg.ink,
            )
        )
    subtitle = (
        "تثقيف طبي مبسّط • مبني على الأدلة"
        if rtl
        else "Clear medical education • evidence informed"
    )
    svg.append(
        _text(
            subtitle,
            cfg.width - 56 if rtl else 56,
            176 if len(title_lines) == 1 else 224,
            anchor=anchor,
            direction=direction,
            size=20,
            weight=500,
            fill=cfg.muted,
        )
    )

    # Dominant artwork. AI artwork is kept free of readable text.
    art_y = 204 if len(title_lines) == 1 else 248
    art_x, art_w, art_h = 56, cfg.width - 112, 300
    svg.append(_art_panel(art_x, art_y, art_w, art_h, illustration, cfg))
    svg.append(_pill(art_x + 20, art_y + 20, 122, 36, cfg.paper, "VISUAL", cfg.ink, opacity=0.94))

    grid_y = art_y + art_h + 22
    grid_h = 670 if len(title_lines) == 1 else 625
    _render_editorial_grid(
        svg,
        body,
        x=56,
        y=grid_y,
        width=cfg.width - 112,
        height=grid_h,
        rtl=rtl,
        cfg=cfg,
        topic=spec.topic,
    )

    footer_y = 1310
    svg.append(
        _text(
            "للتثقيف الطبي فقط؛ لا يغني عن التقييم السريري."
            if rtl
            else "For medical education only; not a substitute for clinical evaluation.",
            cfg.width / 2,
            footer_y,
            anchor="middle",
            direction=direction,
            size=14,
            weight=500,
            fill=cfg.muted,
        )
    )
    svg.append(_watermark(cfg))
    svg.append("</svg>")
    rendered = cairosvg.svg2png(
        bytestring="".join(svg).encode("utf-8"),
        output_width=cfg.width,
        output_height=cfg.height,
    )
    return cast(bytes, rendered)


def _render_editorial_grid(
    svg: list[str],
    blocks: list[TextBlock],
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    rtl: bool,
    cfg: RenderConfig,
    topic: str,
) -> None:
    blocks = blocks[:6]
    count = len(blocks)
    columns = 2 if count <= 4 else 3
    gap = 16
    rows = (count + columns - 1) // columns
    card_w = (width - gap * (columns - 1)) / columns
    card_h = (height - gap * (rows - 1)) / rows
    for index, block in enumerate(blocks):
        row = index // columns
        col = index % columns
        card_x = x + col * (card_w + gap)
        card_y = y + row * (card_h + gap)
        fill, accent = _panel_colors(index, cfg)
        svg.append(_rounded(card_x, card_y, card_w, card_h, 24, fill, cfg.line))

        header_h = 58
        svg.append(_rounded(card_x + 2, card_y + 2, card_w - 4, header_h, 20, accent, "none"))
        svg.append(_rect(card_x + 2, card_y + header_h - 18, card_w - 4, 18, accent))

        text_x = card_x + card_w - 24 if rtl else card_x + 24
        text_anchor = "end" if rtl else "start"
        label = _section_label(block, index, topic, rtl)
        svg.append(
            _text(
                label,
                text_x,
                card_y + 38,
                anchor=text_anchor,
                direction="rtl" if rtl else "ltr",
                size=21,
                weight=900,
                fill=cfg.paper,
            )
        )

        lines = _fit_lines(
            block.text,
            30 if columns == 3 else 43,
            max_lines=max(3, int((card_h - 82) / 29)),
        )
        for line_index, line in enumerate(lines):
            svg.append(
                _text(
                    line,
                    text_x,
                    card_y + 94 + line_index * 29,
                    anchor=text_anchor,
                    direction="rtl" if rtl else "ltr",
                    size=19 if columns == 3 else 20,
                    weight=600,
                    fill=cfg.ink,
                )
            )


def _section_label(block: TextBlock, index: int, topic: str, rtl: bool) -> str:
    if not rtl:
        labels = ("What is it?", "How it happens", "Key features", "Diagnosis", "Treatment", "Important note")
        return labels[index % len(labels)]
    labels = ("شنو هو؟", "شلون يصير؟", "أهم الأعراض", "شلون نشخّصه؟", "العلاج", "ملاحظات مهمة")
    if block.role == "danger":
        return "⚠ تنبيه"
    if "علاج" in topic or "treatment" in topic.lower():
        labels = ("شنو هو؟", "شلون يصير؟", "أهم النقاط", "التشخيص", "العلاج", "تنبيه")
    return labels[index % len(labels)]


def _panel_colors(index: int, cfg: RenderConfig) -> tuple[str, str]:
    palette = (
        (cfg.pink_light, cfg.rose),
        (cfg.cyan_light, "#4C9EAD"),
        (cfg.mint_light, "#5E9E83"),
        (cfg.purple_light, "#8766A9"),
        (cfg.gold_light, "#A87536"),
        (cfg.pink_light, cfg.rose),
    )
    return palette[index % len(palette)]


def _art_panel(
    x: float,
    y: float,
    width: float,
    height: float,
    illustration: GeneratedIllustration,
    cfg: RenderConfig,
) -> str:
    uri = _data_uri(illustration.image_bytes, illustration.mime_type)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'rx="30" fill="{cfg.paper}" stroke="{cfg.line}" stroke-width="2"/>'
        f'<image href="{uri}" x="{x + 5:.1f}" y="{y + 5:.1f}" '
        f'width="{width - 10:.1f}" height="{height - 10:.1f}" '
        'preserveAspectRatio="xMidYMid meet" opacity="1"/>'
    )


def _watermark(cfg: RenderConfig) -> str:
    x, y = 56, 1254
    return (
        f'<g opacity="0.72"><rect x="{x}" y="{y}" width="120" height="30" rx="15" '
        f'fill="{cfg.paper}" stroke="{cfg.line}"/>'
        f'<circle cx="{x + 18}" cy="{y + 15}" r="7" fill="{cfg.rose}"/>'
        f'<text x="{x + 32}" y="{y + 20}" font-family="DejaVu Sans, sans-serif" '
        f'font-size="13" font-weight="800" fill="{cfg.ink}">QMR7S</text></g>'
    )


def _editorial_background(cfg: RenderConfig) -> str:
    return (
        f'<circle cx="1000" cy="70" r="170" fill="{cfg.pink}" opacity="0.10"/>'
        f'<circle cx="90" cy="1280" r="130" fill="{cfg.cyan}" opacity="0.08"/>'
        f'<path d="M850 40 C930 80 960 10 1030 55" fill="none" stroke="{cfg.purple}" '
        'stroke-width="3" opacity="0.35"/>'
    )


def _defs() -> str:
    return '<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="7" stdDeviation="10" flood-opacity="0.10"/></filter></defs>'


def _root(cfg: RenderConfig) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{cfg.width}" height="{cfg.height}" viewBox="0 0 {cfg.width} {cfg.height}">'


def _rect(x: float, y: float, width: float, height: float, fill: str) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" fill="{fill}"/>'


def _rounded(x: float, y: float, width: float, height: float, radius: float, fill: str, stroke: str) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{radius:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def _pill(x: float, y: float, width: float, height: float, fill: str, value: str, text_fill: str, *, opacity: float = 1.0) -> str:
    return (
        f'<g opacity="{opacity}"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{height / 2}" fill="{fill}"/>'
        f'<text x="{x + width / 2}" y="{y + height / 2 + 5}" text-anchor="middle" font-family="DejaVu Sans, Noto Sans Arabic, sans-serif" font-size="15" font-weight="800" fill="{text_fill}">{_escape(value)}</text></g>'
    )


def _text(value: str, x: float, y: float, *, anchor: str, direction: str, size: int, weight: int, fill: str) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" direction="{direction}" '
        'font-family="Noto Sans Arabic, DejaVu Sans, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{_escape(value)}</text>'
    )


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _data_uri(data: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _compact(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_lines(text: str, max_chars: int, *, max_lines: int) -> list[str]:
    lines = _wrap(text, max_chars)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    kept[-1] = _compact(kept[-1], max_chars - 1) + "…"
    return kept


def _usable_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    internal = (
        "automatic synthesis provider was unavailable",
        "synthesis provider was unavailable",
        "provider was unavailable",
        "provider unavailable",
        "fallback provider",
        "internal error",
        "traceback",
    )
    usable: list[TextBlock] = []
    for block in blocks:
        value = " ".join(block.text.lower().split())
        if any(marker in value for marker in internal):
            continue
        if "http://" in value or "https://" in value:
            continue
        usable.append(block)
    return usable[:6]
