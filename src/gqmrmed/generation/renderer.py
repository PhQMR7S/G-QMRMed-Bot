"""Deterministic 4:5 SVG renderer for exact medical text overlays."""

from html import escape

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan

WIDTH, HEIGHT = 1080, 1350


def render_infographic_svg(*, content: SynthesizedContent, plan: VisualPlan) -> str:
    """Render text separately so the image model never controls factual text."""
    cards = []
    for i, point in enumerate(content.key_points[:8]):
        y = 250 + i * 125
        cards.append(
            f'<rect x="70" y="{y}" width="940" height="100" rx="24" fill="#fff"/>'
            f'<text x="105" y="{y + 62}" font-family="Arial" font-size="28" '
            f'fill="#172033">{escape(point)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
        '<rect width="100%" height="100%" fill="#f5f5f4"/>'
        f'<text x="70" y="115" font-family="Arial" font-size="52" '
        f'font-weight="700">{escape(content.title)}</text>'
        f'<text x="70" y="170" font-family="Arial" font-size="24" '
        f'fill="#64748b">{escape(content.subtitle or "")}</text>'
        f'{"".join(cards)}'
        f'<text x="70" y="1280" font-family="Arial" font-size="18" '
        f'fill="#64748b">{escape(content.disclaimer)}</text>'
        f'<text x="980" y="1320" text-anchor="end" font-family="Arial" '
        f'font-size="20" fill="#94a3b8">{escape(plan.watermark)}</text>'
        '</svg>'
    )
