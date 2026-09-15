# Phase 5 — Reference-Driven Image Generation + Exact Text Rendering

Phase 5 establishes the production boundary between AI illustration and deterministic medical typography.

## Pipeline

```text
MedicalPlan
  -> visual architecture + natural-language design preferences
  -> illustration-only prompt
  -> OpenAI GPT-Image-2 / configured image provider
  -> illustration asset
  -> deterministic QMRMed compositor
  -> exact Arabic/English text / labels / watermark
  -> rasterization to 1024x1536 PNG
```

## Guarantees

- Output canvas is exactly **1024×1536 (2:3)**.
- The image model is responsible only for the clinical artwork layer.
- Readable medical text, labels, numbers, disclaimer, branding and card geometry remain deterministic/local.
- Arabic text is shaped with `arabic-reshaper` + `python-bidi` before raster rendering.
- User-directed palette, background, layout, density, illustration style/position, header treatment, card radius and typography scale are applied without requiring preset menus.
- Illustration assets are separate from the exact-text layer.
- Provider abstraction allows OpenAI, optional ComfyUI/Hugging Face routes, and the deterministic procedural fallback without changing the medical pipeline.
- Quality control validates the final PNG signature and actual dimensions.
- No web image is returned as the generated result.

## Current boundary

OpenAI GPT-Image-2 is the default creative illustration provider when `AI_API_KEY` is configured. The default production image order is `openai,procedural`; ComfyUI is optional and no longer a prerequisite. The reference design is encoded as a stable visual language and applied by the deterministic compositor rather than relying on free-form model layout generation.
