"""Provider-neutral media ingestion and content extraction for Telegram jobs."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from gqmrmed.contracts.generation import InputType


class MediaIngestionError(RuntimeError):
    """Raised when an input cannot be safely ingested or interpreted."""


@dataclass(frozen=True, slots=True)
class IngestedMedia:
    """Normalized local media metadata and optional extracted text."""

    path: Path
    mime_type: str
    size_bytes: int
    sha256: str
    input_type: InputType
    extracted_text: str | None = None


class MediaSource(Protocol):
    async def download(self, storage_key: str, destination: Path) -> None: ...


class MediaExtractor(Protocol):
    async def extract(self, *, path: Path, mime_type: str, input_type: InputType) -> str: ...


@dataclass(frozen=True, slots=True)
class MediaIngestionConfig:
    max_bytes: int = 25 * 1024 * 1024


class MediaIngestor:
    """Download, validate, hash and interpret media through an injected extractor."""

    def __init__(
        self,
        source: MediaSource,
        config: MediaIngestionConfig | None = None,
        extractor: MediaExtractor | None = None,
    ) -> None:
        self._source = source
        self._config = config or MediaIngestionConfig()
        self._extractor = extractor
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
        guessed = mimetypes.guess_type(destination.name)[0]
        normalized_mime = (mime_type or guessed or "application/octet-stream").lower()
        input_type = _input_type_for_mime(normalized_mime)
        extracted_text: str | None = None
        if self._extractor is not None:
            try:
                extracted_text = (await self._extractor.extract(
                    path=destination,
                    mime_type=normalized_mime,
                    input_type=input_type,
                )).strip() or None
            except MediaIngestionError:
                raise
            except Exception as exc:
                raise MediaIngestionError("media_extraction_failed") from exc
        return IngestedMedia(
            path=destination,
            mime_type=normalized_mime,
            size_bytes=size,
            sha256=digest,
            input_type=input_type,
            extracted_text=extracted_text,
        )


def _input_type_for_mime(mime_type: str) -> InputType:
    if mime_type.startswith("image/"):
        return InputType.IMAGE
    if mime_type.startswith("audio/"):
        return InputType.AUDIO
    if mime_type.startswith("video/"):
        return InputType.VIDEO
    return InputType.DOCUMENT


__all__ = [
    "IngestedMedia",
    "MediaExtractor",
    "MediaIngestionConfig",
    "MediaIngestionError",
    "MediaIngestor",
    "MediaSource",
]
