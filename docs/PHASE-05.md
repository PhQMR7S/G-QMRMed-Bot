# Phase 5 — Image Generation + Exact Text Rendering

Phase 5 establishes the production boundary between AI illustration and deterministic medical typography.

## Pipeline

```text
MedicalPlan
  -> illustration prompt
  -> ImageGenerationProvider
  -> illustration asset
  -> deterministic SVG layout
  -> exact text / labels / watermark
  -> rasterization to 1080x1350 PNG
```

## Guarantees

- Output canvas is exactly 1080x1350 (4:5).
- The image model is never responsible for exact medical text.
- SVG escapes user/model text before inserting it into markup.
- Illustration assets are separate from the exact-text layer.
- Provider abstraction allows ComfyUI/local or a future external GPU/API provider without changing the medical pipeline.
- Quality control validates the final PNG signature and actual IHDR dimensions.
- No web image is returned as the generated result.

## Current boundary

The ComfyUI adapter intentionally fails closed until a concrete, configured workflow/checkpoint is supplied. This prevents the bot from silently returning a placeholder or an unverified existing image.

The deterministic pipeline, 4:5 layout, rasterization, quality gate, provider contracts, and automated tests are implemented. A real production ComfyUI deployment still requires its external workflow/checkpoint configuration and is intentionally not fabricated in the repository.
