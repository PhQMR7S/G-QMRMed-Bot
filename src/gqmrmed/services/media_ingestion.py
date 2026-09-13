"""Provider-neutral media ingestion and normalization for Telegram jobs."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from gqmrmed.contracts.generation import GenerationJob if False else InputType


class MediaIngestionError(RuntimeError):
    """Raised when an input cannot be safely ingested."""


@dataclass(frozen=True, slots=True)
class IngestedMedia:
    """Normalized local media metadata."""

    path: Path
    mime_type: str
    size_bytes: int
    sha256: str
    input_type: InputType
    extracted_text: str | None = None


class MediaSource(Protocol):
    async def download(self, storage_key: str, destination: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class MediaIngestionConfig:
    max_bytes: int = 25 * 1024 * 1024


class MediaIngestor:
    """Download, validate, hash and classify media without interpreting it."""

    def __init__(self, source: MediaSource, config: MediaIngestionConfig | None = None) -> None:
        self._source = source
        self._config = config or MediaIngestionConfig()
        if self._config.max_bytes <= 0:
            raise ValueError("invalid_media_max_bytes")

    async def ingest(
        self,
        *,
        storage_key: str,
        mime_type: str | None,
        destination: Path,
    ) -> IngestedMedia:
        if not storage_key.strip():
            raise MediaIngestionError("media_storage_key_required")
        destination.parent.mkdir(parents=True, exist_ok=True)
        await self._source.download(storage_key, destination)
        if not destination.is_file():
            raise MediaIngestionError("media_download_missing")
        size = destination.stat().st_size
        if size <= 0:
            raise MediaIngestionError("media_empty")
        if size > self._config.max_bytes:
            raise MediaIngestionError("media_too_large")
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        normalized_mime = (mime_type or mimetypes.guess_type(destination.name)[0] or "application/octet-stream").lower()
        return IngestedMedia(
            path=destination,
            mime_type=normalized_mime,
            size_bytes=size,
            sha256=digest,
            input_type=_input_type_for_mime(normalized_mime),
        )


def _input_type_for_mime(mime_type: str) -> InputType:
    if mime_type.startswith("image/"):
        return InputType.IMAGE
    if mime_type.startswith("audio/"):
        return InputType.AUDIO
    if mime_type.startswith("video/"):
        return InputType.VIDEO
    return InputType.DOCUMENT


__all__ = ["IngestedMedia", "MediaIngestionConfig", "MediaIngestionError", "MediaIngestor", "MediaSource"]
