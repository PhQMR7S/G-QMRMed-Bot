"""Deterministic reference-driven Arabic medical infographic renderer."""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from functools import lru_cache

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

from gqmrmed.ai.infographic_design import InfographicDesignSpec, InfographicPage, TextBlock
from gqmrmed.generation.providers import GeneratedIllustration


@dataclass(frozen=True, slots=True)
class RenderConfig:
    """Canonical canvas matching the supplied master reference proportions."""

    width: int = 1024
    height: int = 1536
    background: str = "#FBF3F0"
    paper: str = "#FFFDFC"
    ink: str = "#33253A"
    muted: str = "#746B74"
    rose: str = "#C85E82"
    cyan: str = "#4C9FB0"
    mint: str = "#73A98C"
    purple: str = "#8C6AA9"
    amber: str = "#C49A5A"
    line: str = "#E5D9DD"
    soft_rose: str = "#F6E4E9"
    soft_cyan: str = "#E1F0F3"
    soft_mint: str = "#E6F1EA"
    soft_purple: str = "#EEE8F4"
    soft_amber: str = "#F5EBDD"


_SECTION_LABELS_AR = {
    "definition": "ما هو؟",
    "mechanism": "كيف يحدث؟",
    "key clinical points": "أهم النقاط",
    "cautions": "ملاحظة مهمة",
    "danger signs": "علامات الخطر",
    "initial actions": "الإجراءات الأولى",
    "decision points": "نقاط القرار",
    "escalation": "التصعيد",
    "test": "الفحوصات",
    "normal": "الطبيعي",
    "abnormal": "غير الطبيعي",
    "interpretation": "التفسير",
    "class": "الفئة",
    "uses": "الاستخدامات",
    "structure": "التركيب",
    "location": "الموقع",
    "trigger": "المحفز",
    "effect": "النتيجة",
    "clinical result": "النتيجة السريرية",
    "central concept": "الفكرة الأساسية",
    "mechanisms": "الآليات",
    "clinical manifestations": "المظاهر السريرية",
    "key takeaways": "الخلاصة",
}

_PALETTE = (
    ("#F6E4E9", "#C85E82"),
    ("#E1F0F3", "#4C9FB0"),
    ("#E6F1EA", "#73A98C"),
    ("#EEE8F4", "#8C6AA9"),
    ("#F5EBDD", "#C49A5A"),
)


def render_infographic_page(
    spec: InfographicDesignSpec,
    page: InfographicPage,
    illustration: GeneratedIllustration,
    *,
    config: RenderConfig | None = None,
) -> bytes:
    """Render one deterministic 1024x1536 infographic with exact RTL text."""
    cfg = config or RenderConfig()
    if cfg.width * 3 != cfg.height * 2:
        raise ValueError("render_canvas_must_be_2_3")
    if not illustration.image_bytes:
        raise ValueError("illustration_bytes_required")
    if page.page_number != 1 or len(spec.pages) != 1:
        raise ValueError("single_image_contract_violated")

    image = Image.new("RGB", (cfg.width, cfg.height), cfg.background)
    draw = ImageDraw.Draw(image)
    _background(draw, cfg)
    language = spec.language.lower()
    margin = 48

    _callout(draw, (margin, 44, 224, 126), "تثقيف طبي" if language != "en" else "MEDICAL", cfg.soft_rose, cfg.rose, language)
    _callout(draw, (800, 44, cfg.width - margin, 126), "مبني على الأدلة" if language != "en" else "EVIDENCE", cfg.soft_cyan, cfg.cyan, language)

    title = _clean(page.title)
    title_font = _fit_title(draw, title, language, max_width=690)
    title_y = 72
    _text(draw, title, (cfg.width / 2, title_y + title_font.size / 2), title_font, cfg.ink, anchor="mm")

    subtitle = _clean(page.subtitle) or _subtitle(language)
    _text(
        draw,
        subtitle,
        (cfg.width / 2, 188),
        _fit_font(draw, subtitle, _font(21, False, language), 760, 42, language),
        cfg.muted,
        anchor="mm",
    )

    art_box = (margin, 226, cfg.width - margin, 500)
    _artwork(image, illustration, art_box, cfg)
    _small_label(draw, (margin + 18, art_box[1] + 16), "المعلومة بصرياً" if language != "en" else "VISUAL", cfg)

    body = [block for block in page.blocks[1:] if _visible(block.text)]
    body = sorted(body, key=lambda block: -block.importance)[:9]
    if not body:
        raise ValueError("infographic_body_required")
    _cards(draw, body, page.sections, language, cfg, margin, 552, 1438)
    _footer(draw, language, cfg)
    return _png(image)


def _cards(
    draw: ImageDraw.ImageDraw,
    blocks: list[TextBlock],
    sections: list[str],
    language: str,
    cfg: RenderConfig,
    margin: int,
    top: int,
    bottom: int,
) -> None:
    count = len(blocks)
    cols = 2 if count <= 4 else 3
    rows = (count + cols - 1) // cols
    gap = 16
    card_w = (cfg.width - 2 * margin - gap * (cols - 1)) // cols
    card_h = (bottom - top - gap * (rows - 1)) // rows
    for index, block in enumerate(blocks):
        row, col = divmod(index, cols)
        x = margin + col * (card_w + gap)
        y = top + row * (card_h + gap)
        fill, accent = _colors(block.role, index)
        _card(draw, block, sections, index, language, x, y, card_w, card_h, fill, accent, cfg)


def _card(
    draw: ImageDraw.ImageDraw,
    block: TextBlock,
    sections: list[str],
    index: int,
    language: str,
    x: int,
    y: int,
    width: int,
    height: int,
    fill: str,
    accent: str,
    cfg: RenderConfig,
) -> None:
    radius = 24
    draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=fill, outline=cfg.line, width=2)
    header_h = 64
    draw.rounded_rectangle((x, y, x + width, y + header_h), radius=radius, fill=accent)
    draw.rectangle((x, y + header_h - 20, x + width, y + header_h), fill=accent)

    label = _section_label(sections, index, language)
    icon_cx = x + 30 if language == "en" else x + width - 30
    draw.ellipse((icon_cx - 16, y + 16, icon_cx + 16, y + 48), fill=cfg.paper)
    _text(draw, str(index + 1), (icon_cx, y + 32), _font(15, True, "en"), accent, anchor="mm")

    rtl = language != "en" or _is_rtl(block.text)
    label_x = x + width - 56 if rtl else x + 56
    _text(
        draw,
        label,
        (label_x, y + header_h / 2),
        _font(19 if width < 320 else 21, True, "ar" if rtl else "en"),
        cfg.paper,
        anchor="rm" if rtl else "lm",
    )

    pad = 22
    body_y = y + header_h + 24
    max_width = width - 2 * pad
    max_height = height - header_h - 36
    body_font = _fit_font(
        draw,
        block.text,
        _font(20 if width < 320 else 23, False, language),
        max_width,
        max_height,
        language,
    )
    lines = _wrap(draw, block.text, body_font, max_width)
    max_lines = max(3, max_height // (body_font.size + 8))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _truncate(draw, lines[-1], body_font, max_width)
    rtl_body = _is_rtl(block.text)
    anchor = "ra" if rtl_body else "la"
    text_x = x + width - pad if rtl_body else x + pad
    for line_no, line in enumerate(lines):
        _text(
            draw,
            line,
            (text_x, body_y + line_no * (body_font.size + 8)),
            body_font,
            cfg.ink,
            anchor=anchor,
        )


def _section_label(sections: list[str], index: int, language: str) -> str:
    if language == "en":
        return sections[index % len(sections)].replace("_", " ").title()
    section = sections[index % len(sections)].strip().lower()
    return _SECTION_LABELS_AR.get(section, "معلومة مهمة")


def _colors(role: str, index: int) -> tuple[str, str]:
    if role == "danger":
        return "#F8E1E4", "#B84F5E"
    if role == "caution":
        return "#F5E8D4", "#C28D43"
    return _PALETTE[index % len(_PALETTE)]


def _artwork(canvas: Image.Image, illustration: GeneratedIllustration, box: tuple[int, int, int, int], cfg: RenderConfig) -> None:
    x1, y1, x2, y2 = box
    panel = Image.new("RGB", (x2 - x1, y2 - y1), cfg.paper)
    try:
        art = Image.open(io.BytesIO(illustration.image_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise ValueError("illustration_bytes_invalid") from exc
    art.thumbnail((panel.width - 18, panel.height - 18), Image.Resampling.LANCZOS)
    panel.paste(art, ((panel.width - art.width) // 2, (panel.height - art.height) // 2))
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel.width - 1, panel.height - 1), radius=28, fill=255)
    canvas.paste(panel, (x1, y1), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=28, outline=cfg.line, width=2)


def _background(draw: ImageDraw.ImageDraw, cfg: RenderConfig) -> None:
    draw.ellipse((810, -120, 1110, 170), fill="#F4DCE4")
    draw.ellipse((-120, 1310, 180, 1610), fill="#E4F0F2")
    for x in range(70, 1000, 72):
        for y in range(30, 1500, 72):
            draw.ellipse((x, y, x + 2, y + 2), fill="#EFE5E7")


def _callout(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fill: str,
    accent: str,
    language: str,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1, y1, x2, y2), radius=38, fill=fill)
    _text(
        draw,
        text,
        ((x1 + x2) / 2, (y1 + y2) / 2),
        _font(16, True, "ar" if language != "en" else "en"),
        accent,
        anchor="mm",
    )


def _small_label(draw: ImageDraw.ImageDraw, pos: tuple[int, int], text: str, cfg: RenderConfig) -> None:
    font = _font(14, True, "ar" if _is_rtl(text) else "en")
    box = draw.textbbox((0, 0), _shape(text), font=font)
    w = box[2] - box[0] + 22
    x, y = pos
    draw.rounded_rectangle((x, y, x + w, y + 32), radius=16, fill=cfg.paper, outline=cfg.line)
    _text(draw, text, (x + w / 2, y + 16), font, cfg.ink, anchor="mm")


def _footer(draw: ImageDraw.ImageDraw, language: str, cfg: RenderConfig) -> None:
    y = 1464
    draw.rounded_rectangle((48, y, 174, y + 34), radius=17, fill=cfg.paper, outline=cfg.line)
    draw.ellipse((60, y + 11, 72, y + 23), fill=cfg.rose)
    draw.text((82, y + 17), "QMR7S", font=_font(13, True, "en"), fill=cfg.ink, anchor="lm")
    text = "للتثقيف الطبي فقط؛ لا يغني عن التقييم السريري." if language == "ar" else "For medical education only; not a substitute for clinical evaluation."
    _text(draw, text, (520, y + 17), _font(14, False, language), cfg.muted, anchor="mm")


def _fit_title(draw: ImageDraw.ImageDraw, text: str, language: str, max_width: int) -> ImageFont.FreeTypeFont:
    size = 60
    while size >= 42:
        font = _font(size, True, language)
        if _width(draw, text, font) <= max_width:
            return font
        size -= 2
    return _font(42, True, language)


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_height: int,
    language: str,
) -> ImageFont.FreeTypeFont:
    size = font.size
    while size >= 14:
        candidate = _font(size, False, language)
        if len(_wrap(draw, text, candidate, max_width)) * (size + 8) <= max_height:
            return candidate
        size -= 1
    return _font(14, False, language)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = _clean(text).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if _width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _truncate(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    value = text
    while value and _width(draw, value + "…", font) > max_width:
        value = value[:-1].rstrip()
    return value + "…"


def _width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), _shape(text), font=font)
    return box[2] - box[0]


def _text(
    draw: ImageDraw.ImageDraw,
    text: str,
    pos: tuple[float, float],
    font: ImageFont.FreeTypeFont,
    fill: str,
    *,
    anchor: str,
) -> None:
    draw.text(pos, _shape(text), font=font, fill=fill, anchor=anchor)


def _shape(text: str) -> str:
    if not _contains_arabic(text):
        return text
    return get_display(arabic_reshaper.reshape(text), base_dir="R")


@lru_cache(maxsize=96)
def _font(size: int, bold: bool, language: str) -> ImageFont.FreeTypeFont:
    if bold:
        paths = [
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    if language == "en":
        paths = paths[1:] + paths[:1]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.truetype("DejaVuSans.ttf", size)


def _contains_arabic(text: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" for char in text)


def _is_rtl(text: str) -> bool:
    return _contains_arabic(text)


def _clean(text: str) -> str:
    return " ".join(text.replace("\u200e", "").replace("\u200f", "").split())


def _visible(text: str) -> bool:
    value = text.lower()
    blocked = (
        "provider unavailable",
        "provider was unavailable",
        "fallback provider",
        "automatic synthesis",
        "internal error",
        "traceback",
        "stack trace",
    )
    return bool(text.strip()) and not any(marker in value for marker in blocked)


def _subtitle(language: str) -> str:
    if language == "ar":
        return "تثقيف طبي واضح • مبني على الأدلة"
    if language == "mixed":
        return "Medical education • تثقيف طبي مبني على الأدلة"
    return "Clear medical education • evidence informed"


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


__all__ = ["RenderConfig", "render_infographic_page"]
