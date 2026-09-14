"""Publication-grade QMRMed editorial infographic renderer."""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from gqmrmed.ai.infographic_design import InfographicDesignSpec, InfographicPage, TextBlock
from gqmrmed.generation.providers import GeneratedIllustration


@dataclass(frozen=True, slots=True)
class RenderConfig:
    """Canonical 1080x1350 editorial canvas."""

    width: int = 1080
    height: int = 1350
    background: str = "#FBF8F6"
    paper: str = "#FFFFFF"
    ink: str = "#241C2A"
    muted: str = "#6D6670"
    navy: str = "#17345B"
    teal: str = "#2E9DAA"
    green: str = "#5C9B80"
    rose: str = "#B45478"
    purple: str = "#8063A6"
    gold: str = "#B17B32"
    line: str = "#E7DEE3"


def render_infographic_page(
    spec: InfographicDesignSpec,
    page: InfographicPage,
    illustration: GeneratedIllustration,
    *,
    config: RenderConfig | None = None,
) -> bytes:
    """Render one 1080x1350 infographic with correct Arabic/English shaping."""
    cfg = config or RenderConfig()
    if cfg.width * 5 != cfg.height * 4:
        raise ValueError("render_canvas_must_be_4_5")
    if not illustration.image_bytes:
        raise ValueError("illustration_bytes_required")
    if page.page_number != 1 or len(spec.pages) != 1:
        raise ValueError("single_image_contract_violated")

    image = Image.new("RGB", (cfg.width, cfg.height), cfg.background)
    draw = ImageDraw.Draw(image)
    _background(draw, cfg)
    language = spec.language.lower()

    margin = 58
    _badge(draw, (margin, 42), "QMRMed • MEDICAL", cfg.rose, cfg.paper)
    title = _clean(page.title)
    title_font = _font(68, True, language)
    if _width(draw, title, title_font) > 900:
        title_font = _font(56, True, language)
    title_lines = _wrap(draw, title, title_font, 900)
    if len(title_lines) > 2:
        title_lines = title_lines[:2]
        title_lines[-1] = _truncate(draw, title_lines[-1], title_font, 900)
    title_y = 125
    for index, line in enumerate(title_lines):
        rtl = _is_arabic(line)
        draw.text(
            (cfg.width - margin if rtl else margin, title_y + index * (title_font.size + 4)),
            line,
            font=title_font,
            fill=cfg.ink,
            anchor="ra" if rtl else "la",
            direction="rtl" if rtl else "ltr",
        )
    subtitle = _subtitle(language)
    sub_y = title_y + len(title_lines) * (title_font.size + 4) + 10
    draw.text(
        (cfg.width - margin if _is_arabic(subtitle) else margin, sub_y),
        subtitle,
        font=_font(22, False, language),
        fill=cfg.muted,
        anchor="ra" if _is_arabic(subtitle) else "la",
        direction="rtl" if _is_arabic(subtitle) else "ltr",
    )

    art_y = max(245, sub_y + 48)
    _artwork(image, illustration, (margin, art_y, cfg.width - margin, art_y + 320), cfg)
    _small_label(draw, (margin + 20, art_y + 18), "مرئي" if language == "ar" else "VISUAL", cfg)

    body = [b for b in page.blocks[1:] if _visible(b.text)]
    body = sorted(body, key=lambda b: -b.importance)[:6]
    if not body:
        raise ValueError("infographic_body_required")
    top = art_y + 348
    bottom = 1232
    _cards(draw, body, language, cfg, margin, top, bottom)
    _footer(draw, image, language, cfg)
    return _png(image)


def _cards(draw: ImageDraw.ImageDraw, blocks: list[TextBlock], language: str, cfg: RenderConfig, margin: int, top: int, bottom: int) -> None:
    count = len(blocks)
    cols = 2 if count <= 4 else 3
    rows = (count + cols - 1) // cols
    gap = 18
    width = cfg.width - 2 * margin
    card_w = (width - gap * (cols - 1)) // cols
    card_h = (bottom - top - gap * (rows - 1)) // rows
    labels_ar = ("ما هو؟", "كيف يحدث؟", "أهم النقاط", "التشخيص", "العلاج", "ملاحظة مهمة")
    labels_en = ("What is it?", "How it happens", "Key points", "Diagnosis", "Treatment", "Important note")
    for index, block in enumerate(blocks):
        row, col = divmod(index, cols)
        x = margin + col * (card_w + gap)
        y = top + row * (card_h + gap)
        fill, accent = _colors(block.role, index, cfg)
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=26, fill=fill, outline=cfg.line, width=2)
        header = 62 if cols == 2 else 58
        draw.rounded_rectangle((x, y, x + card_w, y + header), radius=26, fill=accent)
        draw.rectangle((x, y + header - 20, x + card_w, y + header), fill=accent)
        rtl = language == "ar" or _is_arabic(block.text)
        label = labels_ar[index] if rtl else labels_en[index]
        draw.text(
            (x + card_w - 22 if rtl else x + 22, y + header / 2),
            label,
            font=_font(23 if cols == 2 else 20, True, "ar" if rtl else "en"),
            fill=cfg.paper,
            anchor="rm" if rtl else "lm",
            direction="rtl" if rtl else "ltr",
        )
        pad = 22
        max_width = card_w - 2 * pad
        body_font = _fit_font(draw, block.text, _font(24 if cols == 2 else 20, False, language), max_width, card_h - header - 34, language)
        lines = _wrap(draw, block.text, body_font, max_width)
        max_lines = max(3, (card_h - header - 34) // (body_font.size + 8))
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = _truncate(draw, lines[-1], body_font, max_width)
        rtl_body = _is_arabic(block.text)
        for line_no, line in enumerate(lines):
            draw.text(
                (x + card_w - pad if rtl_body else x + pad, y + header + 28 + line_no * (body_font.size + 8)),
                line,
                font=body_font,
                fill=cfg.ink,
                anchor="ra" if rtl_body else "la",
                direction="rtl" if rtl_body else "ltr",
            )


def _colors(role: str, index: int, cfg: RenderConfig) -> tuple[str, str]:
    if role == "danger":
        return "#F9E5E7", "#B94B58"
    if role == "caution":
        return "#F7EBD8", cfg.gold
    palette = (("#F8E7ED", cfg.rose), ("#E6F4F4", cfg.teal), ("#EAF4EE", cfg.green), ("#EEE9F6", cfg.purple), ("#F7EBD8", cfg.gold))
    return palette[index % len(palette)]


def _artwork(canvas: Image.Image, illustration: GeneratedIllustration, box: tuple[int, int, int, int], cfg: RenderConfig) -> None:
    x1, y1, x2, y2 = box
    panel = Image.new("RGB", (x2 - x1, y2 - y1), cfg.paper)
    try:
        art = Image.open(io.BytesIO(illustration.image_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise ValueError("illustration_bytes_invalid") from exc
    art.thumbnail((panel.width - 16, panel.height - 16), Image.Resampling.LANCZOS)
    panel.paste(art, ((panel.width - art.width) // 2, (panel.height - art.height) // 2))
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel.width - 1, panel.height - 1), radius=30, fill=255)
    canvas.paste(panel, (x1, y1), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=30, outline=cfg.line, width=2)


def _background(draw: ImageDraw.ImageDraw, cfg: RenderConfig) -> None:
    draw.ellipse((865, -100, 1180, 215), fill="#F6E7EC")
    draw.arc((885, 20, 1060, 145), 200, 340, fill="#D6B1C0", width=3)
    draw.ellipse((-105, 1160, 185, 1450), fill="#EDF4F6")
    for x in range(80, 1040, 80):
        for y in range(40, 1320, 80):
            draw.ellipse((x, y, x + 2, y + 2), fill="#EFE8EB")


def _badge(draw: ImageDraw.ImageDraw, pos: tuple[int, int], text: str, fill: str, text_fill: str) -> None:
    font = _font(17, True, "en")
    box = draw.textbbox((0, 0), text, font=font)
    w = box[2] - box[0] + 28
    h = 40
    x, y = pos
    draw.rounded_rectangle((x, y, x + w, y + h), radius=20, fill=fill)
    draw.text((x + w / 2, y + h / 2), text, font=font, fill=text_fill, anchor="mm")


def _small_label(draw: ImageDraw.ImageDraw, pos: tuple[int, int], text: str, cfg: RenderConfig) -> None:
    font = _font(15, True, "ar" if _is_arabic(text) else "en")
    box = draw.textbbox((0, 0), text, font=font)
    w = box[2] - box[0] + 22
    x, y = pos
    draw.rounded_rectangle((x, y, x + w, y + 32), radius=16, fill=cfg.paper, outline=cfg.line)
    draw.text((x + w / 2, y + 16), text, font=font, fill=cfg.ink, anchor="mm", direction="rtl" if _is_arabic(text) else "ltr")


def _footer(draw: ImageDraw.ImageDraw, image: Image.Image, language: str, cfg: RenderConfig) -> None:
    y = 1270
    draw.rounded_rectangle((58, y, 178, y + 32), radius=16, fill=cfg.paper, outline=cfg.line)
    draw.ellipse((70, y + 11, 82, y + 23), fill=cfg.rose)
    draw.text((92, y + 16), "QMR7S", font=_font(13, True, "en"), fill=cfg.ink, anchor="lm")
    text = "للتثقيف الطبي فقط؛ لا يغني عن التقييم السريري." if language == "ar" else "For medical education only; not a substitute for clinical evaluation."
    draw.text((540, y + 16), text, font=_font(14, False, language), fill=cfg.muted, anchor="mm", direction="rtl" if _is_arabic(text) else "ltr")


def _fit_font(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_height: int, language: str) -> ImageFont.FreeTypeFont:
    size = font.size
    while size >= 15:
        candidate = _font(size, False, language)
        lines = _wrap(draw, text, candidate, max_width)
        if len(lines) * (size + 8) <= max_height:
            return candidate
        size -= 1
    return _font(15, False, language)


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
    direction = "rtl" if _is_arabic(text) else "ltr"
    try:
        box = draw.textbbox((0, 0), text, font=font, direction=direction)
    except ValueError:
        box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


@lru_cache(maxsize=64)
def _font(size: int, bold: bool, language: str) -> ImageFont.FreeTypeFont:
    if bold:
        paths = ["/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    else:
        paths = ["/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    if language == "en":
        paths = paths[1:] + paths[:1]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.truetype("DejaVuSans.ttf", size)


def _is_arabic(text: str) -> bool:
    return any("\u0600" <= c <= "\u06ff" for c in text)


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
