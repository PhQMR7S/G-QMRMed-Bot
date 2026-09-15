# QMRMed master reference design system

The supplied medical infographics are the visual reference family for production. They are treated as a **design system**, not as a free-form style prompt.

## Canvas

- Canonical size: **1024×1536**.
- Ratio: **2:3**.
- Safe outer margin: 48 px.
- Footer safe zone: approximately 70 px.
- Main illustration panel: rounded, centered, upper-middle by default.

## Visual grammar

1. Warm ivory/off-white paper background.
2. Centered bold Arabic headline with short subtitle.
3. Small soft-pastel callout pills around the header.
4. Dominant medical illustration inside a clean rounded panel.
5. Three-column card grid for dense topics; two-column fallback for lighter topics.
6. Rounded cards with subtle borders and restrained shadows.
7. Pastel accent families: rose, cyan, mint, lavender and amber.
8. Dark plum/charcoal medical text with muted secondary text.
9. Small circular icon/number zone in each card header.
10. Compact educational disclaimer and QMRMed mark at the bottom.

## User-directed design

The user does **not** receive a fixed list of design presets. They can describe what they want naturally in the same message as the medical request. The system extracts explicit presentation intent and applies it to both the illustration prompt and deterministic compositor.

Supported natural-language controls include:

- palette and explicit HEX colors;
- background color;
- layout such as balanced cards, two/three columns, comparison, flow or timeline;
- information density and whitespace;
- illustration style such as realistic, anatomical, flat, diagrammatic or soft 3D;
- illustration position;
- header alignment/banner treatment;
- card corner shape;
- typography scale;
- footer visibility.

Unspecified properties remain on the master reference design instead of forcing the user to choose from a menu.

## Typography

- Arabic: Noto Sans Arabic when available, with deterministic `arabic-reshaper` + `python-bidi` shaping.
- English: Noto Sans/DejaVu Sans fallback.
- Titles are bold and centered by default.
- Card headings are bold and short.
- Body text is exact source text from the validated medical content contract.

## AI boundary

OpenAI GPT-Image-2 receives an illustration-only prompt. It must not be asked to render the final infographic. It must not create readable labels, numbers, doses, citations, logos, watermarks, UI or disclaimers.

The deterministic compositor owns:

- all medical text;
- Arabic RTL shaping;
- card positions and sizes;
- section labels;
- user-selected colors and background;
- typography scale and card geometry;
- footer and disclaimer;
- final 1024×1536 PNG contract.

This separation is the core mechanism for keeping the same design identity across different medical subjects while still allowing the user to direct the visual presentation.
