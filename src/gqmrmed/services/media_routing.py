"""Routing layer for local document parsing and AI rich-media extraction."""

from __future__ import annotations

from pathlib import Path

from gqmrmed.contracts.generation import InputType
from gqmrmed.services.media_extractors import LocalMediaExtractor, OpenAIMediaExtractor


class RoutingMediaExtractor:
    def __init__(self, local: LocalMediaExtractor, rich_media: OpenAIMediaExtractor | None) -> None:
        self._local = local
        self._rich_media = rich_media

    async def extract(self, *, path: Path, mime_type: str, input_type: InputType) -> str:
        if input_type is InputType.DOCUMENT:
            return await self._local.extract(path=path, mime_type=mime_type, input_type=input_type)
        if self._rich_media is None:
            raise RuntimeError("rich_media_ai_extractor_not_configured")
        return await self._rich_media.extract(path=path, mime_type=mime_type, input_type=input_type)


__all__ = ["RoutingMediaExtractor"]
