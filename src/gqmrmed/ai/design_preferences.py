"""Natural-language controls for user-directed infographic presentation."""
from __future__ import annotations

import re
from dataclasses import dataclass


_COLOR_MAP: dict[str, str] = {
    "وردي": "#C85E82",
    "زهري": "#C85E82",
    "بنفسجي": "#8C6AA9",
    "موف": "#8C6AA9",
    "أزرق": "#4C9FB0",
    "ازرق": "#4C9FB0",
    "سماوي": "#4C9FB0",
    "أخضر": "#73A98C",
    "اخضر": "#73A98C",
    "نعناعي": "#73A98C",
    "ذهبي": "#C49A5A",
    "أصفر": "#C49A5A",
    "اصفر": "#C49A5A",
    "برتقالي": "#C9784B",
    "أحمر": "#B84F5E",
    "احمر": "#B84F5E",
    "أسود": "#242126",
    "اسود": "#242126",
    "أبيض": "#FFFFFF",
    "ابيض": "#FFFFFF",
    "pink": "#C85E82",
    "purple": "#8C6AA9",
    "blue": "#4C9FB0",
    "green": "#73A98C",
    "mint": "#73A98C",
    "gold": "#C49A5A",
    "yellow": "#C49A5A",
    "orange": "#C9784B",
    "red": "#B84F5E",
    "black": "#242126",
    "white": "#FFFFFF",
}


@dataclass(frozen=True, slots=True)
class DesignPreferences:
    """Validated presentation controls extracted from the user's own wording."""

    palette: tuple[str, ...] | None = None
    background: str | None = None
    layout: str = "balanced"
    density: str = "balanced"
    illustration_style: str = "editorial clinical"
    illustration_position: str = "upper_middle"
    header_style: str = "centered"
    card_radius: int = 24
    font_scale: float = 1.0
    show_footer: bool = True
    raw_instruction: str = ""

    @property
    def prompt_fragment(self) -> str:
        """Return only explicit user controls, suitable for the image model."""
        parts: list[str] = []
        if self.palette:
            parts.append(
                "Use this user-selected palette: " + ", ".join(self.palette) + "."
            )
        if self.background:
            parts.append(f"Use this background color: {self.background}.")
        parts.append(f"Layout: {self.layout}.")
        parts.append(f"Information density: {self.density}.")
        parts.append(f"Illustration style: {self.illustration_style}.")
        parts.append(f"Illustration position: {self.illustration_position}.")
        parts.append(f"Header style: {self.header_style}.")
        if self.raw_instruction:
            parts.append(
                "Honor the user's additional design direction exactly: "
                + self.raw_instruction[:1200]
            )
        return " ".join(parts)


def extract_design_preferences(text: str) -> DesignPreferences:
    """Interpret explicit design language without presenting a fixed option menu."""
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    palette = _extract_palette(normalized)
    background = _extract_background(normalized)
    layout = "balanced"
    if any(token in lowered for token in ("timeline", "خط زمني", "زمني")):
        layout = "timeline"
    elif any(token in lowered for token in ("flow", "flowchart", "مخطط انسيابي", "تدفق", "مسار")):
        layout = "flow"
    elif any(token in lowered for token in ("comparison", "مقارنة", "مقارن")):
        layout = "comparison"
    elif any(token in lowered for token in ("two column", "عمودين", "عمودان")):
        layout = "two_column"
    elif any(token in lowered for token in ("three column", "ثلاثة أعمدة", "ثلاث اعمدة", "3 أعمدة")):
        layout = "three_column"
    elif any(token in lowered for token in ("central", "مركزي", "في الوسط", "وسط الصفحة")):
        layout = "central"

    density = "balanced"
    if any(token in lowered for token in ("minimal", "بسيط جداً", "بسيط جدا", "مساحات واسعة", "هوائي")):
        density = "airy"
    elif any(token in lowered for token in ("compact", "مضغوط", "معلومات كثيرة", "كثيف")):
        density = "compact"

    illustration_style = "editorial clinical"
    style_tokens = (
        ("واقعي", "realistic clinical"),
        ("ثلاثي الأبعاد", "soft 3D clinical"),
        ("ثلاثي الابعاد", "soft 3D clinical"),
        ("3d", "soft 3D clinical"),
        ("كرتوني", "friendly medical illustration"),
        ("تشريحي", "precise anatomical illustration"),
        ("diagram", "clean medical diagram"),
        ("مخطط", "clean medical diagram"),
        ("flat", "clean flat medical illustration"),
        ("مسطح", "clean flat medical illustration"),
    )
    for token, value in style_tokens:
        if token in lowered:
            illustration_style = value
            break

    position = "upper_middle"
    if any(token in lowered for token in ("يسار", "left")):
        position = "left"
    elif any(token in lowered for token in ("يمين", "right")):
        position = "right"
    elif any(token in lowered for token in ("أسفل", "اسفل", "bottom")):
        position = "lower_middle"
    elif any(token in lowered for token in ("في الوسط", "وسط", "center", "central")):
        position = "center"

    header_style = "centered"
    if any(token in lowered for token in ("شريط علوي", "banner", "ribbon", "بانر")):
        header_style = "banner"
    elif any(token in lowered for token in ("يسار العنوان", "عنوان يسار", "left aligned")):
        header_style = "left"

    radius = 24
    if any(token in lowered for token in ("حاد", "مربع", "sharp", "square")):
        radius = 8
    elif any(token in lowered for token in ("دائري", "مستدير جداً", "rounded")):
        radius = 34

    font_scale = 1.0
    if any(token in lowered for token in ("خط كبير", "نص كبير", "large typography")):
        font_scale = 1.15
    elif any(token in lowered for token in ("خط صغير", "نص صغير", "small typography")):
        font_scale = 0.9

    show_footer = not any(
        token in lowered
        for token in ("بدون تذييل", "اخفِ التذييل", "hide footer", "no footer")
    )
    return DesignPreferences(
        palette=palette,
        background=background,
        layout=layout,
        density=density,
        illustration_style=illustration_style,
        illustration_position=position,
        header_style=header_style,
        card_radius=radius,
        font_scale=font_scale,
        show_footer=show_footer,
        raw_instruction=_extract_explicit_design_clause(normalized),
    )


def _extract_palette(text: str) -> tuple[str, ...] | None:
    found: list[str] = []
    lowered = text.lower()
    for name, value in _COLOR_MAP.items():
        if name.lower() in lowered and value not in found:
            found.append(value)
    hexes = re.findall(r"#[0-9a-fA-F]{6}", text)
    for value in hexes:
        normalized = value.upper()
        if normalized not in found:
            found.append(normalized)
    return tuple(found[:6]) or None


def _extract_background(text: str) -> str | None:
    match = re.search(
        r"(?:خلفية|background)\s*(?:بلون|color)?\s*(#[0-9a-fA-F]{6})",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).upper()
    lowered = text.lower()
    for name, value in _COLOR_MAP.items():
        if re.search(rf"(?:خلفية|background)\s+(?:{re.escape(name)})", lowered):
            return value
    return None


def _extract_explicit_design_clause(text: str) -> str:
    markers = ("أريد", "اريد", "اجعل", "خلي", "أريد أن", "make it", "i want")
    lowered = text.lower()
    for marker in markers:
        index = lowered.find(marker.lower())
        if index >= 0:
            return text[index : index + 1800]
    return ""


__all__ = ["DesignPreferences", "extract_design_preferences"]
