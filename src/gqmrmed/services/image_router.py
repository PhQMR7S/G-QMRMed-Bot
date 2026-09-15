"""Ordered image-provider routing with deterministic fallback behavior."""

from __future__ import annotations

from gqmrmed.generation.providers import (
    GeneratedIllustration,
    ImageGenerationError,
    ImageGenerationProvider,
)


class ImageProviderRouter:
    """Try configured illustration providers in order and fail only after all fail."""

    def __init__(self, providers: tuple[ImageGenerationProvider, ...]) -> None:
        if not providers:
            raise ValueError("image_provider_router_requires_provider")
        self._providers = providers

    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
    ) -> GeneratedIllustration:
        errors: list[str] = []
        for provider in self._providers:
            try:
                return await provider.generate(
                    prompt=prompt,
                    width=width,
                    height=height,
                )
            except RuntimeError as exc:
                errors.append(type(exc).__name__)
        raise ImageGenerationError(
            "all_image_providers_failed:" + ",".join(errors)
        )


__all__ = ["ImageProviderRouter"]
