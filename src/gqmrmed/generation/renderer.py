"""Deterministic 2:3 SVG renderer for exact medical text overlays."""

from html import escape

from gqmrmed.contracts.research import SynthesizedContent, VisualPlan

WIDTH, HEIGHT = 1024, 1536


def render_infographic_svg(*, content: SynthesizedContent, plan: VisualPlan) -> str:
    """Render text separately so the image model never controls factual text."""
    cards: list[str] = []
    points = content.key_points[:8]
    for i, point in enumerate(points):
        y = 600 + i * 105
        cards.append(
            f'<rect x="48" y="{y}" width="928" height="82" rx="24" fill="#fff"/>'
            f'<text x="74" y="{y + 52}" font-family="Arial" font-size="24" '
            f'fill="#172033">{escape(point)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
        '<rect width="100%" height="100%" fill="#fbf3f0"/>'
        f'<text x="512" y="120" text-anchor="middle" font-family="Arial" '
        f'font-size="52" font-weight="700">{escape(content.title)}</text>'
        f'<text x="512" y="172" text-anchor="middle" font-family="Arial" font-size="24" '
        f'fill="#746b74">{escape(content.subtitle or "")}</text>'
        '<rect x="48" y="220" width="928" height="330" rx="28" fill="#fff"/>'
        f'{"".join(cards)}'
        f'<text x="512" y="1488" text-anchor="middle" font-family="Arial" font-size="18" '
        f'fill="#746b74">{escape(content.disclaimer)}</text>'
        f'<text x="976" y="1510" text-anchor="end" font-family="Arial" '
        f'font-size="20" fill="#94a3b8">{escape(plan.watermark)}</text>'
        '</svg>'
    )
