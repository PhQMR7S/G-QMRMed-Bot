# QMRMed master reference design system

The supplied Arabic medical infographic is the visual reference for the production design family. It is treated as a **design system**, not as a free-form style prompt.

## Canvas

- Canonical size: **1024×1536**.
- Ratio: **2:3**.
- Safe outer margin: 48 px.
- Footer safe zone: approximately 70 px.
- Main illustration panel: rounded, centered, upper-middle.

## Visual grammar

1. Warm ivory/off-white paper background.
2. Centered bold Arabic headline with short subtitle.
3. Small soft-pastel callout pills around the header.
4. Dominant medical illustration inside a clean rounded panel.
5. Three-column card grid for dense topics; two-column fallback for four cards.
6. Rounded cards with subtle border and no heavy shadows.
7. Pastel accent families: rose, cyan, mint, lavender and amber.
8. Dark plum/charcoal medical text with muted secondary text.
9. Small circular icon/number zone in each card header.
10. Compact educational disclaimer and QMRMed mark at the bottom.

## Typography

- Arabic: Noto Sans Arabic when available, with deterministic `arabic-reshaper` + `python-bidi` shaping.
- English: Noto Sans/DejaVu Sans fallback.
- Titles are bold and centered.
- Card headings are bold and short.
- Body text is exact source text from the validated medical content contract.

## AI boundary

OpenAI GPT-Image-2 receives an illustration-only prompt. It must not be asked to render the final infographic. It must not create readable labels, numbers, doses, citations, logos, watermarks, UI or disclaimers.

The deterministic compositor owns:

- all medical text;
- Arabic RTL shaping;
- card positions and sizes;
- section labels;
- colors;
- typography;
- footer and disclaimer;
- final 1024×1536 PNG contract.

This separation is the core mechanism for keeping the same design identity across different medical subjects.
