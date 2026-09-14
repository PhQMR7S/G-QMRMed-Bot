# Image Generation Boundary

## Scope

This stage establishes the production boundary between deterministic medical content/layout and an external illustration worker.

## Guarantees

- Image generation receives an illustration-only prompt from `VisualPlan`.
- Readable medical text is never delegated to the image model.
- Requests use the canonical 4:5 canvas (`1080x1350`).
- Provider-specific details are isolated behind `IllustrationProvider`.
- ComfyUI/FLUX configuration is explicit and does not fabricate an asset when transport is unavailable.
- The generated artifact is represented by an opaque storage key rather than leaking provider-specific response data into the rest of the application.
- A deterministic seed can be supplied for reproducibility.
- The final raster is validated against the exact 1080x1350 PNG contract.

## Production boundary

`MedicalPlan -> VisualPlan -> ImageGenerationRequest -> IllustrationProvider -> ImageGenerationResult -> SVG/HTML exact-text renderer`

The current ComfyUI adapter is deliberately a safe provider shell. Actual GPU execution is a deployment concern and must be wired to a real ComfyUI worker before external-model image generation is considered production-complete. The deterministic fallback remains available for zero-network CI/runtime validation.
