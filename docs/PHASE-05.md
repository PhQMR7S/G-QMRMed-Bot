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
  -> rasterization to 1080x1920 PNG
```

## Guarantees

- Output canvas is 1080x1920 (9:16).
- The image model is never responsible for exact medical text.
- SVG escapes user/model text before inserting it into markup.
- Illustration assets are separate from the exact-text layer.
- Provider abstraction allows ComfyUI/local or a future external GPU/API provider without changing the medical pipeline.
- No web image is returned as the generated result.

## Current boundary

The ComfyUI adapter intentionally fails closed until a concrete, configured workflow/checkpoint is supplied. This prevents the bot from silently returning a placeholder or an unverified existing image.

Rasterization and the real ComfyUI workflow are the next implementation slice; they require the selected runtime/checkpoint and are not fabricated in this phase.
