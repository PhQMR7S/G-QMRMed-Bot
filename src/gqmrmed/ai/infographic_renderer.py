"""Deterministic reference-driven Arabic medical infographic renderer."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from functools import lru_cache

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

from gqmrmed.ai.design_preferences import DesignPreferences
from gqmrmed.ai.infographic_design import InfographicDesignSpec, InfographicPage, TextBlock
from gqmrmed.generation.providers import GeneratedIllustration


@dataclass(frozen=True, slots=True)
class RenderConfig:
    """Canonical 1024x1536 canvas and reference palette."""

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
_DEFAULT_ACCENTS = ("#C85E82", "#4C9FB0", "#73A98C", "#8C6AA9", "#C49A5A")


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

    prefs = spec.design_preferences
    background = _valid_hex(prefs.background) or cfg.background
    accents = _accent_palette(cfg, prefs)
    page_ink, page_muted = _contrast_text(background, cfg)
    image = Image.new("RGB", (cfg.width, cfg.height), background)
    draw = ImageDraw.Draw(image)
    _background(draw, cfg, prefs)
    language = spec.language.lower()
    margin = 48

    callout_left = accents[0]
    callout_right = accents[1 % len(accents)]
    _callout(draw, (margin, 34, 224, 92), "تثقيف طبي" if language != "en" else "MEDICAL", _soften(callout_left), _readable_accent(callout_left), language)
    _callout(draw, (800, 34, cfg.width - margin, 92), "مبني على الأدلة" if language != "en" else "EVIDENCE", _soften(callout_right), _readable_accent(callout_right), language)

    title = _clean(page.title)
    title_font = _fit_title(draw, title, language, 720, prefs.font_scale)
    if prefs.header_style == "banner":
        banner = (margin, 104, cfg.width - margin, 174)
        draw.rounded_rectangle(banner, radius=24, fill=callout_left)
        _text(draw, title, (cfg.width / 2, 139), title_font, _contrast_text(callout_left, cfg)[0], anchor="mm")
    else:
        title_anchor = "lm" if prefs.header_style == "left" else "mm"
        title_x = margin if title_anchor == "lm" else cfg.width / 2
        _text(draw, title, (title_x, 132), title_font, page_ink, anchor=title_anchor)

    subtitle = _clean(page.subtitle) or _subtitle(language)
    _text(draw, subtitle, (cfg.width / 2, 190), _fit_font(draw, subtitle, _font(max(14, round(20 * prefs.font_scale)), False, language), 760, 40, language), page_muted, anchor="mm")

    art_box = _illustration_box(cfg, margin, prefs)
    _artwork(image, illustration, art_box, cfg)
    _small_label(draw, (art_box[0] + 18, art_box[1] + 16), "المعلومة بصرياً" if language != "en" else "VISUAL", cfg, page_ink)

    body = sorted((block for block in page.blocks[1:] if _visible(block.text)), key=lambda block: -block.importance)[:9]
    if not body:
        raise ValueError("infographic_body_required")
    card_top = art_box[3] + 24
    card_bottom = 1434 if prefs.show_footer else 1482
    if card_top >= card_bottom:
        raise ValueError("illustration_leaves_no_card_area")
    _cards(draw, body, page.sections, language, cfg, prefs, margin, card_top, card_bottom)
    if prefs.show_footer:
        _footer(draw, language, cfg)
    return _png(image)


def _illustration_box(cfg: RenderConfig, margin: int, prefs: DesignPreferences) -> tuple[int, int, int, int]:
    if prefs.illustration_position == "lower_middle":
        return (margin, 330, cfg.width - margin, 604)
    if prefs.illustration_position == "left":
        return (margin, 226, cfg.width // 2 - 8, 500)
    if prefs.illustration_position == "right":
        return (cfg.width // 2 + 8, 226, cfg.width - margin, 500)
    return (margin, 226, cfg.width - margin, 500)


def _cards(draw: ImageDraw.ImageDraw, blocks: list[TextBlock], sections: list[str], language: str, cfg: RenderConfig, prefs: DesignPreferences, margin: int, top: int, bottom: int) -> None:
    count = len(blocks)
    cols = 2 if prefs.layout in {"flow", "timeline", "two_column", "comparison", "central"} else 3 if prefs.layout == "three_column" else (2 if count <= 4 else 3)
    rows = (count + cols - 1) // cols
    gap = 12 if prefs.density == "compact" else 20 if prefs.density == "airy" else 16
    card_w = (cfg.width - 2 * margin - gap * (cols - 1)) // cols
    card_h = (bottom - top - gap * (rows - 1)) // rows
    if card_h < 100:
        raise ValueError("card_area_too_small_for_readable_text")
    for index, block in enumerate(blocks):
        row, col = divmod(index, cols)
        x = margin + col * (card_w + gap)
        y = top + row * (card_h + gap)
        fill, accent = _colors(block.role, index, cfg, prefs)
        _card(draw, block, sections, index, language, x, y, card_w, card_h, fill, accent, cfg, prefs)
        if prefs.layout in {"flow", "timeline"} and index < count - 1:
            next_row, _ = divmod(index + 1, cols)
            if next_row == row:
                cx = x + card_w + gap / 2
                cy = y + card_h / 2
                draw.line((cx - 7, cy, cx + 7, cy), fill=accent, width=3)


def _card(draw: ImageDraw.ImageDraw, block: TextBlock, sections: list[str], index: int, language: str, x: int, y: int, width: int, height: int, fill: str, accent: str, cfg: RenderConfig, prefs: DesignPreferences) -> None:
    radius = max(6, min(42, prefs.card_radius))
    draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=fill, outline=cfg.line, width=2)
    header_h = min(64, max(52, height // 4))
    draw.rounded_rectangle((x, y, x + width, y + header_h), radius=radius, fill=accent)
    draw.rectangle((x, y + header_h - min(18, header_h // 3), x + width, y + header_h), fill=accent)
    rtl = language != "en" or _is_rtl(block.text)
    icon_cx = x + 30 if not rtl else x + width - 30
    draw.ellipse((icon_cx - 16, y + 10, icon_cx + 16, y + 42), fill=cfg.paper)
    _text(draw, str(index + 1), (icon_cx, y + 26), _font(14, True, "en"), _contrast_text(accent, cfg)[0], anchor="mm")
    label = _section_label(sections, index, language)
    label_x = x + width - 56 if rtl else x + 56
    _text(draw, label, (label_x, y + header_h / 2), _font(max(13, round(19 * prefs.font_scale)), True, "ar" if rtl else "en"), _contrast_text(accent, cfg)[0], anchor="rm" if rtl else "lm")
    pad = 22
    body_y = y + header_h + 22
    max_width = width - 2 * pad
    max_height = height - header_h - 32
    body_font = _fit_font(draw, block.text, _font(max(14, round(22 * prefs.font_scale)), False, language), max_width, max_height, language)
    lines = _wrap(draw, block.text, body_font, max_width)
    max_lines = max(2, max_height // (body_font.size + 8))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _truncate(draw, lines[-1], body_font, max_width)
    rtl_body = _is_rtl(block.text)
    text_x = x + width - pad if rtl_body else x + pad
    for line_no, line in enumerate(lines):
        _text(draw, line, (text_x, body_y + line_no * (body_font.size + 8)), body_font, cfg.ink, anchor="ra" if rtl_body else "la")


def _section_label(sections: list[str], index: int, language: str) -> str:
    if language == "en":
        return sections[index % len(sections)].replace("_", " ").title()
    return _SECTION_LABELS_AR.get(sections[index % len(sections)].strip().lower(), "معلومة مهمة")


def _accent_palette(cfg: RenderConfig, prefs: DesignPreferences) -> tuple[str, ...]:
    if prefs.palette:
        valid = tuple(value for value in prefs.palette if _valid_hex(value))
        if valid:
            return valid
    return _DEFAULT_ACCENTS


def _colors(role: str, index: int, cfg: RenderConfig, prefs: DesignPreferences) -> tuple[str, str]:
    if role == "danger":
        accent = "#B84F5E"
    elif role == "caution":
        accent = "#C28D43"
    else:
        accents = _accent_palette(cfg, prefs)
        accent = accents[index % len(accents)]
    return _soften(accent), accent


def _soften(value: str) -> str:
    value = value.lstrip("#")
    if len(value) != 6:
        return "#F3EEF0"
    try:
        rgb = tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return "#F3EEF0"
    return "#%02X%02X%02X" % tuple(round(channel * 0.18 + 255 * 0.82) for channel in rgb)


def _valid_hex(value: str | None) -> str | None:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return None
    try:
        int(value[1:], 16)
    except ValueError:
        return None
    return value.upper()


def _contrast_text(background: str, cfg: RenderConfig) -> tuple[str, str]:
    value = background.lstrip("#")
    if len(value) != 6:
        return cfg.ink, cfg.muted
    rgb = tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    luminance = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255
    if luminance < 0.48:
        return "#FFFDFC", "#E9E1E8"
    return cfg.ink, cfg.muted


def _readable_accent(accent: str) -> str:
    """Choose dark ink for very light custom accents and white for dark ones."""
    value = accent.lstrip("#")
    if len(value) != 6:
        return "#33253A"
    rgb = tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    luminance = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255
    return "#33253A" if luminance > 0.60 else "#FFFDFC"


def _artwork(canvas: Image.Image, illustration: GeneratedIllustration, box: tuple[int, int, int, int], cfg: RenderConfig) -> None:
    x1, y1, x2, y2 = box
    panel = Image.new("RGB", (x2 - x1, y2 - y1), cfg.paper)
    try:
        art = Image.open(io.BytesIO(illustration.image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("illustration_bytes_invalid") from exc
    art.thumbnail((panel.width - 18, panel.height - 18), Image.Resampling.LANCZOS)
    panel.paste(art, ((panel.width - art.width) // 2, (panel.height - art.height) // 2))
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel.width - 1, panel.height - 1), radius=28, fill=255)
    canvas.paste(panel, (x1, y1), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=28, outline=cfg.line, width=2)


def _background(draw: ImageDraw.ImageDraw, cfg: RenderConfig, prefs: DesignPreferences) -> None:
    accents = _accent_palette(cfg, prefs)
    draw.ellipse((810, -120, 1110, 170), fill=_soften(accents[0]))
    draw.ellipse((-120, 1310, 180, 1610), fill=_soften(accents[1 % len(accents)]))
    dot = _soften(cfg.line)
    for x in range(70, 1000, 72):
        for y in range(30, 1500, 72):
            draw.ellipse((x, y, x + 2, y + 2), fill=dot)


def _callout(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fill: str, accent: str, language: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=28, fill=fill)
    _text(draw, text, ((x1 + x2) / 2, (y1 + y2) / 2), _font(15, True, "ar" if language != "en" else "en"), accent, anchor="mm")


def _small_label(draw: ImageDraw.ImageDraw, pos: tuple[int, int], text: str, cfg: RenderConfig, ink: str) -> None:
    font = _font(13, True, "ar" if _is_rtl(text) else "en")
    box = draw.textbbox((0, 0), _shape(text), font=font)
    w = box[2] - box[0] + 22
    x, y = pos
    draw.rounded_rectangle((x, y, x + w, y + 32), radius=16, fill=cfg.paper, outline=cfg.line)
    _text(draw, text, (x + w / 2, y + 16), font, ink, anchor="mm")


def _footer(draw: ImageDraw.ImageDraw, language: str, cfg: RenderConfig) -> None:
    y = 1464
    draw.rounded_rectangle((48, y, 174, y + 34), radius=17, fill=cfg.paper, outline=cfg.line)
    draw.ellipse((60, y + 11, 72, y + 23), fill=cfg.rose)
    draw.text((82, y + 17), "QMR7S", font=_font(13, True, "en"), fill=cfg.ink, anchor="lm")
    text = "للتثقيف الطبي فقط؛ لا يغني عن التقييم السريري." if language == "ar" else "For medical education only; not a substitute for clinical evaluation."
    _text(draw, text, (520, y + 17), _font(14, False, language), cfg.muted, anchor="mm")


def _fit_title(draw: ImageDraw.ImageDraw, text: str, language: str, max_width: int, scale: float = 1.0) -> ImageFont.FreeTypeFont:
    size = round(60 * scale)
    while size >= 34:
        font = _font(size, True, language)
        if _width(draw, text, font) <= max_width:
            return font
        size -= 2
    return _font(max(34, round(42 * scale)), True, language)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_height: int, language: str) -> ImageFont.FreeTypeFont:
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


def _text(draw: ImageDraw.ImageDraw, text: str, pos: tuple[float, float], font: ImageFont.FreeTypeFont, fill: str, *, anchor: str) -> None:
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
    blocked = ("provider unavailable", "provider was unavailable", "fallback provider", "automatic synthesis", "internal error", "traceback", "stack trace")
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
