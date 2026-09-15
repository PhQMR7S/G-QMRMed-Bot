# Image Generation Boundary

## Scope

This stage establishes the production boundary between deterministic medical content/layout and the external illustration worker.

## Guarantees

- Image generation receives an illustration-only prompt from `VisualPlan`/`InfographicDesignSpec`.
- Readable medical text is never delegated to the image model.
- Requests use the canonical **1024×1536, 2:3** canvas.
- OpenAI GPT-Image-2 is the default illustration provider when `AI_API_KEY` is configured.
- Provider-specific details are isolated behind the image-provider contract/router.
- ComfyUI and other legacy providers remain optional and are not required by the default production path.
- The deterministic procedural provider remains available for zero-network CI/runtime validation.
- The generated artifact is represented by validated image bytes and dimensions; provider response metadata does not enter visible artwork.
- A deterministic seed can be supplied to legacy provider contracts where supported.
- The final raster is validated against the exact 1024×1536 PNG contract.

## Production boundary

`MedicalPlan -> VisualPlan -> Illustration-only prompt -> ImageProviderRouter -> GeneratedIllustration -> deterministic QMRMed compositor -> PNG`

OpenAI is responsible only for the clinical artwork layer. QMRMed renders exact Arabic/English text, cards, section labels, typography, branding and disclaimer locally. This separation prevents model-generated text/layout drift and preserves the master reference design across medical topics.
